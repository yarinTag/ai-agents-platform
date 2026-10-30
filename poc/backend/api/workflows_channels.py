from fastapi import APIRouter, HTTPException, Depends, Request

import json

import logging

from ..dependencies import get_db_manager, DatabaseManager, WorkflowRevisionConflict

from ..security import get_authorized_scope

from workflows.parser import validate_workflow_definition

from .workflows_models import ChannelBindingDto, WorkflowResponse
from .workflows_mapping import _workflow_actor, _check_workflow_scope, _workflow_to_response

logger = logging.getLogger(__name__)
router = APIRouter()
_validated_definition = validate_workflow_definition

@router.post("/{workflow_id}/channel-binding", response_model=WorkflowResponse)
def bind_workflow_channel(
    workflow_id: str,
    req: ChannelBindingDto,
    request: Request,
    db: DatabaseManager = Depends(get_db_manager)
):
    """
    Bind a communication channel (Slack / Telegram) to a workflow.
    Configures incoming trigger permissions and outgoing execution reports.
    """
    import json
    wf = db.get_workflow(workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    scope = get_authorized_scope(request, db)
    _check_workflow_scope(wf, scope)

    try:
        def_dict = json.loads(wf.definition_json or "{}")
    except Exception:
        def_dict = {"id": wf.id, "name": wf.name, "steps": []}

    metadata = def_dict.get("metadata") or {}
    metadata["channel_binding"] = req.model_dump()
    def_dict["metadata"] = metadata

    new_def_json = json.dumps(def_dict, indent=2)
    try:
        updated = db.update_workflow(id=workflow_id, definition_json=new_def_json,
            **_workflow_actor(request), change_summary="Channel binding updated", expected_revision=wf.revision)
    except WorkflowRevisionConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _workflow_to_response(updated)

@router.delete("/{workflow_id}/channel-binding", response_model=WorkflowResponse)
def unbind_workflow_channel(
    workflow_id: str,
    request: Request,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Remove communication channel binding from a workflow."""
    import json
    wf = db.get_workflow(workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    scope = get_authorized_scope(request, db)
    _check_workflow_scope(wf, scope)

    try:
        def_dict = json.loads(wf.definition_json or "{}")
    except Exception:
        def_dict = {}

    if "metadata" in def_dict and "channel_binding" in def_dict["metadata"]:
        del def_dict["metadata"]["channel_binding"]

    new_def_json = json.dumps(def_dict, indent=2)
    try:
        updated = db.update_workflow(id=workflow_id, definition_json=new_def_json,
            **_workflow_actor(request), change_summary="Channel binding removed", expected_revision=wf.revision)
    except WorkflowRevisionConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _workflow_to_response(updated)

