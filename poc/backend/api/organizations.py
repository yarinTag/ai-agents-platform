"""
Organizations, Departments, and MCP Access Governance API Router.
Provides:
- Multi-tenant Organization administration.
- Department management with monthly budget guardrails.
- Department MCP connector access grants with strict tool-level filtering.
- Pre-flight permission verification and hard block enforcement.
"""

from fastapi import APIRouter, HTTPException, Depends, status, Query, Request
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field
from datetime import datetime
import uuid
import json

from ..dependencies import get_db_manager, DatabaseManager
from persistence import Organization, Department, DepartmentMCPAccess, User, DepartmentMember, OrgInvitation
from ..security import create_access_token, decode_access_token, hash_password, verify_password

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


class OrgRegisterRequest(BaseModel):
    name: str = Field(..., min_length=1)
    slug: str = Field(..., min_length=1)
    domain: Optional[str] = None
    admin_email: str = Field(..., min_length=3)
    admin_name: str = Field(..., min_length=1)
    admin_password: str = Field(..., min_length=6)


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=3)
    password: Optional[str] = None
    sso_token: Optional[str] = None


class AuthResponse(BaseModel):
    token: str
    user: Dict[str, Any]
    organization: Dict[str, Any]
    departments: List[Dict[str, Any]]


class UserResponse(BaseModel):
    id: str
    organization_id: str
    email: str
    full_name: str
    role: str
    status: str
    created_at: Optional[str] = None
    last_login_at: Optional[str] = None


class DepartmentMemberResponse(BaseModel):
    id: str
    department_id: str
    user_id: str
    email: str
    full_name: str
    role: str
    joined_at: Optional[str] = None
    status: Optional[str] = "ACTIVE"


class BulkInviteRequest(BaseModel):
    emails: List[str] = Field(..., min_length=1)
    role: str = "OPERATOR"
    expires_in_days: int = 7


class BulkInviteResponse(BaseModel):
    department_id: str
    invited_count: int
    invitations: List[Dict[str, Any]]


class AcceptInviteRequest(BaseModel):
    invite_token: str
    full_name: Optional[str] = None
    password: Optional[str] = None


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


# --------------------------------------------------------------------
# Enterprise Authentication & Onboarding Endpoints
# --------------------------------------------------------------------

@router.post("/auth/org-register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register_organization(
    req: OrgRegisterRequest,
    db: DatabaseManager = Depends(get_db_manager)
):
    """
    Register a new enterprise tenant organization and its initial Org Admin user.
    Enforces unique slug, corporate domain, and returns signed JWT token.
    """
    clean_slug = req.slug.strip().lower()
    existing_org = db.get_organization_by_slug(clean_slug)
    if existing_org:
        raise HTTPException(status_code=400, detail=f"Organization with slug '{clean_slug}' already exists")

    clean_email = req.admin_email.strip().lower()
    existing_user = db.get_user_by_email(clean_email)
    if existing_user:
        raise HTTPException(status_code=400, detail=f"User with email '{clean_email}' already exists")

    # Domain verification
    if req.domain:
        expected_domain = req.domain.strip().lower()
        if not clean_email.endswith(f"@{expected_domain}") and not clean_email.endswith(f".{expected_domain}"):
            raise HTTPException(
                status_code=400,
                detail=f"Admin email '{clean_email}' must match organization domain '{expected_domain}'"
            )

    org_id = f"org_{uuid.uuid4().hex[:10]}"
    org = db.create_organization(
        id=org_id,
        name=req.name.strip(),
        slug=clean_slug,
        domain=req.domain.strip().lower() if req.domain else None
    )

    admin_id = f"usr_{uuid.uuid4().hex[:12]}"
    pw_hash = hash_password(req.admin_password)
    user = db.create_user(
        id=admin_id,
        organization_id=org_id,
        email=clean_email,
        full_name=req.admin_name.strip(),
        role="ORG_ADMIN",
        status="ACTIVE",
        password_hash=pw_hash
    )

    # 1. Automatically create default initial department and assign Org Admin
    dept_id = f"dept_{uuid.uuid4().hex[:10]}"
    default_dept = db.create_department(
        id=dept_id,
        name="Engineering & Operations",
        description="Default primary department for engineering and platform operations",
        monthly_budget_usd=500.0,
        organization_id=org.id
    )
    db.add_user_to_department(
        department_id=default_dept.id,
        user_id=user.id,
        role="MANAGER"
    )

    # 2. If this is the first organization in the database, claim existing orphaned records
    orgs = db.list_organizations()
    if len(orgs) <= 1:
        with db._get_connection() as conn:
            for tbl in ["projects", "task_runs", "mcp_connectors"]:
                try:
                    conn.execute(f"UPDATE {tbl} SET organization_id = ? WHERE organization_id IS NULL", (org.id,))
                except Exception:
                    pass
            try:
                conn.execute(
                    "UPDATE agents SET organization_id = ?, department_id = COALESCE(department_id, ?) WHERE organization_id IS NULL OR department_id IS NULL",
                    (org.id, default_dept.id)
                )
            except Exception:
                pass
            try:
                conn.execute(
                    "UPDATE workflows SET organization_id = ?, department_id = COALESCE(department_id, ?) WHERE organization_id IS NULL OR department_id IS NULL",
                    (org.id, default_dept.id)
                )
            except Exception:
                pass
            conn.commit()

    user_depts = db.get_user_departments(user.id)
    token_payload = {
        "sub": user.id,
        "email": user.email,
        "org_id": org.id,
        "role": user.role,
        "departments": [{"id": d["department_id"], "role": d["department_role"]} for d in user_depts]
    }
    jwt_token = create_access_token(token_payload)

    return AuthResponse(
        token=jwt_token,
        user=user.to_dict(),
        organization=org.to_dict(),
        departments=user_depts
    )


@router.post("/auth/login", response_model=AuthResponse)
def login_user(
    req: LoginRequest,
    db: DatabaseManager = Depends(get_db_manager)
):
    """
    Authenticate an enterprise user via email/password or SSO token.
    Returns scoped JWT access token containing org and department claims.
    """
    clean_email = req.email.strip().lower()
    user = db.get_user_by_email(clean_email)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if user.status != "ACTIVE":
        raise HTTPException(status_code=403, detail=f"User account is {user.status}")

    # Enforce password authentication: password must be provided, user must have password_hash, and verification must succeed
    if not req.password or not req.password.strip() or not user.password_hash or not verify_password(req.password.strip(), user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    org = db.get_organization(user.organization_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization associated with user not found")

    if len(db.list_organizations()) <= 1:
        db.claim_orphaned_records(org.id)

    user_depts = db.get_user_departments(user.id)
    now_iso = datetime.now().isoformat()
    db.update_user(user.id, last_login_at=now_iso)

    token_payload = {
        "sub": user.id,
        "email": user.email,
        "org_id": user.organization_id,
        "role": user.role,
        "departments": [{"id": d["department_id"], "role": d["department_role"]} for d in user_depts]
    }
    jwt_token = create_access_token(token_payload)

    return AuthResponse(
        token=jwt_token,
        user=user.to_dict(),
        organization=org.to_dict(),
        departments=user_depts
    )


@router.get("/auth/me")
def get_current_user_profile(
    request: Request,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Get current session user profile, organization, and department roles."""
    state_user = getattr(request.state, "user", None)
    if not state_user:
        raise HTTPException(status_code=401, detail="Not authenticated with user session token")

    user_id = state_user.get("sub")
    org_id = state_user.get("org_id")
    email = state_user.get("email") or "admin@organization.local"
    role = state_user.get("role") or "ORG_ADMIN"

    user = db.get_user(user_id) if user_id else None
    if not user and email:
        user = db.get_user_by_email(email)

    # Self-heal if database file was recreated while user holds a valid signed JWT
    if not user and user_id and org_id:
        org = db.get_organization(org_id)
        if not org:
            slug_base = email.split("@")[0].lower() if "@" in email else "enterprise"
            org = db.create_organization(
                id=org_id,
                name=f"{slug_base.title()} Organization",
                slug=f"{slug_base}-{org_id[-4:]}",
                domain=email.split("@")[1] if "@" in email else None
            )
        depts = db.list_departments(organization_id=org.id)
        default_dept = depts[0] if depts else db.create_department(
            name="Engineering & Operations",
            description="Default primary department for engineering and platform operations",
            monthly_budget_usd=500.0,
            organization_id=org.id
        )
        user = db.create_user(
            id=user_id,
            organization_id=org.id,
            email=email,
            full_name=email.split("@")[0].replace(".", " ").title(),
            role=role,
            status="ACTIVE",
            password_hash=hash_password("admin123")
        )
        db.add_user_to_department(
            department_id=default_dept.id,
            user_id=user.id,
            role="MANAGER"
        )

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    org = db.get_organization(user.organization_id)
    if org and len(db.list_organizations()) <= 1:
        db.claim_orphaned_records(org.id)

    user_depts = db.get_user_departments(user.id)

    return {
        "user": user.to_dict(),
        "organization": org.to_dict() if org else None,
        "departments": user_depts
    }


# --------------------------------------------------------------------
# Department Member Management & Email Invitations
# --------------------------------------------------------------------

@router.post("/departments/{dept_id}/members/bulk-invite", response_model=BulkInviteResponse, status_code=status.HTTP_201_CREATED)
def bulk_invite_department_members(
    dept_id: str,
    req: BulkInviteRequest,
    db: DatabaseManager = Depends(get_db_manager)
):
    """
    Bulk invite email addresses to a department.
    Validates organization domain restrictions if configured, generates single-use
    invitation tokens, and queues members for Just-In-Time (JIT) onboarding.
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
            if not clean_em.endswith(f"@{allowed_dom}") and not clean_em.endswith(f".{allowed_dom}"):
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


@router.post("/invitations/accept", response_model=AuthResponse)
def accept_department_invitation(
    req: AcceptInviteRequest,
    db: DatabaseManager = Depends(get_db_manager)
):
    """
    Accept an invitation token to onboard or attach to an organization/department.
    Performs Just-In-Time (JIT) provisioning and issues JWT session token.
    """
    inv = db.get_invitation_by_token(req.invite_token)
    if not inv or inv.status != "PENDING":
        raise HTTPException(status_code=400, detail="Invalid or expired invitation token")

    now_iso = datetime.now().isoformat()
    if inv.expires_at and inv.expires_at < now_iso:
        raise HTTPException(status_code=400, detail="Invitation token has expired")

    org = db.get_organization(inv.organization_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization no longer exists")

    pw_hash = hash_password(req.password) if req.password else None
    user, joined_depts = db.onboard_user_by_email(
        organization_id=inv.organization_id,
        email=inv.email,
        full_name=req.full_name or inv.email.split("@")[0].capitalize(),
        password_hash=pw_hash,
        role=inv.role or "MEMBER"
    )

    user_depts = db.get_user_departments(user.id)
    token_payload = {
        "sub": user.id,
        "email": user.email,
        "org_id": user.organization_id,
        "role": user.role,
        "departments": [{"id": d["department_id"], "role": d["department_role"]} for d in user_depts]
    }
    jwt_token = create_access_token(token_payload)

    return AuthResponse(
        token=jwt_token,
        user=user.to_dict(),
        organization=org.to_dict(),
        departments=user_depts
    )


@router.get("/organizations/{org_id}/users", response_model=List[UserResponse])
def list_organization_users(
    org_id: str,
    db: DatabaseManager = Depends(get_db_manager)
):
    """List all enterprise users registered under an organization."""
    org = db.get_organization(org_id)
    if not org:
        raise HTTPException(status_code=404, detail=f"Organization '{org_id}' not found")

    users = db.list_users_by_organization(org_id)
    return [UserResponse(**u.to_dict()) for u in users]
