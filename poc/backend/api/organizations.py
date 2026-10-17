"""
Organizations, Departments, and MCP Access Governance API Router.
Provides:
- Multi-tenant Organization administration.
- Department management with monthly budget guardrails.
- Department MCP connector access grants with strict tool-level filtering.
- Pre-flight permission verification and hard block enforcement.
"""

from fastapi import APIRouter, HTTPException, Depends, status, Query
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field
import uuid
import json

from ..dependencies import get_db_manager, DatabaseManager
from persistence import Organization, Department, DepartmentMCPAccess

router = APIRouter()


# --------------------------------------------------------------------
# Request / Response Schemas
# --------------------------------------------------------------------

class OrganizationCreateRequest(BaseModel):
    id: Optional[str] = None
    name: str = Field(..., min_length=1)
    slug: str = Field(..., min_length=1)
    domain: Optional[str] = None
    settings_json: Optional[str] = "{}"


class OrganizationUpdateRequest(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    domain: Optional[str] = None
    settings_json: Optional[str] = None


class OrganizationResponse(BaseModel):
    id: str
    name: str
    slug: str
    domain: Optional[str] = None
    settings_json: str = "{}"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class DepartmentCreateRequest(BaseModel):
    id: Optional[str] = None
    name: str = Field(..., min_length=1)
    description: Optional[str] = None
    monthly_budget_usd: float = 100.0
    budget_action: str = "HARD_STOP"
    alert_threshold_pct: float = 80.0
    organization_id: Optional[str] = None


class DepartmentUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    monthly_budget_usd: Optional[float] = None
    budget_action: Optional[str] = None
    alert_threshold_pct: Optional[float] = None
    organization_id: Optional[str] = None


class DepartmentResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    monthly_budget_usd: float
    current_spend_usd: float
    budget_action: str
    alert_threshold_pct: float
    organization_id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class DepartmentMCPAccessRequest(BaseModel):
    connector_id: str
    allowed_tools: Union[str, List[str]] = "*"
    organization_id: Optional[str] = None
    granted_by_user_id: Optional[str] = None


class DepartmentMCPAccessResponse(BaseModel):
    id: str
    department_id: str
    connector_id: str
    allowed_tools: str
    parsed_allowed_tools: List[str]
    organization_id: Optional[str] = None
    is_active: bool
    granted_by_user_id: Optional[str] = None
    granted_at: Optional[str] = None


def _format_access_response(access: DepartmentMCPAccess) -> DepartmentMCPAccessResponse:
    raw = access.allowed_tools or "*"
    parsed: List[str] = []
    if raw == "*":
        parsed = ["*"]
    elif raw.startswith("["):
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = [raw]
    else:
        parsed = [t.strip() for t in raw.split(",") if t.strip()]

    return DepartmentMCPAccessResponse(
        id=access.id,
        department_id=access.department_id,
        connector_id=access.connector_id,
        allowed_tools=access.allowed_tools,
        parsed_allowed_tools=parsed,
        organization_id=access.organization_id,
        is_active=access.is_active,
        granted_by_user_id=access.granted_by_user_id,
        granted_at=access.granted_at
    )


# --------------------------------------------------------------------
# Organizations Endpoints
# --------------------------------------------------------------------

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


# --------------------------------------------------------------------
# Departments Endpoints
# --------------------------------------------------------------------

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


# --------------------------------------------------------------------
# Department MCP Access Governance Endpoints (Tool-Level Filtering)
# --------------------------------------------------------------------

@router.post("/departments/{dept_id}/mcp-access", response_model=DepartmentMCPAccessResponse, status_code=status.HTTP_201_CREATED)
def grant_department_mcp_access(
    dept_id: str,
    req: DepartmentMCPAccessRequest,
    db: DatabaseManager = Depends(get_db_manager)
):
    """
    Grant or update MCP connector access for a department with tool-level filtering.
    allowed_tools can be '*' (all tools) or a specific list e.g. ['git_diff', 'list_issues'].
    """
    dept = db.get_department(dept_id)
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")

    access = db.grant_department_mcp_access(
        department_id=dept_id,
        connector_id=req.connector_id,
        allowed_tools=req.allowed_tools,
        organization_id=req.organization_id or dept.organization_id,
        granted_by_user_id=req.granted_by_user_id
    )
    return _format_access_response(access)


@router.get("/departments/{dept_id}/mcp-access", response_model=List[DepartmentMCPAccessResponse])
def list_department_mcp_access(
    dept_id: str,
    db: DatabaseManager = Depends(get_db_manager)
):
    """List all active MCP grants and tool permissions for a department."""
    dept = db.get_department(dept_id)
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")

    grants = db.list_department_mcp_access(dept_id)
    return [_format_access_response(g) for g in grants]


@router.get("/departments/{dept_id}/mcp-access/{connector_id}", response_model=DepartmentMCPAccessResponse)
def get_department_mcp_access(
    dept_id: str,
    connector_id: str,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Get active MCP access record for department and connector."""
    access = db.get_department_mcp_access(dept_id, connector_id)
    if not access:
        raise HTTPException(status_code=404, detail=f"No active access grant for connector '{connector_id}' on department '{dept_id}'")
    return _format_access_response(access)


@router.delete("/departments/{dept_id}/mcp-access/{connector_id}")
def revoke_department_mcp_access(
    dept_id: str,
    connector_id: str,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Revoke a department's access to an MCP connector."""
    revoked = db.revoke_department_mcp_access(dept_id, connector_id)
    if not revoked:
        raise HTTPException(status_code=404, detail=f"No active grant found to revoke for connector '{connector_id}'")
    return {"status": "SUCCESS", "message": f"Revoked access to '{connector_id}' for department '{dept_id}'"}


@router.get("/departments/{dept_id}/mcp-access/{connector_id}/check")
def check_department_mcp_permission(
    dept_id: str,
    connector_id: str,
    tool_name: Optional[str] = Query(None, description="Optional tool name to verify permission"),
    db: DatabaseManager = Depends(get_db_manager)
):
    """
    Check if a department is permitted to access an MCP connector and an optional specific tool.
    Returns: { "allowed": bool, "reason": str, "allowed_tools": List[str] }
    """
    return db.check_department_mcp_permission(
        department_id=dept_id,
        connector_id=connector_id,
        tool_name=tool_name
    )
