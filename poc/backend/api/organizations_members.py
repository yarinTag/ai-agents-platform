"""Organizations: members ownership."""

from fastapi import HTTPException, Depends, status, Request
from typing import List
from datetime import datetime
from ..dependencies import get_db_manager, DatabaseManager
from ..security import create_access_token, hash_password, verify_password
from .organizations_models import AcceptInviteRequest, AuthResponse, BulkInviteRequest, BulkInviteResponse, DepartmentMemberResponse, UserResponse
from fastapi import APIRouter

router = APIRouter()

INVITABLE_ROLES = {"ORG_ADMIN", "MANAGER", "OPERATOR", "MEMBER"}
MAX_INVITES_PER_REQUEST = 100
MAX_INVITE_DAYS = 30
MIN_PASSWORD_LENGTH = 8


def _require_active_org_admin(request: Request, db: DatabaseManager, organization_id: str):
    """Require a current, database-verified ORG_ADMIN of exactly this organization."""
    claims = getattr(request.state, "user", None) or {}
    user = db.get_user(claims.get("sub")) if claims.get("sub") else None
    if (not user or user.status != "ACTIVE" or user.role != "ORG_ADMIN"
            or user.organization_id != organization_id
            or claims.get("org_id") != organization_id):
        raise HTTPException(status_code=403, detail="An active administrator of this organization must send invitations.")
    return user


@router.post("/departments/{dept_id}/members/bulk-invite", response_model=BulkInviteResponse, status_code=status.HTTP_201_CREATED)
def bulk_invite_department_members(
    dept_id: str,
    req: BulkInviteRequest,
    request: Request,
    db: DatabaseManager = Depends(get_db_manager)
):
    """
    Bulk invite email addresses to a department.
    Only an active ORG_ADMIN of the department's organization may invite. The
    single-use tokens are returned to that administrator for out-of-band delivery.
    """
    dept = db.get_department(dept_id)
    if not dept or not dept.organization_id:
        raise HTTPException(status_code=404, detail=f"Department '{dept_id}' not found")
    _require_active_org_admin(request, db, dept.organization_id)

    if req.role not in INVITABLE_ROLES:
        raise HTTPException(status_code=400, detail=f"Role must be one of: {', '.join(sorted(INVITABLE_ROLES))}")
    if len(req.emails) > MAX_INVITES_PER_REQUEST:
        raise HTTPException(status_code=400, detail=f"At most {MAX_INVITES_PER_REQUEST} invitations per request")
    if not 1 <= req.expires_in_days <= MAX_INVITE_DAYS:
        raise HTTPException(status_code=400, detail=f"expires_in_days must be between 1 and {MAX_INVITE_DAYS}")

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

    # Holding an invite token never authenticates as an existing account.
    password = (req.password or "").strip()
    existing = db.get_user_by_email(inv.email)
    if existing:
        if existing.organization_id != inv.organization_id:
            raise HTTPException(status_code=409, detail="This email already belongs to another organization")
        if existing.status != "ACTIVE":
            raise HTTPException(status_code=403, detail="This account is not active")
        if not password or not existing.password_hash or not verify_password(password, existing.password_hash):
            raise HTTPException(status_code=401, detail="Enter the existing account password to accept this invitation")
        pw_hash = None
    else:
        if len(password) < MIN_PASSWORD_LENGTH:
            raise HTTPException(status_code=400, detail=f"Password must be at least {MIN_PASSWORD_LENGTH} characters")
        pw_hash = hash_password(password)
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

