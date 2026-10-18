"""
API Key and Bearer token authentication provider.
"""
import os
import logging
from typing import Optional, Dict, Any
from fastapi import Request, HTTPException, status, Security
from fastapi.security import APIKeyHeader, HTTPBearer, HTTPAuthorizationCredentials

logger = logging.getLogger(__name__)

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)
BEARER_AUTH = HTTPBearer(auto_error=False)


def get_configured_api_key() -> Optional[str]:
    """Get the currently configured platform API key from environment."""
    key = os.getenv("PLATFORM_API_KEY", "").strip()
    return key if key else None


def get_current_user_claims(request: Request) -> Optional[Dict[str, Any]]:
    """Extract validated JWT claims from request state if present."""
    return getattr(request.state, "user", None)


def get_current_user_optional(request: Request) -> Optional[Dict[str, Any]]:
    """Extract validated JWT claims from request state if present."""
    return getattr(request.state, "user", None)


def require_org_admin(request: Request) -> Dict[str, Any]:
    """Dependency enforcing that the authenticated user possesses the ORG_ADMIN role."""
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide a valid JWT bearer token."
        )
    role = user.get("role", "MEMBER")
    if role != "ORG_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: ORG_ADMIN privileges required."
        )
    return user


def get_current_org_id(request: Request) -> Optional[str]:
    """Extract organization ID from current user claims in request state."""
    user = get_current_user_claims(request)
    if isinstance(user, dict):
        return user.get("org_id")
    return None


def get_authorized_scope(request: Request, db_manager=None) -> Dict[str, Any]:
    """
    Compute authorized tenant and department scope for current request.
    Returns:
    {
        "org_id": str or None,
        "user_id": str or None,
        "is_org_admin": bool,
        "department_ids": List[str],
        "default_department_id": str or None
    }
    """
    claims = get_current_user_claims(request) or {}
    user_id = claims.get("sub")
    org_id = claims.get("org_id")
    role = claims.get("role", "MEMBER")
    is_org_admin = (role == "ORG_ADMIN")

    department_ids = []

    # If org admin and db_manager provided, get all department IDs in the organization
    if is_org_admin and org_id and db_manager:
        try:
            with db_manager._get_connection() as conn:
                rows = conn.execute("SELECT id FROM departments WHERE organization_id = ? ORDER BY created_at ASC", (org_id,)).fetchall()
                department_ids = [r['id'] for r in rows]
        except Exception:
            department_ids = []

    # If not org admin, or if department_ids is still empty:
    if not is_org_admin:
        if db_manager and user_id:
            try:
                user_depts = db_manager.get_user_departments(user_id)
                department_ids = [d["department_id"] for d in user_depts if d.get("department_id")]
            except Exception:
                department_ids = []
        if not department_ids and "departments" in claims:
            # Fallback to JWT departments claim: [{"id": ...}]
            department_ids = [
                d.get("id") or d.get("department_id")
                for d in claims["departments"]
                if isinstance(d, dict) and (d.get("id") or d.get("department_id"))
            ]

    default_department_id = department_ids[0] if department_ids else None
    if not default_department_id and org_id and db_manager:
        try:
            with db_manager._get_connection() as conn:
                row = conn.execute("SELECT id FROM departments WHERE organization_id = ? ORDER BY created_at ASC LIMIT 1", (org_id,)).fetchone()
                if row:
                    default_department_id = row['id']
                    if is_org_admin and default_department_id not in department_ids:
                        department_ids.append(default_department_id)
        except Exception:
            pass

    # Check X-Department-ID header override if caller specified an active department
    header_dept = request.headers.get("X-Department-ID", "").strip()
    if header_dept:
        if is_org_admin or header_dept in department_ids:
            default_department_id = header_dept
            if header_dept not in department_ids and is_org_admin:
                department_ids.append(header_dept)

    return {
        "org_id": org_id,
        "user_id": user_id,
        "is_org_admin": is_org_admin,
        "department_ids": department_ids,
        "default_department_id": default_department_id
    }


async def authenticate_request(
    request: Request,
    api_key_header: Optional[str] = Security(API_KEY_HEADER),
    bearer_creds: Optional[HTTPAuthorizationCredentials] = Security(BEARER_AUTH)
) -> Dict[str, Any]:
    """
    Authenticate an incoming request against signed JWT or PLATFORM_API_KEY.
    Enforces strict zero-trust access control. Unauthenticated requests are rejected
    with 401 unless the path is exempt or ALLOW_UNAUTHENTICATED_DEV=true is set.
    """
    path = request.url.path.rstrip("/") or "/"

    # Exempt public documentation, health check, and auth onboarding endpoints
    exempt_paths = {
        "/", "/health", "/docs", "/openapi.json", "/redoc",
        "/api/v1/auth/status", "/api/v1/auth/login", "/api/v1/auth/org-register", "/api/v1/invitations/accept"
    }
    if path in exempt_paths or request.url.path in exempt_paths or request.url.path.startswith("/api/v1/workflows/webhooks/"):
        return {
            "authenticated": True,
            "mode": "public_exempt",
            "actor": "anonymous"
        }

    # 1. Extract and verify JWT token from Authorization header or ?token= query parameter
    raw_token = None
    if bearer_creds and bearer_creds.credentials:
        raw_token = bearer_creds.credentials.strip()
    elif request.query_params.get("token"):
        raw_token = request.query_params.get("token").strip()
    elif request.headers.get("authorization", "").lower().startswith("bearer "):
        raw_token = request.headers.get("authorization")[7:].strip()

    if raw_token:
        from .tokens import decode_access_token
        jwt_claims = decode_access_token(raw_token)
        if jwt_claims:
            request.state.user = jwt_claims
            return {
                "authenticated": True,
                "mode": "jwt_bearer",
                "actor": jwt_claims.get("email", jwt_claims.get("sub", "user")),
                "user": jwt_claims
            }

    # 2. Check PLATFORM_API_KEY matching X-API-Key, Bearer token, or ?api_key= query param
    configured_key = get_configured_api_key()
    if configured_key:
        provided_key = None
        query_key = request.query_params.get("api_key")
        if api_key_header:
            provided_key = api_key_header.strip()
        elif raw_token:
            provided_key = raw_token
        elif query_key:
            provided_key = query_key.strip()

        if provided_key and provided_key == configured_key:
            return {
                "authenticated": True,
                "mode": "api_key",
                "actor": "api_client"
            }

    # 3. Allow open development mode only if explicitly enabled via environment variable
    if os.getenv("ALLOW_UNAUTHENTICATED_DEV", "false").lower() == "true":
        return {
            "authenticated": True,
            "mode": "open_development",
            "actor": "developer"
        }

    # 4. Strict rejection for unauthenticated requests
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required. Please log in with a valid organization JWT token."
    )
