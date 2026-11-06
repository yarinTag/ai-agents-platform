"""
API Key and Bearer token authentication provider.
"""
import hmac
import os
import logging
from typing import Optional, Dict, Any
from fastapi import Request, HTTPException, status, Security, Depends
from ..dependencies import get_db_manager
from fastapi.security import APIKeyHeader, HTTPBearer, HTTPAuthorizationCredentials

logger = logging.getLogger(__name__)

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)
BEARER_AUTH = HTTPBearer(auto_error=False)


# Browsers' EventSource cannot send headers; only this stream may take ?token=.
QUERY_TOKEN_PATHS = {"/api/v1/events/stream"}


def get_configured_api_key() -> Optional[str]:
    """Get the currently configured platform API key from environment."""
    key = os.getenv("PLATFORM_API_KEY", "").strip()
    return key if key else None


def _service_claims(org_env: str, mode: str) -> Optional[Dict[str, Any]]:
    """Non-JWT callers act inside one configured organization, never across all tenants."""
    org_id = os.getenv(org_env, "").strip()
    if not org_id:
        logger.warning("%s authentication rejected: %s is not set", mode, org_env)
        return None
    return {"org_id": org_id, "role": "ORG_ADMIN", "service": mode}


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
    from .identity import load_actor
    from ..dependencies import get_db_manager
    actor = load_actor(request, get_db_manager())
    if not actor.admin:
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
    if db_manager is None:
        from ..dependencies import get_db_manager
        db_manager = get_db_manager()
    from .identity import load_actor
    actor = load_actor(request, db_manager)
    departments = list(actor.departments)
    if actor.selected_department:
        departments = [actor.selected_department]
    return {"org_id": actor.organization_id, "user_id": actor.user_id,
            "is_org_admin": actor.admin, "department_ids": departments,
            "default_department_id": actor.default_department(),
            "selected_department_id": actor.selected_department,
            "expires_at": (get_current_user_claims(request) or {}).get("exp")}



async def authenticate_request(
    request: Request,
    api_key_header: Optional[str] = Security(API_KEY_HEADER),
    bearer_creds: Optional[HTTPAuthorizationCredentials] = Security(BEARER_AUTH),
    db_manager = Depends(get_db_manager),
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
        "/api/v1/auth/status", "/api/v1/auth/login", "/api/v1/auth/org-register", "/api/v1/invitations/accept",
        "/api/v1/approvals/telegram-callback", "/api/v1/approvals/slack-callback"
    }
    if path in exempt_paths or request.url.path in exempt_paths or request.url.path.startswith("/api/v1/workflows/webhooks/"):
        return {
            "authenticated": True,
            "mode": "public_exempt",
            "actor": "anonymous"
        }

    # 1. Extract and verify JWT token from Authorization header (or ?token= on the SSE stream only)
    raw_token = None
    if bearer_creds and bearer_creds.credentials:
        raw_token = bearer_creds.credentials.strip()
    elif request.headers.get("authorization", "").lower().startswith("bearer "):
        raw_token = request.headers.get("authorization")[7:].strip()
    elif path in QUERY_TOKEN_PATHS and request.query_params.get("token"):
        raw_token = request.query_params.get("token").strip()

    if raw_token:
        from .tokens import decode_access_token
        jwt_claims = decode_access_token(raw_token)
        if jwt_claims:
            if jwt_claims.get("service"):
                raise HTTPException(401, "User tokens cannot impersonate service identities.")
            request.state.user = jwt_claims
            from .identity import load_actor
            request.state.access_actor = load_actor(request, db_manager)
            return {
                "authenticated": True,
                "mode": "jwt_bearer",
                "actor": jwt_claims.get("email", jwt_claims.get("sub", "user")),
                "user": jwt_claims
            }

    # 2. Check PLATFORM_API_KEY from X-API-Key or Bearer header (never a query parameter)
    configured_key = get_configured_api_key()
    if configured_key:
        provided_key = api_key_header.strip() if api_key_header else raw_token
        if provided_key and hmac.compare_digest(provided_key.encode(), configured_key.encode()):
            claims = _service_claims("PLATFORM_API_KEY_ORG_ID", "api_key")
            if claims:
                request.state.user = claims
                return {"authenticated": True, "mode": "api_key", "actor": "api_client", "user": claims}

    # 3. Open development mode needs both dev flags and an explicit organization
    from .tokens import dev_mode_enabled
    if dev_mode_enabled() and os.getenv("ALLOW_UNAUTHENTICATED_DEV", "false").lower() == "true":
        claims = _service_claims("PLATFORM_DEV_ORG_ID", "open_development")
        if claims:
            request.state.user = claims
            return {"authenticated": True, "mode": "open_development", "actor": "developer", "user": claims}

    # 4. Strict rejection for unauthenticated requests
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required. Please log in with a valid organization JWT token."
    )
