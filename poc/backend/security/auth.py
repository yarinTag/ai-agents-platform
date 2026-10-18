"""
API Key and Bearer token authentication provider with fail-closed production posture.
"""
import os
import hmac
import logging
from typing import Optional, Dict, Any
from fastapi import Request, HTTPException, status, Security
from fastapi.security import APIKeyHeader, HTTPBearer, HTTPAuthorizationCredentials

from .tokens import DEFAULT_SECRET

logger = logging.getLogger(__name__)

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)
BEARER_AUTH = HTTPBearer(auto_error=False)

_INSECURE_DEFAULT_SECRETS = {
    "",
    "default",
    "changeme",
    "secret",
    DEFAULT_SECRET,
}


def is_production_env() -> bool:
    """Return True if the platform is configured to run in production mode."""
    return os.getenv("ENV", os.getenv("PLATFORM_ENV", "dev")).strip().lower() in (
        "prod",
        "production",
    )


def get_configured_api_key() -> Optional[str]:
    """Get the currently configured platform API key from environment."""
    key = os.getenv("PLATFORM_API_KEY", "").strip()
    return key if key else None


def verify_production_security_posture() -> None:
    """
    Enforce fail-closed security posture in production environments.

    Raises `RuntimeError` if `is_production_env()` is True and either
    `PLATFORM_API_KEY` or `PLATFORM_JWT_SECRET` is missing or set to a known default.
    """
    if not is_production_env():
        return

    api_key = (os.getenv("PLATFORM_API_KEY") or "").strip()
    if api_key in _INSECURE_DEFAULT_SECRETS:
        raise RuntimeError(
            "Fail-closed: PLATFORM_API_KEY must be explicitly configured with a non-default secret in production"
        )

    jwt_secret = (os.getenv("PLATFORM_JWT_SECRET") or "").strip()
    if jwt_secret in _INSECURE_DEFAULT_SECRETS:
        raise RuntimeError(
            "Fail-closed: PLATFORM_JWT_SECRET must be explicitly configured with a non-default secret in production"
        )


async def authenticate_request(
    request: Request,
    api_key_header: Optional[str] = Security(API_KEY_HEADER),
    bearer_creds: Optional[HTTPAuthorizationCredentials] = Security(BEARER_AUTH),
) -> Dict[str, Any]:
    """
    Authenticate an incoming request against PLATFORM_API_KEY or signed JWT.
    If PLATFORM_API_KEY is not configured, allows development mode ONLY when
    not in production (`ENV != 'production'`); fails closed with HTTP 503 in production.
    Exempts public endpoints such as health and docs.
    """
    # Exempt public documentation, health check, and auth endpoints
    exempt_paths = {
        "/", "/health", "/docs", "/openapi.json", "/redoc",
        "/api/v1/auth/status", "/api/v1/auth/login", "/api/v1/auth/org-register", "/api/v1/invitations/accept"
    }
    if request.url.path in exempt_paths:
        return {
            "authenticated": True,
            "mode": "public_exempt",
            "actor": "anonymous"
        }

    # 1. First check if incoming Authorization is a valid signed JWT bearer token
    if bearer_creds and bearer_creds.credentials:
        from .tokens import decode_access_token
        jwt_claims = decode_access_token(bearer_creds.credentials.strip())
        if jwt_claims:
            request.state.user = jwt_claims
            return {
                "authenticated": True,
                "mode": "jwt_bearer",
                "actor": jwt_claims.get("email", jwt_claims.get("sub", "user")),
                "user": jwt_claims
            }

    configured_key = get_configured_api_key()
    if not configured_key:
        if is_production_env():
            raise HTTPException(
                status_code=503,
                detail="Fail-closed: PLATFORM_API_KEY is not configured in production",
            )
        return {
            "authenticated": True,
            "mode": "open_development",
            "actor": "developer"
        }

    # Extract token from X-API-Key header, Authorization: Bearer <key>, or ?api_key query param
    provided_key = None
    query_key = request.query_params.get("api_key")
    if api_key_header:
        provided_key = api_key_header.strip()
    elif bearer_creds and bearer_creds.credentials:
        provided_key = bearer_creds.credentials.strip()
    elif query_key:
        provided_key = query_key.strip()

    if not provided_key or not hmac.compare_digest(
        provided_key.encode("utf-8"),
        configured_key.encode("utf-8"),
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing authentication credentials. Provide a valid JWT Bearer token or configured API key."
        )

    return {
        "authenticated": True,
        "mode": "api_key",
        "actor": "api_client"
    }
