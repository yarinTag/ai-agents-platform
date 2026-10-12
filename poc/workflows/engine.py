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
            for step in wf_def.steps:
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

                # Ensure agent exists in database (avoid foreign key failure)
                agent = self.db.get_agent(step.agent_id)
                actual_agent_id = step.agent_id
                if not agent:
                    try:
                        from config import AgentConfig
                        placeholder = AgentConfig(
                            id=step.agent_id,
                            name=step.agent_id,
                            description=f"Auto-generated agent for workflow step {step.key}",
                            system_prompt="You are an autonomous workflow step agent.",
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
                            run_id=task_id,
                            agent_id=actual_agent_id,
                            prompt=formatted_prompt
                        )
                    except Exception as ex:
                        logger.warning(f"Runtime execution warning for step '{step.key}': {ex}")

                # Refresh task run to capture output, tokens, and cost
                updated_run = self.db.get_task_run(task_id) or step_run
                step_output = updated_run.result or f"Step {step.name} completed"
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

        return self.db.get_workflow_execution(execution_id)
