"""Workflow step execution, policy gates and result capture."""
import uuid
import logging
from datetime import datetime
from typing import Dict, Optional, Any
from runtime.models import AgentRun, TaskStatus
from .parser import WorkflowStepDefinition
from .execution_models import WorkflowStepResult, MCPGovernanceViolationError

logger = logging.getLogger(__name__)


class WorkflowStepRunner:
    def __init__(self, database, runtime, skill_context=None):
        self.db = database
        self.runtime = runtime
        self.skill_context = skill_context

    def execute(
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

        if step_skills and self.runtime is not None:
            if self.skill_context is None:
                raise RuntimeError("Required skill context provider is unavailable")
            skills_context = self.skill_context(step_skills)
            if not skills_context:
                raise RuntimeError("Configured step skill context could not be resolved")
            formatted_prompt = f"{skills_context}\n\n[TASK INSTRUCTIONS]\n{formatted_prompt}"

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

        # A missing runtime, failure, pause or timeout is never a completed step.
        updated_run = step_run
        try:
            if self.runtime is None:
                raise RuntimeError("Runtime capability is unavailable")
            self.runtime.start_task(task_id=task_id, agent_id=actual_agent_id, prompt=formatted_prompt)
            import time
            deadline = time.monotonic() + min(step.timeout_seconds or 180, 300)
            observed = {
                "completed", "failed", "cancelled", "waiting_input", "pending_approval",
                "waiting_for_children", "waiting_for_manager", "waiting_for_human",
            }
            while time.monotonic() < deadline:
                updated_run = self.db.get_task_run(task_id) or step_run
                state = getattr(updated_run.status, "value", updated_run.status)
                if str(state).lower() in observed:
                    break
                time.sleep(1.0)
            else:
                if hasattr(self.runtime, "cancel_run"):
                    self.runtime.cancel_run(task_id)
                raise TimeoutError(f"Workflow step '{step.key}' exceeded its runtime timeout")
        except Exception as error:
            updated_run = self.db.get_task_run(task_id) or step_run
            updated_run.status = TaskStatus.FAILED
            updated_run.error = str(error)
            updated_run.ended_at = datetime.now()
            self.db.save_task_run(updated_run)
            logger.warning("Workflow step %s did not complete: %s", step.key, error)

        step_status = str(getattr(updated_run.status, "value", updated_run.status)).upper()
        # Optional Maker-Checker review
        reviewer_id = step.params.get("reviewerAgentId") if getattr(step, "params", None) else None
        if reviewer_id and self.runtime and step_status == "COMPLETED":
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
        step_output = updated_run.result or updated_run.error or ""
        step_in_tok = getattr(updated_run, "input_tokens", 0) or 0
        step_out_tok = getattr(updated_run, "output_tokens", 0) or 0
        step_cost = getattr(updated_run, "cost_usd", 0.0) or 0.0

        now_iso = datetime.now().isoformat()
        self.db.save_workflow_step_run({
            "id": f"step_run_{uuid.uuid4().hex[:8]}", "execution_id": execution_id,
            "step_key": step.key, "agent_id": actual_agent_id, "status": step_status,
            "task_run_id": task_id, "input_data": formatted_prompt,
            "output_data": step_output, "input_tokens": step_in_tok,
            "output_tokens": step_out_tok, "cost_usd": step_cost,
            "started_at": now_dt.isoformat(),
            "completed_at": now_iso if step_status in {"COMPLETED", "FAILED", "CANCELLED"} else None,
        })

        return WorkflowStepResult(
            step_key=step.key,
            status=step_status,
            error=updated_run.error,
            task_run_id=task_id,
            output=step_output,
            input_tokens=step_in_tok,
            output_tokens=step_out_tok,
            cost_usd=step_cost
        )

