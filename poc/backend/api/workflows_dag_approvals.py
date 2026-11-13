"""Tenant-scoped dashboard inbox and personal approval decisions."""
from typing import Annotated

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
                       after: Annotated[str | None, Query(pattern=r"^dga_[a-f0-9]{32}$")] = None,
                       db=Depends(get_db_manager)):
    actor = _actor(request, db, department_id)
    result = dag_approvals.inbox(db, actor.organization_id, department_id, actor.user_id, after=after or "")
    resources = Resources(actor)
    result["items"] = [item for item in result["items"]
                       if resources.allows("execution", item["execution_id"])]
    return result


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
