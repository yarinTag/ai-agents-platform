from fastapi import APIRouter, HTTPException, Depends, status, BackgroundTasks, Request

from typing import Dict, Any

import uuid

import json

import logging

from ..dependencies import get_workflow_engine

from workflows.parser import WorkflowParser

from workflows.engine import WorkflowEngine, compute_execution_hash

from ..security import get_authorized_scope

from workflows.parser import validate_workflow_definition

from .workflows_models import WorkflowExecutionResponse
from .workflows_mapping import _check_workflow_scope

logger = logging.getLogger(__name__)
router = APIRouter()
_validated_definition = validate_workflow_definition

@router.post("/{workflow_id}/playground", response_model=WorkflowExecutionResponse,
             status_code=status.HTTP_202_ACCEPTED)
def execute_playground(
    workflow_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    payload: Dict[str, Any],
    engine: WorkflowEngine = Depends(get_workflow_engine)
):
    """Fresh tool-free inference on the existing DAG; no external notifications or cache reuse."""
    wf = engine.db.get_workflow(workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    scope = get_authorized_scope(request, engine.db)
    _check_workflow_scope(wf, scope)
    if not engine.runtime or not getattr(engine.runtime.get_capabilities(), "supports_playground", False):
        raise HTTPException(status_code=409, detail="Configured runtime does not support tool-free playground execution")
    try:
        try:
            definition = WorkflowParser.from_json(wf.definition_json)
        except Exception:
            definition = WorkflowParser.from_yaml(wf.definition_json)
        for step in definition.steps:
            agent = engine.db.get_agent(step.agent_id)
            if not agent:
                raise ValueError(f"Configure agent '{step.agent_id}' before running the playground")
            if scope["org_id"] and getattr(agent, "organization_id", None) != scope["org_id"]:
                raise HTTPException(status_code=403, detail="Playground agent is outside your organization")
            _check_workflow_scope(agent, scope)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    execution_id = f"pg_exec_{uuid.uuid4().hex[:12]}"
    # Namespace hashes so production deduplication never reuses playground outputs.
    payload_hash = compute_execution_hash(f"playground:{workflow_id}", payload, revision=wf.revision)
    record = engine.db.create_workflow_execution(
        execution_id=execution_id, workflow_id=workflow_id, trigger_type="PLAYGROUND",
        trigger_payload=json.dumps(payload), department_id=wf.department_id,
        payload_hash=payload_hash, status="QUEUED"
    )

    def run():
        try:
            engine.execute_workflow(
                workflow_id=workflow_id, trigger_payload=payload, playground=True,
                execution_id=execution_id, payload_hash=payload_hash,
                user_context=getattr(request.state, "user", None)
            )
        except Exception as exc:
            from datetime import datetime
            logger.exception("Playground execution failed: %s", execution_id)
            engine.db.update_workflow_execution(
                execution_id, status="FAILED", error_message=str(exc),
                completed_at=datetime.now().isoformat()
            )

    background_tasks.add_task(run)
    return WorkflowExecutionResponse(
        id=record.id, workflow_id=workflow_id, trigger_type="PLAYGROUND",
        trigger_payload=json.dumps(payload), status="QUEUED", department_id=wf.department_id,
        payload_hash=payload_hash, created_at=record.created_at,
        message="Tool-free playground run started. External tools and notifications are disabled."
    )

