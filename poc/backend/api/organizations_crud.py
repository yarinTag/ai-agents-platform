"""Organizations: crud ownership."""

from fastapi import HTTPException, Depends, status, Query, Request
from typing import List, Optional
import uuid
from ..dependencies import get_db_manager, DatabaseManager
from persistence import Department
from .organizations_models import DepartmentCreateRequest, DepartmentResponse, DepartmentUpdateRequest, OrganizationCreateRequest, OrganizationResponse, OrganizationUpdateRequest
from fastapi import APIRouter

router = APIRouter()


@router.post("/organizations", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
def create_organization(
    req: OrganizationCreateRequest,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Create a new tenant organization."""
    existing = db.get_organization_by_slug(req.slug)
    if existing:
        raise HTTPException(status_code=400, detail=f"Organization with slug '{req.slug}' already exists")

    org_id = req.id or f"org_{uuid.uuid4().hex[:10]}"
    org = db.create_organization(
        id=org_id,
        name=req.name,
        slug=req.slug,
        domain=req.domain,
        settings_json=req.settings_json or "{}"
    )
    return OrganizationResponse(**org.to_dict())



@router.get("/organizations", response_model=List[OrganizationResponse])
def list_organizations(
    db: DatabaseManager = Depends(get_db_manager)
):
    """List all tenant organizations."""
    orgs = db.list_organizations()
    return [OrganizationResponse(**o.to_dict()) for o in orgs]



@router.get("/organizations/{org_id}", response_model=OrganizationResponse)
def get_organization(
    org_id: str,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Get an organization by ID."""
    org = db.get_organization(org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return OrganizationResponse(**org.to_dict())



@router.put("/organizations/{org_id}", response_model=OrganizationResponse)
def update_organization(
    org_id: str,
    req: OrganizationUpdateRequest,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Update organization settings."""
    org = db.get_organization(org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    updated = db.update_organization(
        id=org_id,
        name=req.name,
        slug=req.slug,
        domain=req.domain,
        settings_json=req.settings_json
    )
    return OrganizationResponse(**updated.to_dict())



@router.post("/departments", response_model=DepartmentResponse, status_code=status.HTTP_201_CREATED)
def create_department(
    req: DepartmentCreateRequest,
    request: Request,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Create a department with budget controls and optional organization assignment."""
    target_org_id = req.organization_id
    if not target_org_id:
        user_state = getattr(request.state, "user", None)
        if isinstance(user_state, dict):
            target_org_id = user_state.get("org_id")

    dept_id = req.id or f"dept_{uuid.uuid4().hex[:10]}"
    dept = db.create_department(
        id=dept_id,
        name=req.name,
        description=req.description,
        monthly_budget_usd=req.monthly_budget_usd,
        budget_action=req.budget_action,
        alert_threshold_pct=req.alert_threshold_pct,
        organization_id=target_org_id
    )
    return DepartmentResponse(**dept.to_dict())



@router.get("/departments", response_model=List[DepartmentResponse])
def list_departments(
    request: Request,
    organization_id: Optional[str] = Query(None, description="Filter departments by organization ID"),
    db: DatabaseManager = Depends(get_db_manager)
):
    """List departments, optionally filtered by organization ID."""
    filter_org_id = organization_id
    if not filter_org_id:
        user_state = getattr(request.state, "user", None)
        if isinstance(user_state, dict):
            filter_org_id = user_state.get("org_id")

    with db._get_connection() as conn:
        if filter_org_id:
            rows = conn.execute("SELECT * FROM departments WHERE organization_id = ? ORDER BY name ASC", (filter_org_id,)).fetchall()
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

