"""
Department Management, Budget Guardrails, and Member Assignment Routes.
"""

from fastapi import APIRouter, HTTPException, Depends, status, Query
from typing import List, Optional
import uuid

from ...dependencies import get_db_manager, DatabaseManager
from persistence import Department
from shared.validators import validate_email_domain
from .schemas import (
    DepartmentCreateRequest,
    DepartmentUpdateRequest,
    DepartmentResponse,
    DepartmentMemberResponse,
    BulkInviteRequest,
    BulkInviteResponse,
)

router = APIRouter()


@router.post("/departments", response_model=DepartmentResponse, status_code=status.HTTP_201_CREATED)
def create_department(
    req: DepartmentCreateRequest,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Create a department with budget controls and optional organization assignment."""
    dept_id = req.id or f"dept_{uuid.uuid4().hex[:10]}"
    dept = db.create_department(
        id=dept_id,
        name=req.name,
        description=req.description,
        monthly_budget_usd=req.monthly_budget_usd,
        budget_action=req.budget_action,
        alert_threshold_pct=req.alert_threshold_pct,
        organization_id=req.organization_id
    )
    return DepartmentResponse(**dept.to_dict())


@router.get("/departments", response_model=List[DepartmentResponse])
def list_departments(
    organization_id: Optional[str] = Query(None, description="Filter departments by organization ID"),
    db: DatabaseManager = Depends(get_db_manager)
):
    """List departments, optionally filtered by organization ID."""
    with db._get_connection() as conn:
        if organization_id:
            rows = conn.execute("SELECT * FROM departments WHERE organization_id = ? ORDER BY name ASC", (organization_id,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM departments ORDER BY name ASC").fetchall()
        depts = [
            Department(
                id=r['id'],
                name=r['name'],
                description=r['description'],
                monthly_budget_usd=float(r['monthly_budget_usd']),
                current_spend_usd=float(r['current_spend_usd']),
                budget_action=r['budget_action'],
                alert_threshold_pct=float(r['alert_threshold_pct']),
                organization_id=r['organization_id'] if 'organization_id' in r.keys() else None,
                created_at=r['created_at'],
                updated_at=r['updated_at']
            )
            for r in rows
        ]
    return [DepartmentResponse(**d.to_dict()) for d in depts]


@router.get("/departments/{dept_id}", response_model=DepartmentResponse)
def get_department(
    dept_id: str,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Get department details."""
    dept = db.get_department(dept_id)
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")
    return DepartmentResponse(**dept.to_dict())


@router.put("/departments/{dept_id}", response_model=DepartmentResponse)
def update_department(
    dept_id: str,
    req: DepartmentUpdateRequest,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Update department budget or organization."""
    dept = db.get_department(dept_id)
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")

    updated = db.update_department(
        id=dept_id,
        name=req.name,
        description=req.description,
        monthly_budget_usd=req.monthly_budget_usd,
        budget_action=req.budget_action,
        alert_threshold_pct=req.alert_threshold_pct
    )
    return DepartmentResponse(**updated.to_dict())


@router.get("/departments/{dept_id}/budget")
def check_department_budget(
    dept_id: str,
    requested_cost: float = Query(0.0, ge=0.0),
    db: DatabaseManager = Depends(get_db_manager)
):
    """Check budget availability and HARD_STOP status for a department."""
    dept = db.get_department(dept_id)
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")
    return db.check_department_budget(dept_id, requested_cost=requested_cost)


@router.post("/departments/{dept_id}/members/bulk-invite", response_model=BulkInviteResponse, status_code=status.HTTP_201_CREATED)
def bulk_invite_department_members(
    dept_id: str,
    req: BulkInviteRequest,
    db: DatabaseManager = Depends(get_db_manager)
):
    """
    Bulk invite email addresses to a department using shared domain validator.
    """
    dept = db.get_department(dept_id)
    if not dept:
        raise HTTPException(status_code=404, detail=f"Department '{dept_id}' not found")

    if not dept.organization_id:
        raise HTTPException(status_code=400, detail="Department is not associated with an enterprise organization")

    org = db.get_organization(dept.organization_id)
    if org and org.domain:
        allowed_dom = org.domain.strip().lower()
        for em in req.emails:
            clean_em = em.strip().lower()
            if not validate_email_domain(clean_em, allowed_dom):
                raise HTTPException(
                    status_code=400,
                    detail=f"Email '{clean_em}' does not belong to organization domain '@{allowed_dom}'"
                )

    invitations = db.bulk_invite_to_department(
        organization_id=dept.organization_id,
        department_id=dept_id,
        emails=req.emails,
        role=req.role,
        expires_in_days=req.expires_in_days
    )

    return BulkInviteResponse(
        department_id=dept_id,
        invited_count=len(invitations),
        invitations=[inv.to_dict() for inv in invitations]
    )


@router.get("/departments/{dept_id}/members", response_model=List[DepartmentMemberResponse])
def list_department_members(
    dept_id: str,
    db: DatabaseManager = Depends(get_db_manager)
):
    """List all users assigned to a specific department."""
    dept = db.get_department(dept_id)
    if not dept:
        raise HTTPException(status_code=404, detail=f"Department '{dept_id}' not found")

    members = db.list_department_members(dept_id)
    return [
        DepartmentMemberResponse(
            id=m["id"],
            department_id=m["department_id"],
            user_id=m["user_id"],
            email=m["email"],
            full_name=m["full_name"],
            role=m["role"],
            joined_at=m["joined_at"],
            status=m.get("user_status", "ACTIVE")
        )
        for m in members
    ]


@router.delete("/departments/{dept_id}/members/{user_id}")
def remove_department_member(
    dept_id: str,
    user_id: str,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Remove a user from a department."""
    dept = db.get_department(dept_id)
    if not dept:
        raise HTTPException(status_code=404, detail=f"Department '{dept_id}' not found")

    removed = db.remove_user_from_department(dept_id, user_id)
    if not removed:
        raise HTTPException(status_code=404, detail=f"User '{user_id}' is not a member of department '{dept_id}'")

    return {"status": "SUCCESS", "message": f"User '{user_id}' removed from department '{dept_id}'"}
