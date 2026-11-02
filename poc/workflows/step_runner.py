"""Workflow step execution, policy gates and result capture."""
import uuid
import logging
import re
import json
from datetime import datetime
from typing import Dict, Optional, Any
from runtime.models import AgentRun, TaskStatus
from .parser import WorkflowStepDefinition
from .execution_models import WorkflowStepResult, MCPGovernanceViolationError

logger = logging.getLogger(__name__)


class WorkflowStepRunner:
    def __init__(self, database, runtime, skill_context=None, prompt_guard=None, output_sanitizer=None, approval_dispatch=None):
        self.db = database
        self.runtime = runtime
        self.skill_context = skill_context
        self.prompt_guard = prompt_guard
        self.output_sanitizer = output_sanitizer
        self.approval_dispatch = approval_dispatch

    def execute(
        self,
        step: WorkflowStepDefinition,
        execution_id: str,
        step_outputs: Dict[str, str],
        trigger_payload: Optional[Dict[str, Any]],
        dept_id: Optional[str],
        playground_workspace: Optional[str] = None
    ) -> WorkflowStepResult:
        """Execute a single workflow step with dynamic substitutions, skill injection, and agent reuse."""
        formatted_prompt = step.prompt_template
        if not playground_workspace:
            # Compatibility for the exact known authoring disclaimer; saved revisions stay intact.
            formatted_prompt = re.sub(re.escape('This is an inactive preview; do not claim execution.'),
                '', formatted_prompt, flags=re.IGNORECASE).strip()
        for prev_key, prev_out in step_outputs.items():
            formatted_prompt = formatted_prompt.replace(f"{{{{{prev_key}.output}}}}", prev_out or "")
            formatted_prompt = formatted_prompt.replace(f"${{{prev_key}.output}}", prev_out or "")

        if trigger_payload:
            for k, v in trigger_payload.items():
                formatted_prompt = formatted_prompt.replace(f"{{{{{k}}}}}", str(v))
                formatted_prompt = formatted_prompt.replace(f"${{{k}}}", str(v))

        # Step-level MCP Governance check & Tool filtering (Least Privilege & Hard Block)
        if dept_id and not playground_workspace and getattr(step, "mcp_servers", None):
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
        from .skill_inheritance import workflow_skill_ids
        execution_for_skills = self.db.get_workflow_execution(execution_id)
        workflow_for_skills = self.db.get_workflow(execution_for_skills.workflow_id)
        configured_skills = workflow_skill_ids(json.loads(workflow_for_skills.definition_json))
        # Server delivery uses predecessor text directly and performs no inference.
        if (step.params or {}).get('channel_action') is not None:
            configured_skills = []
        step_skills = []
        for sk in configured_skills:
            sk_rendered = str(sk)
            if trigger_payload:
                for k, v in trigger_payload.items():
                    sk_rendered = sk_rendered.replace(f"{{{{{k}}}}}", str(v))
                    sk_rendered = sk_rendered.replace(f"${{{k}}}", str(v))
            step_skills.append(sk_rendered)

        if step_skills and self.runtime is not None:
            if self.skill_context is None:
                raise RuntimeError("Required skill context provider is unavailable")
            skills_context = self.skill_context(step_skills, organization_id=workflow_for_skills.organization_id)
            if not skills_context:
                raise RuntimeError("Configured step skill context could not be resolved")
            formatted_prompt = f"{skills_context}\n\n[TASK INSTRUCTIONS]\n{formatted_prompt}"

        if self.prompt_guard:
            self.prompt_guard(formatted_prompt, step.key, execution_id)

        # Ensure agent exists in database (reuse or auto-provision)
        execution = self.db.get_workflow_execution(execution_id)
        workflow = self.db.get_workflow(execution.workflow_id)
        agent = self.db.get_agent(step.agent_id)
        if workflow.organization_id and agent and agent.organization_id != workflow.organization_id:
            raise ValueError("Workflow execution agent is outside its organization")
        actual_agent_id = step.agent_id
        if not agent and playground_workspace:
            raise ValueError(f"Playground requires a configured agent: {step.agent_id}")
        if not agent:
            try:
                from config import AgentConfig
                placeholder = AgentConfig(
                    id=step.agent_id,
                    name=step.name or step.agent_id,
                    description=f"Auto-generated agent for workflow step {step.key}",
                    system_prompt=f"You are an autonomous agent specialized in {step.name or step.key}.",
                    organization_id=workflow.organization_id, department_id=workflow.department_id,
                    model="default"
                )
                self.db.save_agent(placeholder)
                agent = placeholder
            except Exception as error:
                raise RuntimeError(f"Could not provision workflow agent '{step.agent_id}'") from error

        # Create task run for this step
        task_id = f"{'pg_task_' if playground_workspace else 'wf_task_'}{uuid.uuid4().hex[:12]}"
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
            retry_count=step.retry_count,
            organization_id=getattr(agent, "organization_id", None)
        )
        self.db.save_task_run(step_run)

        step_record_id = f"step_run_{uuid.uuid4().hex[:8]}"
        self.db.save_workflow_step_run({
            "id": step_record_id, "execution_id": execution_id,
            "step_key": step.key, "agent_id": actual_agent_id, "status": "RUNNING",
            "task_run_id": task_id, "input_data": formatted_prompt,
            "started_at": now_dt.isoformat(), "completed_at": None,
            "output_data": None, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0,
        })

        # A missing runtime, failure, pause or timeout is never a completed step.
        updated_run = step_run
        workspace = None
        try:
            if self.runtime is None:
                raise RuntimeError("Runtime capability is unavailable")
            from .channel_action import action_configuration, execute_channel_action
            from integrations.repo_workspace import workspace_configuration
            channel_action = action_configuration(step)
            workspace_config = workspace_configuration(step)
            if channel_action and playground_workspace:
                raise RuntimeError("Channel delivery actions cannot run in the tool-free Playground")
            if workspace_config and playground_workspace:
                raise RuntimeError("Repository workspaces cannot run in the tool-free Playground")
            if playground_workspace:
                self.runtime.start_playground_task(
                    agent_id=actual_agent_id, task_id=task_id,
                    prompt=formatted_prompt, workspace=playground_workspace,
                )
            else:
                if workspace_config:
                    # Sandboxed code steps get a container workspace instead of a connector scope.
                    from integrations.repo_workspace import open_workspace
                    workspace = open_workspace(self.db, task_id, execution_id, step, workspace_config)
                else:
                    from integrations.tool_scopes import prepare_scope
                    prepare_scope(self.db, task_id, execution_id, step)
                if channel_action:
                    execute_channel_action(self.db, step, step_run, step_outputs)
                else:
                    self.runtime.start_task(task_id=task_id, agent_id=actual_agent_id, prompt=formatted_prompt)
            import time
            deadline = time.monotonic() + min(step.timeout_seconds or 180, 300)
            approval_sent = False
            approval_deadline = None
            observed = {
                "completed", "failed", "cancelled", "waiting_input", "pending_approval",
                "waiting_for_children", "waiting_for_manager", "waiting_for_human",
            }
            while time.monotonic() < (approval_deadline or deadline):
                updated_run = self.db.get_task_run(task_id) or step_run
                state = getattr(updated_run.status, "value", updated_run.status)
                normalized = str(state).lower()
                if normalized in {"waiting_input", "pending_approval"}:
                    if playground_workspace:
                        self.runtime.cancel_run(task_id)
                        raise RuntimeError("Playground requires additional input; start a new run with that input")
                    if self.approval_dispatch:
                        if not approval_sent:
                            approval_sent = True
                            approval_deadline = time.monotonic() + 1800
                            try:
                                self.approval_dispatch(task_id, execution_id)
                            except Exception:
                                logger.warning("Optional approval delivery failed for %s", task_id)
                        time.sleep(1.0)
                        continue
                if normalized in observed:
                    break
                time.sleep(1.0)
            else:
                if hasattr(self.runtime, "cancel_run"):
                    self.runtime.cancel_run(task_id)
                raise TimeoutError(f"Workflow step '{step.key}' exceeded its runtime timeout")
            if workspace is not None and workspace["mode"] == "write":
                finished = self.db.get_task_run(task_id) or updated_run
                if str(getattr(finished.status, "value", finished.status)).lower() == "completed":
                    # The backend, not the model, publishes: new branch + draft PR, never a merge.
                    from integrations.repo_workspace import publish_workspace
                    receipt = publish_workspace(self.db, step, workspace, finished.result)
                    if step.params.get('required_outcome') == 'pull_request' and (
                            not receipt.get('changed') or not receipt.get('pull_request_url')):
                        raise RuntimeError('This step requires a created pull request, but no PR receipt was returned.')
                    note = (f"Draft pull request for human review: {receipt['pull_request_url']}"
                            if receipt["changed"] else "No file changes; no pull request was opened.")
                    finished.result = f"{finished.result or ''}\n\n[REPOSITORY RESULT]\n{note}"
                    self.db.save_task_run(finished)
                    updated_run = finished
        except Exception as error:
            updated_run = self.db.get_task_run(task_id) or step_run
            updated_run.status = TaskStatus.FAILED
            updated_run.error = str(error)
            updated_run.ended_at = datetime.now()
            self.db.save_task_run(updated_run)
            logger.warning("Workflow step %s did not complete: %s", step.key, error)
        finally:
            if workspace is not None:
                from integrations.repo_workspace import close_workspace
                try:
                    close_workspace(self.db, workspace)
                except Exception:
                    logger.warning("Repository sandbox cleanup failed for %s", task_id)

        step_status = str(getattr(updated_run.status, "value", updated_run.status)).upper()
        # Optional Maker-Checker review
        reviewer_id = step.params.get("reviewerAgentId") if getattr(step, "params", None) else None
        if reviewer_id and self.runtime and not playground_workspace and step_status == "COMPLETED":
            try:
                reviewer_agent = self.db.get_agent(reviewer_id)
                if reviewer_agent:
                    if workflow.organization_id and reviewer_agent.organization_id != workflow.organization_id:
                        raise ValueError("Workflow reviewer is outside its organization")
                    review_task_id = f"review_{uuid.uuid4().hex[:10]}"
                    updated_run = self.db.get_task_run(task_id) or step_run
                    rev_prompt = (
                        f"Review deliverable from {actual_agent_id} for step '{step.name}'.\n"
                        f"Acceptance criteria: {step.acceptance_criteria or 'Ensure high quality'}\n"
                        f"Deliverable:\n{updated_run.result or 'No output'}"
                    )
                    self.db.save_task_run(AgentRun(
                        run_id=review_task_id, agent_id=reviewer_id, project_id=None,
                        prompt=rev_prompt, status=TaskStatus.QUEUED, created_at=datetime.now(),
                        parent_task_id=task_id, root_task_id=task_id,
                        organization_id=getattr(reviewer_agent, "organization_id", None),
                    ))
                    self.runtime.start_task(task_id=review_task_id, agent_id=reviewer_id, prompt=rev_prompt)
            except Exception as r_err:
                logger.warning(f"Maker-checker review note for step '{step.key}': {r_err}")

        # Refresh task run to capture output, tokens, and cost
        step_output = updated_run.result or updated_run.error or ""
        if self.output_sanitizer:
            try:
                step_output = self.output_sanitizer(step.key, step_output)
            except Exception:
                step_output = "[SANITIZED_BY_SECURITY_FIREWALL: Potential indirect prompt injection neutralized]"
        step_in_tok = getattr(updated_run, "input_tokens", 0) or 0
        step_out_tok = getattr(updated_run, "output_tokens", 0) or 0
        step_cost = getattr(updated_run, "cost_usd", 0.0) or 0.0

        now_iso = datetime.now().isoformat()
        self.db.save_workflow_step_run({
            "id": step_record_id, "execution_id": execution_id,
            "step_key": step.key, "agent_id": actual_agent_id, "status": step_status,
            "task_run_id": task_id, "input_data": formatted_prompt,
            "output_data": step_output, "error_message": updated_run.error, "input_tokens": step_in_tok,
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

