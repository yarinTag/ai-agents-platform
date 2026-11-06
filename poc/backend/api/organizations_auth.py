"""Organizations: auth ownership."""

from fastapi import HTTPException, Depends, status, Request
from datetime import datetime
import uuid
from ..dependencies import get_db_manager, DatabaseManager
from ..security import create_access_token, hash_password, verify_password
from .organizations_models import AuthResponse, LoginRequest, OrgRegisterRequest
from fastapi import APIRouter

router = APIRouter()


def _session_departments(db: DatabaseManager, user, memberships):
    """Project selectable departments separately from membership-based JWT claims."""
    if user.role != "ORG_ADMIN" or not user.organization_id:
        return memberships
    member_by_id = {entry["department_id"]: entry for entry in memberships}
    result = []
    for department in db.list_departments(organization_id=user.organization_id):
        if department is None:
            continue
        entry = {**department.to_dict(), "department_id": department.id}
        membership = member_by_id.get(department.id)
        if membership:
            entry.update({key: membership[key] for key in ("department_role", "joined_at") if key in membership})
        result.append(entry)
    return result


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

    user_depts = [entry for entry in db.get_user_departments(user.id) if entry.get("organization_id") == user.organization_id]
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
        departments=_session_departments(db, user, user_depts)
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

    # Enforce password authentication: password must be provided, user must have password_hash, and verification must succeed
    if not req.password or not req.password.strip() or not user.password_hash or not verify_password(req.password.strip(), user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if user.status != "ACTIVE":
        raise HTTPException(status_code=403, detail=f"User account is {user.status}")

    org = db.get_organization(user.organization_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization associated with user not found")

    user_depts = [entry for entry in db.get_user_departments(user.id) if entry.get("organization_id") == user.organization_id]
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
        departments=_session_departments(db, user, user_depts)
    )



@router.get("/auth/me")
def get_current_user_profile(
    request: Request,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Get current session user profile, organization, and department roles."""
    state_user = getattr(request.state, "user", None)
    if not state_user or state_user.get("service"):
        # Org-bound API-key/dev service claims are not a user session and must never self-heal a user.
        raise HTTPException(status_code=401, detail="Not authenticated with user session token")

    # Resolve strictly by the signed subject. A token never creates, revives or
    # re-identifies an account: unknown or inactive users must sign in again.
    user_id = state_user.get("sub")
    user = db.get_user(user_id) if user_id else None
    if not user or user.status != "ACTIVE" or user.organization_id != state_user.get("org_id"):
        raise HTTPException(status_code=401, detail="Session is no longer valid. Please sign in again.")

    org = db.get_organization(user.organization_id)
    user_depts = [entry for entry in db.get_user_departments(user.id) if entry.get("organization_id") == user.organization_id]

    return {
        "user": user.to_dict(),
        "organization": org.to_dict() if org else None,
        "departments": _session_departments(db, user, user_depts)
    }

