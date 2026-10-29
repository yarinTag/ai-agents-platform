"""
Workflow Execution Engine:
Compiles declarative workflows into DAG task runs, enforces department budgets
(HARD_STOP with additional budget request on API keys), manages execution state,
coordinates sandboxes, supports parallel multi-agent stages, step-level skills,
maker-checker reviews, and captures run evaluations.
"""

import uuid
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

logger = logging.getLogger(__name__)


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
    ):
        self.db = db_manager
        self.notifier = notifier
        self.runtime = runtime_adapter
        self._step_runner = WorkflowStepRunner(db_manager, runtime_adapter, skill_context)
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
            if not budget_status.get("allowed", False):
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

        # 4b. Pre-flight MCP Governance check
        if dept_id:
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
                    raise MCPGovernanceViolationError(
                        department_id=dept_id,
                        connector_id=conn_id,
                        reason=err_msg
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
                    if not check.get("allowed", False):
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
        if self.notifier:
            try:
                self.notifier.notify(
                    workflow_id, execution_id, trigger_type, final_status, step_outputs,
                    total_input_tokens, total_output_tokens, total_cost_usd, failure_error,
                )
            except Exception:
                logger.warning("Workflow notification adapter failed for %s", execution_id)

        return self.db.get_workflow_execution(execution_id)

    def _execute_single_step(self, step, execution_id, step_outputs, trigger_payload, dept_id):
        self._step_runner.runtime = self.runtime
        return self._step_runner.execute(step, execution_id, step_outputs, trigger_payload, dept_id)

    def _group_steps_into_stages(self, steps):
        return group_steps_into_stages(steps)

    def _topological_sort_steps(self, steps: List[Any]) -> List[Any]:
        """Flatten stages into ordered steps."""
        stages = self._group_steps_into_stages(steps)
        res = []
        for stage in stages:
            res.extend(stage)
        return res
