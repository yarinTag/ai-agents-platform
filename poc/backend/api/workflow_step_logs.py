"""
Workflow Step Logs & Configurable Notification Policy API Router.
Provides:
- GET /executions/{execution_id}/steps: All steps with correlated events, MCP calls, and audit logs
- GET /executions/{execution_id}/steps/{step_key}/logs: Detailed correlated logs for a single step
- PUT /{workflow_id}/notification-policy: Updates workflow notification policy and step-level overrides
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from ..dependencies import DatabaseManager, get_db_manager
from ..security.tenant_access import authorize_execution, authorize_workflow
from shared.notifications import VALID_NOTIFY_POLICIES
from workflows.step_logs_service import get_execution_step_logs

logger = logging.getLogger(__name__)

router = APIRouter()


class NotificationPolicyUpdateRequest(BaseModel):
    """Request payload for updating a workflow's channel notification policy."""
    notify_policy: str = Field(
        "FINAL_ONLY",
        description="Supported policies: FINAL_ONLY, START_AND_END, EVERY_STEP, ON_FAILURE_ONLY",
    )
    provider: Optional[str] = Field("slack", description="Notification channel provider (slack or telegram)")
    channel_id: Optional[str] = Field("", description="Target channel or chat identifier")
    connector_id: Optional[str] = None
    notify_mode: Optional[str] = None
    message_template: Optional[str] = None
    step_notifications: Optional[Dict[str, bool]] = Field(
        default=None,
        description="Optional per-step notification override mapping {step_key: bool}",
    )


@router.get("/executions/{execution_id}/steps")
def list_execution_steps_with_logs(
    execution_id: str,
    request: Request,
    db: DatabaseManager = Depends(get_db_manager),
) -> Dict[str, Any]:
    """Return all steps and correlated observability/security logs for a workflow execution."""
    authorize_execution(request, db, execution_id)
    return get_execution_step_logs(db=db, execution_id=execution_id)


@router.get("/executions/{execution_id}/steps/{step_key}/logs")
def get_single_step_correlated_logs(
    execution_id: str,
    step_key: str,
    request: Request,
    db: DatabaseManager = Depends(get_db_manager),
) -> Dict[str, Any]:
    """Return detailed correlated events, MCP tool calls, and security audit logs for a single step."""
    authorize_execution(request, db, execution_id)
    correlated = get_execution_step_logs(db=db, execution_id=execution_id, step_key=step_key)
    if not correlated["steps"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Step '{step_key}' not found in workflow execution '{execution_id}'",
        )
    step_data = dict(correlated["steps"][0])
    step_data["execution_id"] = execution_id
    step_data["total_steps"] = 1
    step_data["steps"] = correlated["steps"]
    return step_data


@router.put("/{workflow_id}/notification-policy")
def update_workflow_notification_policy(
    workflow_id: str,
    req: NotificationPolicyUpdateRequest,
    request: Request,
    db: DatabaseManager = Depends(get_db_manager),
) -> Dict[str, Any]:
    """
    Update `metadata.channel_binding.notify_policy`, `provider`, `channel_id`,
    and optional `step_notifications` inside a workflow's `definition_json`.
    """
    policy_upper = (req.notify_policy or "").strip().upper()
    if policy_upper not in VALID_NOTIFY_POLICIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid notify_policy '{req.notify_policy}'. Must be one of {VALID_NOTIFY_POLICIES}",
        )

    wf = authorize_workflow(request, db, workflow_id, admin=True)

    try:
        def_dict = json.loads(wf.definition_json or "{}")
        if not isinstance(def_dict, dict):
            def_dict = {"id": wf.id, "name": wf.name, "steps": []}
    except Exception:
        def_dict = {"id": wf.id, "name": wf.name, "steps": []}

    metadata = def_dict.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}

    channel_binding = metadata.get("channel_binding")
    if not isinstance(channel_binding, dict):
        channel_binding = {}

    channel_binding["notify_policy"] = policy_upper
    if req.provider is not None:
        channel_binding["provider"] = req.provider
    elif "provider" not in channel_binding:
        channel_binding["provider"] = "slack"

    if req.channel_id is not None:
        channel_binding["channel_id"] = req.channel_id
    elif "channel_id" not in channel_binding:
        channel_binding["channel_id"] = ""

    if req.connector_id is not None:
        channel_binding["connector_id"] = req.connector_id
    elif "connector_id" not in channel_binding:
        channel_binding["connector_id"] = channel_binding["provider"]

    if req.notify_mode is not None:
        channel_binding["notify_mode"] = req.notify_mode
    elif "notify_mode" not in channel_binding:
        channel_binding["notify_mode"] = "ON_COMPLETE"

    if req.message_template is not None:
        channel_binding["message_template"] = req.message_template

    if req.step_notifications is not None:
        clean_step_map = {str(k): bool(v) for k, v in req.step_notifications.items()}
        channel_binding["step_notifications"] = clean_step_map
        steps_list = def_dict.get("steps")
        if isinstance(steps_list, list):
            for step_obj in steps_list:
                if isinstance(step_obj, dict) and step_obj.get("key") in clean_step_map:
                    step_obj["notify_on_complete"] = clean_step_map[step_obj["key"]]

    metadata["channel_binding"] = channel_binding
    def_dict["metadata"] = metadata

    new_def_json = json.dumps(def_dict, indent=2)
    updated = db.update_workflow(id=workflow_id, definition_json=new_def_json)

    return {
        "id": updated.id,
        "workflow_id": updated.id,
        "name": updated.name,
        "notify_policy": channel_binding["notify_policy"],
        "channel_binding": channel_binding,
        "step_notifications": channel_binding.get("step_notifications", {}),
        "definition_json": updated.definition_json,
    }
