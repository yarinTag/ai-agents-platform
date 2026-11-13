"""Revisioned channel trigger configuration and side-effect-free preview."""
import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from storage.records import WorkflowRevisionConflict
from workflows.channel_trigger_rules import ChannelTriggerInput, TriggerRule, match_trigger
from ..dependencies import get_db_manager
from ..security.identity import load_actor
from ..security.resource_access import Resources

router = APIRouter(prefix="/{workflow_id}/channel-trigger")


class TriggerUpdate(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    expected_revision: Annotated[int, Field(ge=1)]
    rule: TriggerRule | None


class TriggerPreview(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    rule: TriggerRule
    event: ChannelTriggerInput


def _scope(db, request, workflow_id, level=1):
    actor = load_actor(request, db)
    workflow = Resources(actor).require("workflow", workflow_id, level)
    if not workflow.department_id:
        raise HTTPException(409, "Channel triggers require a department-scoped workflow.")
    return actor, workflow


def _eligible(db, workflow, binding_id=None):
    with db._get_connection() as conn:
        rows = conn.execute("""
            SELECT b.id, b.provider, b.connector_id, b.channel_id
            FROM channel_bindings b
            JOIN mcp_connectors c ON c.id = b.connector_id
                AND c.organization_id = b.organization_id AND lower(c.provider) = b.provider
            JOIN department_mcp_access g ON g.department_id = b.department_id
                AND g.connector_id = b.connector_id
                AND (g.organization_id IS NULL OR g.organization_id = b.organization_id)
            WHERE b.organization_id = ? AND b.department_id = ? AND b.trigger_workflows = 1
                AND g.is_active = 1 AND (? IS NULL OR b.id = ?)
            ORDER BY b.provider, b.channel_id, b.id
        """, (workflow.organization_id, workflow.department_id, binding_id, binding_id))
        return [dict(row) for row in rows]


def _require_binding(db, workflow, rule):
    eligible = _eligible(db, workflow, rule.binding_id)
    if not eligible:
        raise HTTPException(422, "Select a trigger-enabled binding in the workflow department.")
    return eligible[0]


def _public(workflow):
    config = json.loads(workflow.definition_json).get("metadata", {}).get("channel_trigger")
    return {"revision": workflow.revision, "rule": config}


@router.get("")
def get_channel_trigger(workflow_id: str, request: Request, db=Depends(get_db_manager)):
    actor, workflow = _scope(db, request, workflow_id)
    can_edit = bool(actor.user_id and actor.allows(workflow.department_id, 3))
    return {**_public(workflow), "can_edit": can_edit,
            "bindings": _eligible(db, workflow) if can_edit else []}


@router.put("")
def save_channel_trigger(workflow_id: str, request: Request, payload: TriggerUpdate, db=Depends(get_db_manager)):
    actor, workflow = _scope(db, request, workflow_id, 3)
    if not actor.user_id:
        raise HTTPException(403, "Channel trigger edits require a signed-in user.")
    definition = json.loads(workflow.definition_json)
    metadata = definition.setdefault("metadata", {})
    if payload.rule:
        _require_binding(db, workflow, payload.rule)
        metadata["channel_trigger"] = payload.rule.model_dump()
        metadata["channel_trigger_principal"] = actor.user_id
    else:
        metadata.pop("channel_trigger", None)
        metadata.pop("channel_trigger_principal", None)
    try:
        updated = db.update_workflow(workflow.id, definition_json=json.dumps(definition, ensure_ascii=False),
                                     actor_id=actor.user_id, expected_revision=payload.expected_revision,
                                     change_summary="Update channel trigger rule")
    except WorkflowRevisionConflict:
        raise HTTPException(409, "Workflow changed. Reload before saving the trigger.") from None
    if updated is None:
        raise HTTPException(404, "Workflow not found.")
    return _public(updated)


@router.post("/preview")
def preview_channel_trigger(workflow_id: str, request: Request, payload: TriggerPreview, db=Depends(get_db_manager)):
    _, workflow = _scope(db, request, workflow_id, 3)
    binding = _require_binding(db, workflow, payload.rule)
    event = payload.event.model_copy(update={"channel_id": binding["channel_id"]})
    parameters = match_trigger(payload.rule, event)
    return {"matched": parameters is not None, "parameters": parameters}
