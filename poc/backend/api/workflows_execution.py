"""Workflows: execution ownership."""

from fastapi import HTTPException, Depends, status, Request
from typing import Optional, Dict, Any
import uuid
from ..dependencies import get_db_manager, get_workflow_engine, DatabaseManager
from workflows.engine import WorkflowEngine, BudgetExceededError, MCPGovernanceViolationError, UnauthorizedUserDepartmentError
from ..security import get_authorized_scope
from .workflows_models import EvaluationRequest, WorkflowExecutionResponse
from .workflows_mapping import _check_workflow_scope, _execution_to_response
from fastapi import APIRouter

router = APIRouter()


@router.post("/{workflow_id}/execute", response_model=WorkflowExecutionResponse)
def execute_workflow(
    workflow_id: str,
    request: Request,
    payload: Optional[Dict[str, Any]] = None,
    engine: WorkflowEngine = Depends(get_workflow_engine)
):
    """Manually trigger a workflow execution with scope enforcement."""
    wf = engine.db.get_workflow(workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    scope = get_authorized_scope(request, engine.db)
    _check_workflow_scope(wf, scope)

    try:
        user_ctx = getattr(request.state, "user", None)
        execution = engine.execute_workflow(
            workflow_id=workflow_id,
            trigger_type="MANUAL",
            trigger_payload=payload,
            user_context=user_ctx
        )
        return _execution_to_response(execution)
    except UnauthorizedUserDepartmentError as uude:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Department Access Denied: {str(uude)}"
        )
    except MCPGovernanceViolationError as mcp_err:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"MCP Governance Violation: {str(mcp_err)}"
        )
    except BudgetExceededError as be:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Budget limit reached for department '{be.department_id}': {str(be)}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@router.post("/webhook/{webhook_token}", response_model=WorkflowExecutionResponse, status_code=status.HTTP_202_ACCEPTED)
async def trigger_webhook(
    webhook_token: str,
    request: Request,
    db: DatabaseManager = Depends(get_db_manager),
    engine: WorkflowEngine = Depends(get_workflow_engine)
):
    """
    Incoming webhook endpoint for a specific workflow.
    Validates token, extracts JSON body payload, and launches workflow execution.
    """
    wf = db.get_workflow_by_webhook_token(webhook_token)
    if not wf:
        raise HTTPException(status_code=404, detail="Invalid or inactive webhook token")

    body_data = {}
    try:
        body_data = await request.json()
    except Exception:
        pass

    try:
        execution = engine.execute_workflow(
            workflow_id=wf.id,
            trigger_type="WEBHOOK",
            trigger_payload=body_data
        )
        return _execution_to_response(execution)
    except MCPGovernanceViolationError as mcp_err:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"MCP Governance Violation: {str(mcp_err)}"
        )
    except BudgetExceededError as be:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Department budget exceeded: {str(be)}"
        )



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


@router.get("/executions/{execution_id}", response_model=WorkflowExecutionResponse)
def get_execution_status(
    execution_id: str,
    request: Request,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Get full status and token/cost metrics of a workflow execution."""
    exec_record = _get_scoped_execution(execution_id, request, db)

    return _execution_to_response(exec_record)



@router.post("/executions/{execution_id}/evaluate", status_code=status.HTTP_201_CREATED)
def evaluate_execution(
    execution_id: str,
    req: EvaluationRequest,
    request: Request,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Submit human review, rating, and lessons learned for self-improvement."""
    exec_record = _get_scoped_execution(execution_id, request, db)

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

