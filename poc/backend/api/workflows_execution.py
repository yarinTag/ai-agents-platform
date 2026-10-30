"""Production workflow dispatch, deduplication and webhook entry points."""
import asyncio
import json
import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Request, Query, status
from ..dependencies import get_db_manager, get_workflow_engine, get_task_queue_publisher, DatabaseManager
from ..security import get_authorized_scope
from workflows.engine import (
    WorkflowEngine, BudgetExceededError, MCPGovernanceViolationError,
    UnauthorizedUserDepartmentError, compute_execution_hash,
)
from .workflows_models import WorkflowExecutionResponse
from .workflows_mapping import _check_workflow_scope, _execution_to_response

router = APIRouter()


async def _queue_execution(database, workflow, payload, trigger_type, payload_hash, user_context=None):
    publisher = get_task_queue_publisher()
    execution_id = f"wf_exec_{uuid.uuid4().hex[:12]}"
    record = database.create_workflow_execution(
        execution_id=execution_id, workflow_id=workflow.id, trigger_type=trigger_type,
        trigger_payload=json.dumps(payload) if payload is not None else None,
        department_id=workflow.department_id, payload_hash=payload_hash, status="QUEUED",
    )
    try:
        await publisher.publish_workflow_execution(
            workflow_id=workflow.id, execution_id=execution_id,
            trigger_type=trigger_type, trigger_payload=payload,
            department_id=workflow.department_id, org_id=workflow.organization_id,
            user_context=user_context, priority=5,
        )
    except Exception as error:
        database.update_workflow_execution(
            execution_id, status="FAILED", error_message="Queue dispatch unavailable",
            completed_at=datetime.now().isoformat(),
        )
        raise HTTPException(status_code=503, detail="Queue dispatch unavailable") from error
    return _execution_to_response(record, message="Workflow execution queued for processing.")


@router.post("/{workflow_id}/execute", response_model=WorkflowExecutionResponse)
async def execute_workflow(
    workflow_id: str, request: Request, payload: Optional[Dict[str, Any]] = None,
    use_queue: bool = Query(True), force_rerun: bool = Query(False),
    engine: WorkflowEngine = Depends(get_workflow_engine),
):
    """Execute the saved revision, optionally reusing a matching active/completed run."""
    workflow = engine.db.get_workflow(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    _check_workflow_scope(workflow, get_authorized_scope(request, engine.db))
    payload_hash = compute_execution_hash(workflow_id, payload, revision=workflow.revision)
    if not force_rerun:
        match = engine.db.find_matching_workflow_execution(workflow_id, payload_hash)
        if match and match.status in {"QUEUED", "RUNNING", "COMPLETED"}:
            return _execution_to_response(match, is_deduplicated=True,
                message="Identical saved workflow execution reused.")
    user_context = getattr(request.state, "user", None)
    if use_queue:
        return await _queue_execution(engine.db, workflow, payload, "MANUAL", payload_hash, user_context)
    try:
        execution = await asyncio.to_thread(
            engine.execute_workflow, workflow_id=workflow_id, trigger_type="MANUAL",
            trigger_payload=payload, user_context=user_context, payload_hash=payload_hash,
        )
        return _execution_to_response(execution, message="Workflow execution finished synchronously.")
    except (UnauthorizedUserDepartmentError, MCPGovernanceViolationError) as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except BudgetExceededError as error:
        raise HTTPException(status_code=402, detail=str(error)) from error


@router.post("/webhook/{webhook_token}", response_model=WorkflowExecutionResponse,
             status_code=status.HTTP_202_ACCEPTED)
async def trigger_webhook(
    webhook_token: str, request: Request,
    db: DatabaseManager = Depends(get_db_manager),
    engine: WorkflowEngine = Depends(get_workflow_engine),
):
    workflow = db.get_workflow_by_webhook_token(webhook_token)
    if not workflow:
        raise HTTPException(status_code=404, detail="Invalid or inactive webhook token")
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    payload_hash = compute_execution_hash(workflow.id, payload, revision=workflow.revision)
    match = db.find_matching_workflow_execution(workflow.id, payload_hash)
    if match and match.status in {"QUEUED", "RUNNING", "COMPLETED"}:
        return _execution_to_response(match, is_deduplicated=True,
            message="Duplicate webhook trigger reused an active/completed execution.")
    return await _queue_execution(db, workflow, payload, "WEBHOOK", payload_hash)
