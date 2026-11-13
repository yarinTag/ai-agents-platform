"""
Workflow Execution Engine:
Compiles declarative workflows into DAG task runs, enforces department budgets
(HARD_STOP with additional budget request on API keys), manages execution state,
coordinates sandboxes, supports parallel multi-agent stages, step-level skills,
maker-checker reviews, and captures run evaluations.
"""

import uuid
import json
import hashlib
import logging
import concurrent.futures
from datetime import datetime
from typing import Dict, List, Optional, Any

from storage.records import WorkflowExecution
from .ports import WorkflowStore, WorkflowNotifications
from runtime.protocol import RuntimeAdapter
from .parser import WorkflowParser, WorkflowDefinition, WorkflowStepDefinition
from .sandbox import SandboxManager

from .execution_models import BudgetExceededError, MCPGovernanceViolationError, UnauthorizedUserDepartmentError, WorkflowStepResult
from .conditions import evaluate_condition_rule, evaluate_trigger_conditions
from .step_runner import WorkflowStepRunner
from .stages import group_steps_into_stages
from .agent_scope import require_agent_scope, require_workflow_actor

logger = logging.getLogger(__name__)


def compute_execution_hash(workflow_id: str, payload: Any, revision: Optional[int] = None) -> str:
    """Stable namespace includes the saved revision and playground identity."""
    payload_text = json.dumps(payload, sort_keys=True) if payload else ""
    namespace = f"{workflow_id}:v{revision}" if revision is not None else workflow_id
    return hashlib.sha256(f"{namespace}:{payload_text}".encode("utf-8")).hexdigest()[:16]


class WorkflowEngine:
    """
    Core engine managing the lifecycle and execution of multi-agent workflows.
    Reuses existing DatabaseManager, OrchestrationEngine, and RuntimeAdapter.
    Supports parallel multi-agent stage execution, step-level skills, and maker-checker loops.
    """

    def __init__(
        self,
        db_manager: WorkflowStore,
        runtime_adapter: Optional[RuntimeAdapter] = None,
        orchestration_engine: Any = None,
        sandbox_manager: Optional[SandboxManager] = None,
        notifier: Optional[WorkflowNotifications] = None,
        skill_context=None,
        prompt_guard=None,
        output_sanitizer=None,
        approval_dispatch=None,
    ):
        self.db = db_manager
        self.notifier = notifier
        self.runtime = runtime_adapter
        self._step_runner = WorkflowStepRunner(db_manager, runtime_adapter, skill_context, prompt_guard, output_sanitizer, approval_dispatch)
        self.orchestration = orchestration_engine
        self.sandbox_manager = sandbox_manager or SandboxManager()

    def execute_workflow(
        self,
        workflow_id: str,
        trigger_type: str = "MANUAL",
        trigger_payload: Optional[Dict[str, Any]] = None,
        source_workspace: Optional[str] = None,
        runtime_provider: Optional[str] = None,
        user_context: Optional[Dict[str, Any]] = None,
        execution_id: Optional[str] = None,
        payload_hash: Optional[str] = None,
        playground: bool = False,
        channel_lease: str | None = None,
        dag_approval_id: str | None = None,
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

        if playground:
            if not self.runtime or not getattr(self.runtime.get_capabilities(), "supports_playground", False):
                raise ValueError("The configured runtime does not support tool-free playground execution")
            trigger_type = "PLAYGROUND"

        checkpoint = None
        if dag_approval_id:
            from storage.dag_approvals import claim_resume
            checkpoint = claim_resume(self.db, dag_approval_id, workflow.id, workflow.revision)
            if checkpoint is None:
                raise ValueError("DAG continuation is no longer eligible or already claimed.")
            execution_id = checkpoint["execution_id"]
            user_context = checkpoint["user_context"]
            trigger_payload = checkpoint["trigger_payload"]
            trigger_type = self.db.get_workflow_execution(execution_id).trigger_type
        elif trigger_type == "CHANNEL":
            from .channel_trigger_dispatch import admit_dispatch
            admitted = admit_dispatch(self.db, execution_id, workflow, channel_lease)
            if admitted is None:
                raise ValueError("Channel execution is no longer eligible or already claimed.")
            trigger_payload, user_context = admitted
        elif execution_id:
            queued = self.db.get_workflow_execution(execution_id)
            if queued and queued.trigger_type == "CHANNEL":
                raise ValueError("Channel execution requires verified trigger admission.")
            if queued and queued.status == "WAITING_APPROVAL":
                raise ValueError("Waiting execution requires an approved continuation.")
            if queued:
                with self.db._get_connection() as conn:
                    had_barrier = conn.execute(
                        "SELECT 1 FROM workflow_dag_approvals WHERE execution_id=? LIMIT 1", (execution_id,),
                    ).fetchone()
                if had_barrier:
                    raise ValueError("DAG checkpoint requires an approved continuation.")

        # 1. Budget and Department Access Authorization pre-check
        require_workflow_actor(workflow, user_context, self.db)
        dept_id = workflow.department_id
        if dept_id:
            budget_status = self.db.check_department_budget(dept_id)
            if not budget_status.get("allowed", False):
                raise BudgetExceededError(
                    department_id=dept_id,
                    message=budget_status.get("message", "Department budget limit exceeded. Additional budget required."),
                    current_spend=budget_status.get("current_spend_usd", 0.0),
                    budget=budget_status.get("monthly_budget_usd", 0.0)
                )

        if not execution_id:
            execution_id = f"{'pg_exec_' if playground else 'wf_exec_'}{uuid.uuid4().hex[:12]}"

        if not payload_hash:
            payload_hash = compute_execution_hash(f"playground:{workflow_id}" if playground else workflow_id, trigger_payload, revision=workflow.revision)

        # 2. Setup sandbox session
        sandbox = self.sandbox_manager.create_sandbox(
            execution_id=execution_id,
            source_workspace=None if playground else source_workspace,
            force_type="EPHEMERAL_DIR" if playground else None
        )

        # 3. Create or update execution record in database
        payload_str = json.dumps(trigger_payload) if trigger_payload is not None else None
        existing_exec = self.db.get_workflow_execution(execution_id)
        if existing_exec:
            wf_exec = self.db.update_workflow_execution(
                execution_id=execution_id,
                status="RUNNING",
                started_at=datetime.now().isoformat(),
                sandbox_path=sandbox.path,
                payload_hash=payload_hash
            )
        else:
            wf_exec = self.db.create_workflow_execution(
                execution_id=execution_id,
                workflow_id=workflow_id,
                trigger_type=trigger_type,
                trigger_payload=payload_str,
                department_id=dept_id,
                sandbox_path=sandbox.path,
                payload_hash=payload_hash,
                status="RUNNING"
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

        try:
            from .backend_policy import preflight_backends
            preflight_backends(wf_def, playground=playground, db=self.db, workflow=workflow)
            from .dag_approval_config import dag_approval_policy
            if any(dag_approval_policy(step) for step in wf_def.steps) and (
                not dept_id or not (user_context or {}).get("sub") or source_workspace
            ):
                raise ValueError("DAG approvals require a personal initiator, department and independent step workspaces.")
            for step in wf_def.steps:
                require_agent_scope(self.db.get_agent(step.agent_id), workflow, user_context, db=self.db)
                reviewer_id = (getattr(step, "params", None) or {}).get("reviewerAgentId")
                if reviewer_id and not playground:
                    require_agent_scope(self.db.get_agent(reviewer_id), workflow, user_context, db=self.db)
        except Exception as error:
            self.db.update_workflow_execution(
                execution_id, status="FAILED", error_message=str(error),
                completed_at=datetime.now().isoformat(),
            )
            sandbox.cleanup()
            raise

        # Tool-free exercises never connect to declared MCP servers.
        if not playground and checkpoint is None:
            from integrations.tool_scopes import prepare_execution_context
            try:
                prepare_execution_context(self.db, wf_exec, workflow, wf_def, user_context)
            except ValueError as error:
                self.db.update_workflow_execution(execution_id, status="FAILED", error_message=str(error),
                    completed_at=datetime.now().isoformat())
                self._notify_lifecycle(workflow_id, execution_id, trigger_type, 'FAILED', {},
                                       error=str(error), event='complete')
                sandbox.cleanup()
                raise MCPGovernanceViolationError(department_id=dept_id, connector_id="workflow_scope", reason=str(error)) from error

        # Live executions still require department connector grants.
        # 4b. Pre-flight MCP Governance check
        if dept_id and not playground:
            all_mcp_servers = set(getattr(wf_def, "mcp_servers", []) or [])
            for s in wf_def.steps:
                for sm in (getattr(s, "mcp_servers", []) or []):
                    all_mcp_servers.add(sm)

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
                    self._notify_lifecycle(workflow_id, execution_id, trigger_type, 'FAILED', {},
                                           error=err_msg, event='complete')
                    raise MCPGovernanceViolationError(
                        department_id=dept_id,
                        connector_id=conn_id,
                        reason=err_msg
                    )

        # 5. Execute steps in DAG dependency stages (multi-agent parallel execution)
        step_outputs: Dict[str, str] = checkpoint["outputs"] if checkpoint else {}
        total_input_tokens = checkpoint["input_tokens"] if checkpoint else 0
        total_output_tokens = checkpoint["output_tokens"] if checkpoint else 0
        total_cost_usd = checkpoint["cost_usd"] if checkpoint else 0.0
        final_status = "COMPLETED"
        failure_error: Optional[str] = None

        if not playground and checkpoint is None:
            self._notify_lifecycle(workflow_id, execution_id, trigger_type, 'RUNNING', {}, event='start')

        try:
            from .stages import isolate_approval_barriers
            stages = isolate_approval_barriers(self._group_steps_into_stages(wf_def.steps))
            for stage in stages:
                stage = [step for step in stage if step.key not in step_outputs]
                if not stage:
                    continue
                # Check mid-run budget cap before launching next stage
                if dept_id:
                    from storage.hosted_budget import execution_settled
                    # Hosted requests already appear in department spend before workflow rollup.
                    incremental = max(0.0, total_cost_usd - execution_settled(self.db, execution_id))
                    check = self.db.check_department_budget(dept_id, requested_cost=incremental)
                    if not check.get("allowed", False):
                        final_status = "FAILED"
                        failure_error = f"Mid-run budget exceeded for department {dept_id}. Additional budget required."
                        break

                approval = dag_approval_policy(stage[0]) if len(stage) == 1 else None
                if approval:
                    from storage.dag_approvals import suspend
                    suspend(self.db, execution_id=execution_id, step_key=stage[0].key,
                            revision=workflow.revision, initiator_id=user_context["sub"],
                            policy=approval.model_dump(), checkpoint={
                                "outputs": step_outputs, "input_tokens": total_input_tokens,
                                "output_tokens": total_output_tokens, "cost_usd": total_cost_usd,
                                "trigger_payload": trigger_payload,
                            })
                    return self.db.get_workflow_execution(execution_id)
                if len(stage) == 1:
                    # Sequential step execution
                    res = self._execute_single_step(
                        step=stage[0],
                        execution_id=execution_id,
                        step_outputs=step_outputs,
                        trigger_payload=trigger_payload,
                        dept_id=dept_id,
                        playground_workspace=sandbox.path if playground else None
                    )
                    step_outputs[res.step_key] = res.output or ""
                    total_input_tokens += res.input_tokens
                    total_output_tokens += res.output_tokens
                    total_cost_usd += res.cost_usd
                    if not playground:
                        self._notify_lifecycle(workflow_id, execution_id, trigger_type, res.status,
                                               step_outputs, error=res.error, event=f'step:{res.step_key}')
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
                                dept_id,
                                sandbox.path if playground else None
                            ): s for s in stage
                        }
                        for fut in concurrent.futures.as_completed(future_map):
                            res = fut.result()
                            step_outputs[res.step_key] = res.output or ""
                            total_input_tokens += res.input_tokens
                            total_output_tokens += res.output_tokens
                            total_cost_usd += res.cost_usd
                            if not playground:
                                self._notify_lifecycle(workflow_id, execution_id, trigger_type, res.status,
                                                       step_outputs, error=res.error, event=f'step:{res.step_key}')
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
            sandbox.cleanup()

        # Update final execution record
        self.db.update_workflow_execution(
            execution_id=execution_id,
            status=final_status,
            total_input_tokens=total_input_tokens,
            total_output_tokens=total_output_tokens,
            total_cost_usd=total_cost_usd,
            completed_at=datetime.now().isoformat() if final_status in {"COMPLETED", "FAILED", "CANCELLED"} else None,
            error_message=failure_error
        )

        # Optional delivery must not change the authoritative execution result.
        if self.notifier and not playground and final_status in {"COMPLETED", "FAILED", "CANCELLED"}:
            try:
                self.notifier.notify(
                    workflow_id, execution_id, trigger_type, final_status, step_outputs,
                    total_input_tokens, total_output_tokens, total_cost_usd, failure_error,
                )
            except Exception:
                logger.warning("Workflow notification adapter failed for %s", execution_id)

        return self.db.get_workflow_execution(execution_id)

    def _notify_lifecycle(self, workflow_id, execution_id, trigger_type, status, outputs, error=None, *, event):
        if not self.notifier or not hasattr(self.notifier, 'notify_event'):
            return
        try:
            self.notifier.notify_event(workflow_id, execution_id, trigger_type, status, outputs, error=error, event=event)
        except Exception:
            logger.warning('Workflow lifecycle notification failed for %s', execution_id)

    def _execute_single_step(self, step, execution_id, step_outputs, trigger_payload, dept_id, playground_workspace=None):
        self._step_runner.runtime = self.runtime
        return self._step_runner.execute(step, execution_id, step_outputs, trigger_payload, dept_id, playground_workspace)

    def _group_steps_into_stages(self, steps):
        return group_steps_into_stages(steps)

    def _topological_sort_steps(self, steps: List[Any]) -> List[Any]:
        """Flatten stages into ordered steps."""
        stages = self._group_steps_into_stages(steps)
        res = []
        for stage in stages:
            res.extend(stage)
        return res
