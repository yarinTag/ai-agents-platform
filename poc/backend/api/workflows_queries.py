from fastapi import APIRouter, HTTPException, Depends, status, Request, Query

from typing import List, Optional

import uuid

import logging

from ..dependencies import get_db_manager, DatabaseManager

from ..security import get_authorized_scope

from workflows.parser import validate_workflow_definition

from .workflows_models import WorkflowExecutionResponse, EvaluationRequest
from .workflows_mapping import _check_workflow_scope, _execution_to_response

logger = logging.getLogger(__name__)
router = APIRouter()
_validated_definition = validate_workflow_definition


def _with_notification_status(db, record, **overrides):
    from integrations.tool_scopes import execution_context
    from .workflow_costs import execution_costs
    context = execution_context(db, record.id) or {}
    summary, steps = execution_costs(db, record.id)
    for step in overrides.get('step_runs', []):
        step.update(steps.get(step['id'], {}))
    response = _execution_to_response(record, notification_error=context.get('notification_error'), **overrides)
    response.cost_summary = summary
    return response

def _get_scoped_execution(execution_id: str, request: Request, db: DatabaseManager):
    """Authorize both the current workflow owner and execution department."""
    execution = db.get_workflow_execution(execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    workflow = db.get_workflow(execution.workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Execution not found")
    scope = get_authorized_scope(request, db)
    org_id = scope.get("org_id")
    if org_id:
        if getattr(workflow, "organization_id", None) != org_id:
            raise HTTPException(status_code=404, detail="Execution not found")
        if not scope["is_org_admin"]:
            allowed_departments = scope.get("department_ids") or []
            required_departments = {
                department_id for department_id in
                (workflow.department_id, execution.department_id) if department_id
            }
            if not required_departments.issubset(set(allowed_departments)):
                raise HTTPException(status_code=403, detail="Not authorized to access execution in this department")
    _check_workflow_scope(workflow, scope)
    return execution

@router.get("/executions", response_model=List[WorkflowExecutionResponse])
def list_executions(
    request: Request,
    workflow_id: Optional[str] = Query(None),
    department_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: DatabaseManager = Depends(get_db_manager)
):
    """List recent workflow executions with filtering."""
    records = db.list_workflow_executions(
        workflow_id=workflow_id,
        department_id=department_id,
        status=status,
        limit=limit
    )
    visible = []
    for record in records:
        wf = db.get_workflow(record.workflow_id)
        if not wf:
            continue
        try:
            _get_scoped_execution(record.id, request, db)
        except HTTPException:
            continue
        visible.append(record)
    return [_with_notification_status(db, record) for record in visible]

@router.get("/executions/{execution_id}", response_model=WorkflowExecutionResponse)
def get_execution_status(
    execution_id: str,
    request: Request,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Get full status and token/cost metrics of a workflow execution."""
    exec_record = _get_scoped_execution(execution_id, request, db)
    if not exec_record:
        raise HTTPException(status_code=404, detail="Execution not found")

    wf = db.get_workflow(exec_record.workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    _check_workflow_scope(wf, get_authorized_scope(request, db))
    with db._get_connection() as conn:
        step_runs = [dict(row) for row in conn.execute(
            "SELECT * FROM workflow_step_runs WHERE execution_id = ? ORDER BY started_at, step_key",
            (execution_id,)
        ).fetchall()]
    for step in step_runs:
        task = db.get_task_run(step["task_run_id"]) if step.get("task_run_id") else None
        from .workflow_pr_evidence import step_pr_evidence
        step["pr_evidence"] = step_pr_evidence(db, step, wf.organization_id)
        step["events"] = task.events[-500:] if task else []
        step["error"] = task.error if task else None
        step["task_status"] = task.status.value if task else None
    return _with_notification_status(db, exec_record, step_runs=step_runs)

@router.post("/executions/{execution_id}/evaluate", status_code=status.HTTP_201_CREATED)
def evaluate_execution(
    execution_id: str,
    req: EvaluationRequest,
    request: Request,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Submit human review, rating, and lessons learned for self-improvement."""
    exec_record = _get_scoped_execution(execution_id, request, db)
    if not exec_record:
        raise HTTPException(status_code=404, detail="Execution not found")

    eval_id = f"eval_{uuid.uuid4().hex[:10]}"
    db.save_run_evaluation(
        id=eval_id,
        execution_id=execution_id,
        workflow_id=exec_record.workflow_id,
        rating=req.rating,
        feedback_notes=req.feedback_notes,
        lessons_extracted=req.lessons_extracted
    )
    return {"status": "SUCCESS", "evaluation_id": eval_id}

