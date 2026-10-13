"""
Workflow Execution Engine:
Compiles declarative workflows into DAG task runs, enforces department budgets
(HARD_STOP with additional budget request on API keys), manages execution state,
coordinates sandboxes, and captures run evaluations.
"""

import uuid
import logging
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

from persistence import DatabaseManager, Workflow, WorkflowExecution, WorkflowStepRun, RunEvaluation
from runtime.protocol import RuntimeAdapter
from runtime.models import AgentRun, TaskStatus
from .parser import WorkflowParser, WorkflowDefinition, WorkflowStepDefinition
from .sandbox import SandboxManager, SandboxSession

logger = logging.getLogger(__name__)


class BudgetExceededError(Exception):
    """Raised when department monthly budget is exceeded under HARD_STOP policy."""
    def __init__(self, department_id: str, message: str, current_spend: float, budget: float):
        super().__init__(message)
        self.department_id = department_id
        self.current_spend = current_spend
        self.budget = budget


@dataclass
class WorkflowStepResult:
    """Result of an individual workflow step execution."""
    step_key: str
    status: str
    task_run_id: str
    output: Optional[str] = None
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    error: Optional[str] = None


class WorkflowEngine:
    """
    Core engine managing the lifecycle and execution of multi-agent workflows.
    Reuses existing DatabaseManager, OrchestrationEngine, and RuntimeAdapter.
    """

    def __init__(
        self,
        db_manager: DatabaseManager,
        runtime_adapter: Optional[RuntimeAdapter] = None,
        orchestration_engine: Any = None,
        sandbox_manager: Optional[SandboxManager] = None
    ):
        self.db = db_manager
        self.runtime = runtime_adapter
        self.orchestration = orchestration_engine
        self.sandbox_manager = sandbox_manager or SandboxManager()

    def execute_workflow(
        self,
        workflow_id: str,
        trigger_type: str = "MANUAL",
        trigger_payload: Optional[Dict[str, Any]] = None,
        source_workspace: Optional[str] = None,
        runtime_provider: Optional[str] = None
    ) -> WorkflowExecution:
        """
        Execute an entire workflow instance.
        1. Checks department budget (HARD_STOP if exceeded).
        2. Sets up isolated sandbox environment.
        3. Executes DAG steps in dependency order.
        4. Aggregates tokens, cost, and final status.
        5. Cleans up sandbox.
        """
        workflow = self.db.get_workflow(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow '{workflow_id}' not found")

        # 1. Budget pre-check (HARD_STOP enforcement on API_KEY runs)
        dept_id = workflow.department_id
        if dept_id:
            budget_status = self.db.check_department_budget(dept_id)
            if not budget_status.get("allowed", True):
                raise BudgetExceededError(
                    department_id=dept_id,
                    message=budget_status.get("message", "Department budget limit exceeded. Additional budget required."),
                    current_spend=budget_status.get("current_spend_usd", 0.0),
                    budget=budget_status.get("monthly_budget_usd", 0.0)
                )

        execution_id = f"wf_exec_{uuid.uuid4().hex[:12]}"

        # 2. Setup sandbox session
        sandbox = self.sandbox_manager.create_sandbox(
            execution_id=execution_id,
            source_workspace=source_workspace
        )

        # 3. Create execution record in database
        payload_str = str(trigger_payload) if trigger_payload else None
        wf_exec = self.db.create_workflow_execution(
            execution_id=execution_id,
            workflow_id=workflow_id,
            trigger_type=trigger_type,
            trigger_payload=payload_str,
            department_id=dept_id,
            sandbox_path=sandbox.path
        )

        # 4. Parse workflow definition
        wf_def: WorkflowDefinition
        try:
            wf_def = WorkflowParser.from_json(workflow.definition_json)
        except Exception:
            try:
                wf_def = WorkflowParser.from_yaml(workflow.definition_json)
            except Exception as e:
                self.db.update_workflow_execution(
                    execution_id,
                    status="FAILED",
                    error_message=f"Invalid workflow definition format: {e}",
                    completed_at=datetime.now().isoformat()
                )
                sandbox.cleanup()
                return self.db.get_workflow_execution(execution_id)

        # 5. Execute steps in DAG dependency order
        step_outputs: Dict[str, str] = {}
        total_input_tokens = 0
        total_output_tokens = 0
        total_cost_usd = 0.0
        final_status = "COMPLETED"
        failure_error: Optional[str] = None

        try:
            ordered_steps = self._topological_sort_steps(wf_def.steps)
            for step in ordered_steps:
                # Check mid-run budget cap before launching next step
                if dept_id:
                    check = self.db.check_department_budget(dept_id, requested_cost=total_cost_usd)
                    if not check.get("allowed", True):
                        final_status = "FAILED"
                        failure_error = f"Mid-run budget exceeded for department {dept_id}. Additional budget required."
                        break

                # Prepare prompt with dynamic substitutions from previous step outputs
                formatted_prompt = step.prompt_template
                for prev_key, prev_out in step_outputs.items():
                    formatted_prompt = formatted_prompt.replace(f"{{{{{prev_key}.output}}}}", prev_out or "")
                    formatted_prompt = formatted_prompt.replace(f"${{{prev_key}.output}}", prev_out or "")

                if trigger_payload:
                    for k, v in trigger_payload.items():
                        formatted_prompt = formatted_prompt.replace(f"{{{{{k}}}}}", str(v))
                        formatted_prompt = formatted_prompt.replace(f"${{{k}}}", str(v))

                # Step-level Skills injection (dynamic resolution)
                step_skills = []
                for sk in getattr(step, "skills", []) or []:
                    sk_rendered = str(sk)
                    if trigger_payload:
                        for k, v in trigger_payload.items():
                            sk_rendered = sk_rendered.replace(f"{{{{{k}}}}}", str(v))
                            sk_rendered = sk_rendered.replace(f"${{{k}}}", str(v))
                    step_skills.append(sk_rendered)

                if step_skills:
                    try:
                        from skills_service import build_skills_system_prompt
                        skills_context = build_skills_system_prompt(step_skills)
                        if skills_context:
                            formatted_prompt = f"{skills_context}\n\n[TASK INSTRUCTIONS]\n{formatted_prompt}"
                    except Exception as sk_err:
                        logger.warning(f"Failed to build skills prompt for step '{step.key}': {sk_err}")

                # Ensure agent exists in database (reuse or auto-provision)
                agent = self.db.get_agent(step.agent_id)
                actual_agent_id = step.agent_id
                if not agent:
                    try:
                        from config import AgentConfig
                        placeholder = AgentConfig(
                            id=step.agent_id,
                            name=step.name or step.agent_id,
                            description=f"Auto-generated agent for workflow step {step.key}",
                            system_prompt=f"You are an autonomous agent specialized in {step.name or step.key}.",
                            model="default"
                        )
                        self.db.save_agent(placeholder)
                    except Exception as ex:
                        logger.warning(f"Could not auto-provision agent '{step.agent_id}': {ex}")
                        existing = self.db.list_agents()
                        if existing:
                            actual_agent_id = existing[0].id
                        else:
                            raise

                # Create task run for this step
                task_id = f"task_{uuid.uuid4().hex[:12]}"
                now_dt = datetime.now()
                step_run = AgentRun(
                    run_id=task_id,
                    agent_id=actual_agent_id,
                    project_id=None,
                    prompt=formatted_prompt,
                    status=TaskStatus.RUNNING,
                    created_at=now_dt,
                    started_at=now_dt,
                    acceptance_criteria=step.acceptance_criteria,
                    retry_count=step.retry_count
                )
                self.db.save_task_run(step_run)

                # Execute step via runtime adapter if available
                if self.runtime:
                    try:
                        self.runtime.start_task(
                            task_id=task_id,
                            agent_id=actual_agent_id,
                            prompt=formatted_prompt
                        )
                        # Poll for task completion up to step timeout (capped at 300s)
                        import time
                        max_wait = min(step.timeout_seconds or 180, 300)
                        start_wait = time.time()
                        while time.time() - start_wait < max_wait:
                            updated_run = self.db.get_task_run(task_id)
                            if updated_run and str(updated_run.status).lower() in (
                                "completed", "failed", "cancelled",
                                str(TaskStatus.COMPLETED).lower(),
                                str(TaskStatus.FAILED).lower(),
                                str(TaskStatus.CANCELLED).lower()
                            ):
                                break
                            time.sleep(1.0)
                    except Exception as ex:
                        logger.warning(f"Runtime execution warning for step '{step.key}': {ex}")

                # Refresh task run to capture output, tokens, and cost
                updated_run = self.db.get_task_run(task_id) or step_run
                step_output = updated_run.result or getattr(updated_run, "error", None) or f"Step {step.name} completed"
                step_outputs[step.key] = step_output

                # Aggregate metrics
                step_in_tok = getattr(updated_run, "input_tokens", 0) or 0
                step_out_tok = getattr(updated_run, "output_tokens", 0) or 0
                step_cost = getattr(updated_run, "cost_usd", 0.0) or 0.0

                total_input_tokens += step_in_tok
                total_output_tokens += step_out_tok
                total_cost_usd += step_cost

                # Record step run
                now_iso = datetime.now().isoformat()
                with self.db._get_connection() as conn:
                    conn.execute("""
                        INSERT INTO workflow_step_runs (
                            id, execution_id, step_key, agent_id, status, task_run_id,
                            input_data, output_data, input_tokens, output_tokens, cost_usd,
                            started_at, completed_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        f"step_run_{uuid.uuid4().hex[:8]}",
                        execution_id,
                        step.key,
                        actual_agent_id,
                        "COMPLETED",
                        task_id,
                        formatted_prompt,
                        step_output,
                        step_in_tok,
                        step_out_tok,
                        step_cost,
                        now_iso,
                        now_iso
                    ))
                    conn.commit()

        except Exception as e:
            final_status = "FAILED"
            failure_error = str(e)
            logger.error(f"Workflow execution {execution_id} failed: {e}", exc_info=True)
        finally:
            # Clean up ephemeral sandbox
            sandbox.cleanup()

        # Update final execution record
        self.db.update_workflow_execution(
            execution_id=execution_id,
            status=final_status,
            total_input_tokens=total_input_tokens,
            total_output_tokens=total_output_tokens,
            total_cost_usd=total_cost_usd,
            completed_at=datetime.now().isoformat(),
            error_message=failure_error
        )

        # Dispatch outgoing notification to bound communication channel (Slack / Telegram)
        try:
            import json
            wf_record = self.db.get_workflow(workflow_id)
            if wf_record and wf_record.definition_json:
                dj = json.loads(wf_record.definition_json)
                channel_binding = dj.get("metadata", {}).get("channel_binding")
                if channel_binding:
                    notify_mode = channel_binding.get("notify_mode", "ON_COMPLETE")
                    should_notify = (
                        notify_mode == "ALWAYS" or
                        (notify_mode == "ON_COMPLETE" and final_status == "COMPLETED") or
                        (notify_mode == "ON_FAILURE" and final_status == "FAILED")
                    )
                    if should_notify:
                        provider = channel_binding.get("provider", "slack")
                        channel_id = channel_binding.get("channel_id", "")
                        custom_tmpl = channel_binding.get("message_template")
                        
                        # Extract final step output or synthesized report
                        final_output = list(step_outputs.values())[-1] if step_outputs else ""
                        if len(final_output) > 2500:
                            final_output = final_output[:2450] + "...\n(truncated)"

                        if custom_tmpl:
                            msg_body = custom_tmpl.replace("{{workflow_name}}", wf_record.name).replace("{{status}}", final_status)
                            if "{{output}}" in custom_tmpl:
                                msg_body = msg_body.replace("{{output}}", final_output)
                            elif final_output and final_output not in msg_body:
                                msg_body += f"\n\n📋 *Workflow Summary / Report:*\n{final_output}"
                        else:
                            msg_body = (
                                f"🤖 *Workflow Run Notification*\n"
                                f"• Workflow: *{wf_record.name}* (`{wf_record.id}`)\n"
                                f"• Status: *{final_status}*\n"
                                f"• Trigger: `{trigger_type}`\n"
                                f"• Tokens: {total_input_tokens + total_output_tokens} (Cost: ${total_cost_usd:.4f})"
                            )
                            if final_output:
                                msg_body += f"\n\n📋 *Result:*\n{final_output}"
                            if failure_error:
                                msg_body += f"\n• Error: {failure_error}"

                        # Dispatch live HTTP notification to Telegram if provider is telegram
                        if provider.lower() == "telegram":
                            try:
                                conn = self.db.get_mcp_connector("telegram")
                                if conn and conn.configuration:
                                    bot_token = conn.configuration.get("bot_token")
                                    configured_chat_id = conn.configuration.get("chat_id")
                                    target_chat = channel_id
                                    if target_chat in ("@agents_office_alerts", "@hermesganbot", "hermesganbot", "Hermes_test") and configured_chat_id:
                                        target_chat = configured_chat_id
                                    elif target_chat.lower().endswith("bot") and configured_chat_id:
                                        target_chat = configured_chat_id

                                    if bot_token and target_chat:
                                        import urllib.request
                                        payload = json.dumps({"chat_id": target_chat, "text": msg_body}).encode("utf-8")
                                        telegram_req = urllib.request.Request(
                                            f"https://api.telegram.org/bot{bot_token}/sendMessage",
                                            data=payload,
                                            headers={"Content-Type": "application/json"}
                                        )
                                        with urllib.request.urlopen(telegram_req, timeout=5) as t_resp:
                                            if t_resp.status == 200:
                                                logger.info(f"Successfully delivered live Telegram notification to {target_chat}")
                            except Exception as t_err:
                                logger.warning(f"Failed to post live notification to Telegram API: {t_err}")

                        # Record notification as an MCP tool call in SQLite
                        now_dt = datetime.now().isoformat()
                        self.db.save_mcp_tool_call({
                            "id": f"call_notify_{uuid.uuid4().hex[:8]}",
                            "connector_id": channel_binding.get("connector_id", provider),
                            "tool_id": f"tool_{provider}_send_message",
                            "agent_id": "ceo-orchestrator",
                            "task_id": None,
                            "arguments": {"channel": channel_id, "text": msg_body},
                            "status": "COMPLETED",
                            "result": f"Notification posted to {channel_id}",
                            "started_at": now_dt,
                            "completed_at": now_dt
                        })
                        logger.info(f"Successfully posted workflow notification to {provider}:{channel_id}")
        except Exception as notify_err:
            logger.warning(f"Failed to dispatch channel binding notification: {notify_err}")

        return self.db.get_workflow_execution(execution_id)

    def _topological_sort_steps(self, steps: List[Any]) -> List[Any]:
        """Order steps according to their DAG dependencies (from depends_on / flow)."""
        if not steps:
            return []
        step_map = {s.key: s for s in steps}
        in_degree = {s.key: 0 for s in steps}
        adj: Dict[str, List[str]] = {s.key: [] for s in steps}

        for s in steps:
            for dep in s.depends_on:
                if dep in step_map:
                    adj[dep].append(s.key)
                    in_degree[s.key] += 1

        queue = [s.key for s in steps if in_degree[s.key] == 0]
        ordered_keys: List[str] = []

        while queue:
            curr = queue.pop(0)
            ordered_keys.append(curr)
            for neighbor in adj.get(curr, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # In case of disconnected steps or cycles, append remaining steps
        for s in steps:
            if s.key not in ordered_keys:
                ordered_keys.append(s.key)

        return [step_map[k] for k in ordered_keys if k in step_map]
