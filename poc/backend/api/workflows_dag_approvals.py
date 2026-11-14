"""Tenant-scoped dashboard inbox and personal approval decisions."""
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict

from storage import dag_approvals
from ..dependencies import get_db_manager
from ..security.identity import load_actor
from ..security.resource_access import Resources

router = APIRouter(prefix="/dag-approvals")


class Decision(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    approve: bool


def _actor(request, db, department_id):
    actor = load_actor(request, db)
    Resources(actor).require("department", department_id)
    if not actor.user_id:
        raise HTTPException(403, "A personal account is required.")
    return actor


@router.get("")
def list_dag_approvals(department_id: str, request: Request,
                       after: Annotated[str | None, Query(pattern=r"^(dga|wfa)_[a-f0-9]{32}$")] = None,
                       view: Literal["pending", "history"] = "pending", execution_id: str | None = None,
                       kind: Literal["checkpoint", "terminal"] = "checkpoint",
                       db=Depends(get_db_manager)):
    actor = _actor(request, db, department_id)
    resources = Resources(actor)
    if execution_id:
        resources.require("execution", execution_id)
    if kind == "terminal":
        return _terminal_inbox(db, actor, resources, department_id, view, after, execution_id)
    result = dag_approvals.inbox(db, actor.organization_id, department_id, actor.user_id,
                                 after=after or "", view=view, execution_id=execution_id)
    result["items"] = [item for item in result["items"]
                       if resources.allows("execution", item["execution_id"])]
    return result


def _terminal_inbox(db, actor, resources, department_id, view, after, execution_id):
    base = """SELECT a.id,a.execution_id,a.status,a.expires_at,a.resolved_at,a.created_at,w.id AS workflow_id,
                     w.name AS workflow_name
              FROM workflow_approvals a
              JOIN workflow_executions x ON x.id=a.execution_id
              JOIN workflows w ON w.id=x.workflow_id AND w.organization_id=a.organization_id
              WHERE a.organization_id=? AND a.department_id=?"""
    params = (actor.organization_id, department_id)
    if execution_id:
        base += " AND a.execution_id=?"
        params += (execution_id,)
    active = "a.status IN ('NOTIFYING','PENDING','RESOLVING','EXPIRING')"
    base += " AND " + (active if view == "pending" else f"NOT ({active})")
    with db._get_connection() as conn:
        cursor = conn.execute(base +
                              " AND a.id=?", (*params, after)).fetchone() if after else None
        if cursor:
            base += " AND (COALESCE(a.resolved_at,a.created_at),a.id)<(?,?)"
            params += (cursor["resolved_at"] or cursor["created_at"], cursor["id"])
        rows = conn.execute(base + " ORDER BY COALESCE(a.resolved_at,a.created_at) DESC,a.id DESC LIMIT 51",
                            params).fetchall()
    return {"items": [dict(row) for row in rows[:50] if resources.allows("execution", row["execution_id"])],
            "next_after": rows[49]["id"] if len(rows) > 50 else None}


@router.post("/{approval_id}/decision")
def decide_dag_approval(approval_id: str, department_id: str, payload: Decision,
                        request: Request, db=Depends(get_db_manager)):
    actor = _actor(request, db, department_id)
    with db._get_connection() as conn:
        row = conn.execute("""SELECT execution_id FROM workflow_dag_approvals
            WHERE id=? AND organization_id=? AND department_id=?""",
            (approval_id, actor.organization_id, department_id)).fetchone()
    Resources(actor).require("execution", row["execution_id"] if row else None)
    try:
        status = dag_approvals.decide(db, actor.organization_id, department_id, approval_id,
                                     actor.user_id, payload.approve)
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from None
    except dag_approvals.ApprovalConflict as exc:
        raise HTTPException(409, str(exc)) from None
    return {"status": status}
