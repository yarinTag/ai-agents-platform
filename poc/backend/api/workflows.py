"""
Workflows and Webhooks API router.
Supports:
- CRUD for workflows (JSON / YAML formats)
- Workflow execution (manual trigger)
- Incoming Webhooks with webhook token lookup
- Execution inspection with full token usage and cost accounting
- Human evaluations and lessons learned
"""

from fastapi import APIRouter, HTTPException, Depends, status, BackgroundTasks, Header, Request
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
import uuid

from ..dependencies import get_db_manager, get_workflow_engine, DatabaseManager
from workflows.parser import WorkflowParser, WorkflowDefinition
from workflows.engine import WorkflowEngine, BudgetExceededError

router = APIRouter()


class WorkflowCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    description: Optional[str] = None
    department_id: Optional[str] = None
    definition_yaml: Optional[str] = None
    definition_json: Optional[str] = None
    cron_expression: Optional[str] = None
    webhook_enabled: bool = True


class WorkflowResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    department_id: Optional[str] = None
    definition_json: str
    definition_yaml: Optional[str] = None
    webhook_enabled: bool
    webhook_token: Optional[str] = None
    cron_expression: Optional[str] = None
    is_active: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class WorkflowExecutionResponse(BaseModel):
    id: str
    workflow_id: str
    trigger_type: str
    trigger_payload: Optional[str] = None
    status: str
    department_id: Optional[str] = None
    sandbox_path: Optional[str] = None
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None
    created_at: Optional[str] = None


class EvaluationRequest(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    feedback_notes: Optional[str] = None
    lessons_extracted: Optional[str] = None


@router.post("", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
def create_workflow(
    req: WorkflowCreateRequest,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Create a new workflow from YAML or JSON definition."""
    def_json = req.definition_json
    if not def_json and req.definition_yaml:
        try:
            def_json = WorkflowParser.yaml_to_json(req.definition_yaml)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid YAML definition: {e}")
    elif not def_json:
        raise HTTPException(status_code=400, detail="Either definition_yaml or definition_json is required")

    wf_id = f"wf_{uuid.uuid4().hex[:10]}"
    wf = db.create_workflow(
        id=wf_id,
        name=req.name,
        definition_json=def_json,
        department_id=req.department_id,
        description=req.description,
        cron_expression=req.cron_expression,
        webhook_enabled=req.webhook_enabled
    )

    yaml_repr = None
    try:
        yaml_repr = WorkflowParser.json_to_yaml(wf.definition_json)
    except Exception:
        pass

    return WorkflowResponse(
        id=wf.id,
        name=wf.name,
        description=wf.description,
        department_id=wf.department_id,
        definition_json=wf.definition_json,
        definition_yaml=yaml_repr,
        webhook_enabled=wf.webhook_enabled,
        webhook_token=wf.webhook_token,
        cron_expression=wf.cron_expression,
        is_active=wf.is_active,
        created_at=wf.created_at,
        updated_at=wf.updated_at
    )


@router.get("", response_model=List[WorkflowResponse])
@router.get("/", response_model=List[WorkflowResponse])
def list_workflows(
    department_id: Optional[str] = None,
    active_only: bool = False,
    db: DatabaseManager = Depends(get_db_manager)
):
    """List workflows."""
    workflows = db.list_workflows(department_id=department_id, active_only=active_only)
    resp = []
    for wf in workflows:
        y_repr = None
        try:
            y_repr = WorkflowParser.json_to_yaml(wf.definition_json)
        except Exception:
            pass
        resp.append(WorkflowResponse(
            id=wf.id,
            name=wf.name,
            description=wf.description,
            department_id=wf.department_id,
            definition_json=wf.definition_json,
            definition_yaml=y_repr,
            webhook_enabled=wf.webhook_enabled,
            webhook_token=wf.webhook_token,
            cron_expression=wf.cron_expression,
            is_active=wf.is_active,
            created_at=wf.created_at,
            updated_at=wf.updated_at
        ))
    return resp


@router.get("/{workflow_id}", response_model=WorkflowResponse)
def get_workflow(
    workflow_id: str,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Get workflow by ID."""
    wf = db.get_workflow(workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    y_repr = None
    try:
        y_repr = WorkflowParser.json_to_yaml(wf.definition_json)
    except Exception:
        pass
    return WorkflowResponse(
        id=wf.id,
        name=wf.name,
        description=wf.description,
        department_id=wf.department_id,
        definition_json=wf.definition_json,
        definition_yaml=y_repr,
        webhook_enabled=wf.webhook_enabled,
        webhook_token=wf.webhook_token,
        cron_expression=wf.cron_expression,
        is_active=wf.is_active,
        created_at=wf.created_at,
        updated_at=wf.updated_at
    )


@router.post("/{workflow_id}/execute", response_model=WorkflowExecutionResponse)
def execute_workflow(
    workflow_id: str,
    payload: Optional[Dict[str, Any]] = None,
    engine: WorkflowEngine = Depends(get_workflow_engine)
):
    """Manually trigger a workflow execution."""
    try:
        execution = engine.execute_workflow(
            workflow_id=workflow_id,
            trigger_type="MANUAL",
            trigger_payload=payload
        )
        return WorkflowExecutionResponse(
            id=execution.id,
            workflow_id=execution.workflow_id,
            trigger_type=execution.trigger_type,
            trigger_payload=execution.trigger_payload,
            status=execution.status,
            department_id=execution.department_id,
            sandbox_path=execution.sandbox_path,
            total_input_tokens=execution.total_input_tokens,
            total_output_tokens=execution.total_output_tokens,
            total_cost_usd=execution.total_cost_usd,
            started_at=execution.started_at,
            completed_at=execution.completed_at,
            error_message=execution.error_message,
            created_at=execution.created_at
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
        return WorkflowExecutionResponse(
            id=execution.id,
            workflow_id=execution.workflow_id,
            trigger_type=execution.trigger_type,
            trigger_payload=execution.trigger_payload,
            status=execution.status,
            department_id=execution.department_id,
            sandbox_path=execution.sandbox_path,
            total_input_tokens=execution.total_input_tokens,
            total_output_tokens=execution.total_output_tokens,
            total_cost_usd=execution.total_cost_usd,
            started_at=execution.started_at,
            completed_at=execution.completed_at,
            error_message=execution.error_message,
            created_at=execution.created_at
        )
    except BudgetExceededError as be:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Department budget exceeded: {str(be)}"
        )


@router.get("/executions/{execution_id}", response_model=WorkflowExecutionResponse)
def get_execution_status(
    execution_id: str,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Get full status and token/cost metrics of a workflow execution."""
    exec_record = db.get_workflow_execution(execution_id)
    if not exec_record:
        raise HTTPException(status_code=404, detail="Execution not found")

    return WorkflowExecutionResponse(
        id=exec_record.id,
        workflow_id=exec_record.workflow_id,
        trigger_type=exec_record.trigger_type,
        trigger_payload=exec_record.trigger_payload,
        status=exec_record.status,
        department_id=exec_record.department_id,
        sandbox_path=exec_record.sandbox_path,
        total_input_tokens=exec_record.total_input_tokens,
        total_output_tokens=exec_record.total_output_tokens,
        total_cost_usd=exec_record.total_cost_usd,
        started_at=exec_record.started_at,
        completed_at=exec_record.completed_at,
        error_message=exec_record.error_message,
        created_at=exec_record.created_at
    )


@router.post("/executions/{execution_id}/evaluate", status_code=status.HTTP_201_CREATED)
def evaluate_execution(
    execution_id: str,
    req: EvaluationRequest,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Submit human review, rating, and lessons learned for self-improvement."""
    exec_record = db.get_workflow_execution(execution_id)
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
