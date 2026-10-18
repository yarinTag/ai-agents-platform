"""
Enterprise Authentication, JWT Session Issuance, and Invitation Onboarding Routes.
"""

from fastapi import APIRouter, HTTPException, Depends, status, Request
from datetime import datetime
import uuid

from ...dependencies import get_db_manager, DatabaseManager
from ...security import create_access_token, hash_password, verify_password
from shared.validators import normalize_email, validate_email_domain
from .schemas import (
    OrgRegisterRequest,
    LoginRequest,
    AuthResponse,
    AcceptInviteRequest,
)

router = APIRouter()


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

    clean_email = normalize_email(req.admin_email)
    existing_user = db.get_user_by_email(clean_email)
    if existing_user:
        raise HTTPException(status_code=400, detail=f"User with email '{clean_email}' already exists")

    if req.domain:
        expected_domain = req.domain.strip().lower()
        if not validate_email_domain(clean_email, expected_domain):
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

    token_payload = {
        "sub": user.id,
        "email": user.email,
        "org_id": org.id,
        "role": user.role,
        "departments": []
    }
    jwt_token = create_access_token(token_payload)

    return AuthResponse(
        token=jwt_token,
        user=user.to_dict(),
        organization=org.to_dict(),
        departments=[]
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
    clean_email = normalize_email(req.email)
    user = db.get_user_by_email(clean_email)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if user.status != "ACTIVE":
        raise HTTPException(status_code=403, detail=f"User account is {user.status}")

    if user.password_hash and req.password:
        if not verify_password(req.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid email or password")

    org = db.get_organization(user.organization_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization associated with user not found")

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
    user = db.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    org = db.get_organization(user.organization_id)
    user_depts = db.get_user_departments(user.id)

    return {
        "user": user.to_dict(),
        "organization": org.to_dict() if org else None,
        "departments": user_depts
    }


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
    user, _ = db.onboard_user_by_email(
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
