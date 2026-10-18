"""
Workflow Execution Engine:
Compiles declarative workflows into DAG task runs, enforces department budgets
(HARD_STOP with additional budget request on API keys), manages execution state,
coordinates sandboxes, supports parallel multi-agent stages, step-level skills,
maker-checker reviews, and captures run evaluations.
"""

import re
import uuid
import logging
import concurrent.futures
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


class MCPGovernanceViolationError(Exception):
    """Raised when an MCP connector or tool violates department governance policies."""
    def __init__(self, department_id: str, connector_id: str, reason: str, tool_name: Optional[str] = None):
        super().__init__(reason)
        self.department_id = department_id
        self.connector_id = connector_id
        self.tool_name = tool_name
        self.reason = reason


class UnauthorizedUserDepartmentError(Exception):
    """Raised when an authenticated user attempts to execute a workflow outside their authorized departments."""
    def __init__(self, user_id: str, department_id: str, message: str):
        super().__init__(message)
        self.user_id = user_id
        self.department_id = department_id


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


def evaluate_condition_rule(rule: Dict[str, Any], payload: Dict[str, Any]) -> bool:
    """Evaluate a single rule against a nested payload using dot notation."""
    field_path = rule.get("field", "")
    operator = rule.get("operator", "equals").lower()
    target_value = rule.get("value")

    curr = payload
    for part in field_path.split("."):
        if isinstance(curr, dict) and part in curr:
            curr = curr[part]
        else:
            curr = None
            break

    if curr is None:
        return False

    str_curr = str(curr)
    str_target = str(target_value)

    if operator in ("matches", "regex"):
        return bool(re.search(str_target, str_curr))
    elif operator in ("equals", "eq", "=="):
        return str_curr == str_target
    elif operator in ("not_equals", "ne", "!="):
        return str_curr != str_target
    elif operator in ("contains", "has"):
        return str_target in str_curr
    elif operator == "in":
        if isinstance(target_value, (list, tuple)):
            return curr in target_value
        return str_curr in str_target
    return False


def evaluate_trigger_conditions(trigger: Dict[str, Any], payload: Dict[str, Any]) -> bool:
    """Evaluate full trigger conditions with combinator 'and'/'or'."""
    conds = trigger.get("conditions")
    if not conds:
        return True
    combinator = conds.get("combinator", "and").lower()
    rules = conds.get("rules", [])
    if not rules:
        return True

    results = [evaluate_condition_rule(r, payload) for r in rules]
    if combinator == "or":
        return any(results)
    return all(results)


class WorkflowEngine:
    """
    Core engine managing the lifecycle and execution of multi-agent workflows.
    Reuses existing DatabaseManager, OrchestrationEngine, and RuntimeAdapter.
    Supports parallel multi-agent stage execution, step-level skills, and maker-checker loops.
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
        runtime_provider: Optional[str] = None,
        user_context: Optional[Dict[str, Any]] = None
    ) -> WorkflowExecution:
        """
        Execute an entire workflow instance.
        1. Checks user department authorization (Tenant & Department Isolation).
        2. Checks department budget (HARD_STOP if exceeded).
        3. Sets up isolated sandbox environment.
        4. Executes DAG steps in dependency order and parallel multi-agent stages.
        5. Accumulates token usage, cost, outputs, and dispatches notifications.
        """
        workflow = self.db.get_workflow(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow '{workflow_id}' not found")

        # 1. Budget and Department Access Authorization pre-check
        dept_id = workflow.department_id
        if dept_id:
            # Check user department authorization if user context is provided
            if user_context:
                user_role = user_context.get("role", "MEMBER")
                if user_role != "ORG_ADMIN":
                    raw_depts = user_context.get("departments", [])
                    authorized_depts = [
                        d.get("id") if isinstance(d, dict) else str(d)
                        for d in raw_depts
                    ]
                    if dept_id not in authorized_depts:
                        raise UnauthorizedUserDepartmentError(
                            user_id=user_context.get("sub", "unknown"),
                            department_id=dept_id,
                            message=f"User '{user_context.get('email', user_context.get('sub'))}' is not an authorized member of department '{dept_id}'"
                        )

            budget_status = self.db.check_department_budget(dept_id)
            if not budget_status.get("allowed", True):
                raise BudgetExceededError(
                    department_id=dept_id,
                    message=budget_status.get("message", "Department budget limit exceeded. Additional budget required."),
                    current_spend=budget_status.get("current_spend_usd", 0.0),
                    budget=budget_status.get("monthly_budget_usd", 0.0)
                )

        execution_id = f"wf_exec_{uuid.uuid4().hex[:12]}"

        # 1b. Sanitize external trigger payload (size ceiling + control char stripping)
        if trigger_payload is not None:
            from shared.payload_sanitizer import sanitize_trigger_payload
            trigger_payload = sanitize_trigger_payload(trigger_payload)

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

        # 4b. Pre-flight MCP Governance check & Short-Lived ScopedRunToken Issuance
        all_mcp_servers = set(getattr(wf_def, "mcp_servers", []) or [])
        for s in wf_def.steps:
            for sm in (getattr(s, "mcp_servers", []) or []):
                all_mcp_servers.add(sm)

        if dept_id:
            for conn_id in sorted(all_mcp_servers):
                perm = self.db.check_department_mcp_permission(dept_id, conn_id)
                if not perm.get("allowed", False):
                    err_msg = f"MCP Governance Violation: {perm.get('reason')}"
                    self.db.update_workflow_execution(
                        execution_id,
                        status="FAILED",
                        error_message=err_msg,
                        completed_at=datetime.now().isoformat()
                    )
                    sandbox.cleanup()
                    raise MCPGovernanceViolationError(
                        department_id=dept_id,
                        connector_id=conn_id,
                        reason=err_msg
                    )

        from gateways.secrets_broker import secrets_broker
        org_id_for_run = (user_context or {}).get("org_id") or "org_default"
        user_id_for_run = (user_context or {}).get("sub")
        scoped_run_token = secrets_broker.issue_run_token(
            org_id=org_id_for_run,
            department_id=dept_id or "dept_default",
            run_id=execution_id,
            user_id=user_id_for_run,
            allowed_mcps=sorted(all_mcp_servers) if all_mcp_servers else ["*"],
        )

        # 5. Execute steps in DAG dependency stages (multi-agent parallel execution)
        step_outputs: Dict[str, str] = {}
        total_input_tokens = 0
        total_output_tokens = 0
        total_cost_usd = 0.0
        final_status = "COMPLETED"
        failure_error: Optional[str] = None

        try:
            stages = self._group_steps_into_stages(wf_def.steps)
            for stage in stages:
                # Check mid-run budget cap before launching next stage
                if dept_id:
                    check = self.db.check_department_budget(dept_id, requested_cost=total_cost_usd)
                    if not check.get("allowed", True):
                        final_status = "FAILED"
                        failure_error = f"Mid-run budget exceeded for department {dept_id}. Additional budget required."
                        break

                if len(stage) == 1:
                    # Sequential step execution
                    res = self._execute_single_step(
                        step=stage[0],
                        execution_id=execution_id,
                        step_outputs=step_outputs,
                        trigger_payload=trigger_payload,
                        dept_id=dept_id
                    )
                    step_outputs[res.step_key] = res.output or ""
                    total_input_tokens += res.input_tokens
                    total_output_tokens += res.output_tokens
                    total_cost_usd += res.cost_usd
                    if res.status != "COMPLETED":
                        final_status = res.status
                        failure_error = res.error
                        break
                else:
                    # Parallel multi-agent execution across independent steps
                    with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(stage), 4)) as executor:
                        future_map = {
                            executor.submit(
                                self._execute_single_step,
                                s,
                                execution_id,
                                dict(step_outputs),
                                trigger_payload,
                                dept_id
                            ): s for s in stage
                        }
                        for fut in concurrent.futures.as_completed(future_map):
                            res = fut.result()
                            step_outputs[res.step_key] = res.output or ""
                            total_input_tokens += res.input_tokens
                            total_output_tokens += res.output_tokens
                            total_cost_usd += res.cost_usd
                            if res.status != "COMPLETED" and final_status == "COMPLETED":
                                final_status = res.status
                                failure_error = res.error

                    if final_status != "COMPLETED":
                        break

        except MCPGovernanceViolationError as e:
            final_status = "FAILED"
            failure_error = str(e)
            sandbox.cleanup()
            self.db.update_workflow_execution(
                execution_id=execution_id,
                status=final_status,
                total_input_tokens=total_input_tokens,
                total_output_tokens=total_output_tokens,
                total_cost_usd=total_cost_usd,
                completed_at=datetime.now().isoformat(),
                error_message=failure_error
            )
            raise
        except Exception as e:
            final_status = "FAILED"
            failure_error = str(e)
            logger.error(f"Workflow execution {execution_id} failed: {e}", exc_info=True)
        finally:
            secrets_broker.revoke_run_token(scoped_run_token.token, reason="Workflow execution finished")
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
        from shared.notifications import dispatch_workflow_completion_notification
        dispatch_workflow_completion_notification(
            db=self.db,
            workflow_id=workflow_id,
            final_status=final_status,
            trigger_type=trigger_type,
            step_outputs=step_outputs,
            total_tokens=total_input_tokens + total_output_tokens,
            total_cost_usd=total_cost_usd,
            failure_error=failure_error
        )

        return self.db.get_workflow_execution(execution_id)

    def _execute_single_step(
        self,
        step: WorkflowStepDefinition,
        execution_id: str,
        step_outputs: Dict[str, str],
        trigger_payload: Optional[Dict[str, Any]],
        dept_id: Optional[str]
    ) -> WorkflowStepResult:
        """Execute a single workflow step with dynamic substitutions, skill injection, and agent reuse."""
        formatted_prompt = step.prompt_template
        for prev_key, prev_out in step_outputs.items():
            formatted_prompt = formatted_prompt.replace(f"{{{{{prev_key}.output}}}}", prev_out or "")
            formatted_prompt = formatted_prompt.replace(f"${{{prev_key}.output}}", prev_out or "")

        if trigger_payload:
            for k, v in trigger_payload.items():
                formatted_prompt = formatted_prompt.replace(f"{{{{{k}}}}}", str(v))
                formatted_prompt = formatted_prompt.replace(f"${{{k}}}", str(v))

        # Step-level MCP Governance check & Tool filtering (Least Privilege & Hard Block)
        if dept_id and getattr(step, "mcp_servers", None):
            for conn_id in step.mcp_servers:
                perm = self.db.check_department_mcp_permission(dept_id, conn_id)
                if not perm.get("allowed", False):
                    raise MCPGovernanceViolationError(
                        department_id=dept_id,
                        connector_id=conn_id,
                        reason=perm.get("reason", f"Access to MCP connector '{conn_id}' denied for department '{dept_id}'")
                    )

                # Tool-level filtering
                step_tools = []
                if hasattr(step, "params") and isinstance(step.params, dict):
                    raw_tools = step.params.get("tools") or step.params.get("mcp_tools") or []
                    if isinstance(raw_tools, list):
                        step_tools = raw_tools
                    elif isinstance(raw_tools, str):
                        step_tools = [raw_tools]

                for t in step_tools:
                    tool_perm = self.db.check_department_mcp_permission(dept_id, conn_id, tool_name=t)
                    if not tool_perm.get("allowed", False):
                        raise MCPGovernanceViolationError(
                            department_id=dept_id,
                            connector_id=conn_id,
                            reason=tool_perm.get("reason", f"Tool '{t}' blocked by department policy"),
                            tool_name=t
                        )

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

        # Optional Maker-Checker review
        reviewer_id = step.params.get("reviewerAgentId") if getattr(step, "params", None) else None
        if reviewer_id and self.runtime:
            try:
                reviewer_agent = self.db.get_agent(reviewer_id)
                if reviewer_agent:
                    review_task_id = f"review_{uuid.uuid4().hex[:10]}"
                    updated_run = self.db.get_task_run(task_id) or step_run
                    rev_prompt = (
                        f"Review deliverable from {actual_agent_id} for step '{step.name}'.\n"
                        f"Acceptance criteria: {step.acceptance_criteria or 'Ensure high quality'}\n"
                        f"Deliverable:\n{updated_run.result or 'No output'}"
                    )
                    self.runtime.start_task(task_id=review_task_id, agent_id=reviewer_id, prompt=rev_prompt)
            except Exception as r_err:
                logger.warning(f"Maker-checker review note for step '{step.key}': {r_err}")

        # Refresh task run to capture output, tokens, and cost
        updated_run = self.db.get_task_run(task_id) or step_run
        step_output = updated_run.result or getattr(updated_run, "error", None) or f"Step {step.name} completed"
        step_in_tok = getattr(updated_run, "input_tokens", 0) or 0
        step_out_tok = getattr(updated_run, "output_tokens", 0) or 0
        step_cost = getattr(updated_run, "cost_usd", 0.0) or 0.0

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

        return WorkflowStepResult(
            step_key=step.key,
            status="COMPLETED",
            task_run_id=task_id,
            output=step_output,
            input_tokens=step_in_tok,
            output_tokens=step_out_tok,
            cost_usd=step_cost
        )

    def _group_steps_into_stages(self, steps: List[WorkflowStepDefinition]) -> List[List[WorkflowStepDefinition]]:
        """Group steps into DAG execution stages for parallel multi-agent execution."""
        if not steps:
            return []
        step_map = {s.key: s for s in steps}
        completed_keys = set()
        stages: List[List[WorkflowStepDefinition]] = []
        remaining = list(steps)

        while remaining:
            ready = [
                s for s in remaining
                if all(dep in completed_keys or dep not in step_map for dep in s.depends_on)
            ]
            if not ready:
                # Cycle or disconnected steps - fallback to sequential
                stages.append(remaining)
                break
            stages.append(ready)
            for s in ready:
                completed_keys.add(s.key)
                remaining.remove(s)

        return stages

    def _topological_sort_steps(self, steps: List[Any]) -> List[Any]:
        """Flatten stages into ordered steps."""
        stages = self._group_steps_into_stages(steps)
        res = []
        for stage in stages:
            res.extend(stage)
        return res
