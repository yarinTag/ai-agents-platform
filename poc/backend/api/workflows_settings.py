"""Per-workflow settings (model, machine size, egress allowlist) and write-only secrets."""
import json
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field

from ..dependencies import get_db_manager, DatabaseManager, WorkflowRevisionConflict
from ..security import get_authorized_scope
from .workflows_mapping import _workflow_actor, _check_workflow_scope

router = APIRouter()


class WorkflowSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    settings: Dict[str, Any]
    expected_revision: int = Field(ge=1)
    change_summary: Optional[str] = Field(default=None, max_length=500)


class WorkflowSecretWrite(BaseModel):
    model_config = ConfigDict(extra='forbid')
    value: Optional[str] = Field(default=None, min_length=1, max_length=32768)
    external_ref: Optional[str] = Field(default=None, min_length=1, max_length=600)


def _load(workflow_id: str, request: Request, db) -> Any:
    wf = db.get_workflow(workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    _check_workflow_scope(wf, get_authorized_scope(request, db))
    return wf


def _manager(request: Request, db, wf):
    """Current-DB ORG_ADMIN, or MANAGER of the workflow's department. JWT role alone is not enough."""
    claims = getattr(request.state, "user", None) or {}
    user = db.get_user(claims.get("sub")) if claims.get("sub") else None
    if not user or user.status != "ACTIVE" or user.organization_id != wf.organization_id:
        raise HTTPException(status_code=403, detail="Only active organization users can manage workflow settings.")
    from ..security.identity import load_actor
    actor = load_actor(request, db)
    actor.require(wf.department_id, 3)
    return user



def _can_manage(request, db, wf) -> bool:
    try:
        _manager(request, db, wf)
        return True
    except HTTPException:
        return False


def _response(db, wf, can_manage: bool) -> Dict[str, Any]:
    from workflows.settings import MACHINE_SIZES, MAX_ALLOWED_HOSTS, WorkflowSettings, validate_settings
    from runtime.execution_backends import backend_catalog
    raw = json.loads(wf.definition_json or "{}").get("settings")
    try:
        settings = validate_settings(raw)
        error = None
    except ValueError as exc:
        settings, error = WorkflowSettings(), str(exc)  # Shown so a manager can repair it; runs fail closed.
    secrets: List[Dict[str, Any]] = [
        {"name": row["name"], "kind": row["kind"], "external_ref": row["external_ref"],
         "created_by": row["created_by"], "updated_at": row["updated_at"]}
        for row in db.list_workflow_secrets(wf.id)]
    return {"workflow_id": wf.id, "revision": wf.revision, "settings": settings.model_dump(),
            "settings_error": error, "secrets": secrets, "can_manage": can_manage,
            "machine_sizes": MACHINE_SIZES, "max_allowed_hosts": MAX_ALLOWED_HOSTS,
            "execution_backends": backend_catalog()}


def _audit(db, request, user, action, wf, details):
    db.log_audit(action=action, actor=user.id, entity_type="workflow", entity_id=wf.id, details=details,
                 ip_address=request.client.host if request.client else None)


@router.get("/{workflow_id}/settings")
def get_workflow_settings(workflow_id: str, request: Request, db: DatabaseManager = Depends(get_db_manager)):
    wf = _load(workflow_id, request, db)
    return _response(db, wf, _can_manage(request, db, wf))


@router.put("/{workflow_id}/settings")
def update_workflow_settings(workflow_id: str, req: WorkflowSettingsUpdate, request: Request,
                             db: DatabaseManager = Depends(get_db_manager)):
    from workflows.settings import validate_settings
    from workflows.parser import validate_workflow_definition
    wf = _load(workflow_id, request, db)
    user = _manager(request, db, wf)
    try:
        settings = validate_settings(req.settings)
        data = json.loads(wf.definition_json)
        data["settings"] = settings.model_dump(exclude_none=True)
        validate_workflow_definition(data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid workflow settings: {exc}") from exc
    try:
        updated = db.update_workflow(workflow_id, definition_json=json.dumps(data, ensure_ascii=False),
            **_workflow_actor(request), expected_revision=req.expected_revision,
            change_summary=req.change_summary or "Updated workflow settings")
    except WorkflowRevisionConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    _audit(db, request, user, "workflow.settings.update", wf, {
        "execution_backend": settings.execution_backend.value,
        "model": settings.model, "machine_size": settings.machine_size,
        "network_allowlist": settings.network_allowlist})
    return _response(db, updated, True)


@router.put("/{workflow_id}/secrets/{name}")
def put_workflow_secret(workflow_id: str, name: str, req: WorkflowSecretWrite, request: Request,
                        db: DatabaseManager = Depends(get_db_manager)):
    from integrations.tool_definitions import ToolAccessError
    from integrations.workflow_secrets import store_secret
    wf = _load(workflow_id, request, db)
    user = _manager(request, db, wf)
    try:
        store_secret(db, wf, name, req.value, req.external_ref, user.id)
    except ToolAccessError as exc:  # Server configuration (key/prefixes) missing: not the caller's fault.
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    kind = "external" if req.external_ref is not None else "encrypted"
    _audit(db, request, user, "workflow.secret.set", wf, {"name": name, "kind": kind})  # Never the value.
    row = next(r for r in db.list_workflow_secrets(wf.id) if r["name"] == name)
    return {"name": row["name"], "kind": row["kind"], "external_ref": row["external_ref"],
            "created_by": row["created_by"], "updated_at": row["updated_at"]}


@router.delete("/{workflow_id}/secrets/{name}", status_code=status.HTTP_204_NO_CONTENT)
def delete_workflow_secret(workflow_id: str, name: str, request: Request,
                           db: DatabaseManager = Depends(get_db_manager)):
    wf = _load(workflow_id, request, db)
    user = _manager(request, db, wf)
    if not db.delete_workflow_secret(wf.id, name):
        raise HTTPException(status_code=404, detail="Secret not found")
    _audit(db, request, user, "workflow.secret.delete", wf, {"name": name})
    return Response(status_code=status.HTTP_204_NO_CONTENT)
