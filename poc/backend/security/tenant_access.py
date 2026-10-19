"""
Shared tenant-authorization helpers for API routes (single source of truth, Rule of 2).

Callers authenticated with a JWT (`request.state.user`) are bound to their own organization;
writes require `ORG_ADMIN`. Platform-API-key callers (no `request.state.user`) are operators.
Anything whose owning organization cannot be resolved is rejected (fail-closed, 404 to avoid
leaking existence of other tenants' resources).
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import HTTPException, Request, status


def authorize_org(request: Request, org_id: str, admin: bool = False) -> None:
    """JWT callers may only access their own org; writes require ORG_ADMIN. API-key callers are operators."""
    user = getattr(request.state, "user", None)
    if user is None:
        return
    if user.get("org_id") != org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: not a member of this organization")
    if admin and user.get("role") != "ORG_ADMIN":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: ORG_ADMIN role required")


def org_of_department(db: Any, department_id: Optional[str]) -> Optional[str]:
    """Return the owning organization id of a department, or None if unknown."""
    if not department_id:
        return None
    dept = db.get_department(department_id)
    return getattr(dept, "organization_id", None) if dept else None


def authorize_workflow(request: Request, db: Any, workflow_id: str, admin: bool = False) -> Any:
    """Authorize access to a workflow via its department's organization. Returns the workflow."""
    wf = db.get_workflow(workflow_id)
    if wf is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Workflow '{workflow_id}' not found")
    _authorize_owned(request, org_of_department(db, wf.department_id), f"Workflow '{workflow_id}'", admin)
    return wf


def authorize_execution(request: Request, db: Any, execution_id: str) -> Any:
    """Authorize read access to a workflow execution via its department/workflow organization."""
    ex = db.get_workflow_execution(execution_id)
    if ex is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Workflow execution '{execution_id}' not found")
    org = org_of_department(db, ex.department_id)
    if org is None:
        wf = db.get_workflow(ex.workflow_id)
        org = org_of_department(db, wf.department_id) if wf else None
    _authorize_owned(request, org, f"Workflow execution '{execution_id}'", False)
    return ex


def _authorize_owned(request: Request, owner_org: Optional[str], label: str, admin: bool) -> None:
    """Enforce that a resource's owning org matches the JWT caller; operators bypass."""
    if getattr(request.state, "user", None) is None:
        return
    if owner_org is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{label} not found")
    try:
        authorize_org(request, owner_org, admin=admin)
    except HTTPException as exc:
        if exc.detail.startswith("Forbidden: not a member"):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{label} not found") from exc
        raise
