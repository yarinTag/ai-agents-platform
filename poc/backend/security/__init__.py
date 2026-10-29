"""
Security and hardening modules for AI Agents Platform.
Includes authentication, request correlation, rate limiting, and structured error handling.
"""

from .auth import (
    authenticate_request,
    get_configured_api_key,
    get_current_user_claims,
    get_current_user_optional,
    get_current_org_id,
    get_authorized_scope,
    require_org_admin,
)
from .tokens import create_access_token, decode_access_token, hash_password, verify_password
from .correlation import CorrelationIdMiddleware, CORRELATION_HEADER
from .rate_limiter import RateLimiterMiddleware
from .errors import http_exception_handler, generic_exception_handler
from .firewall import (
    PromptInjectionFirewall,
    PromptInjectionDetectedError,
    InjectionScanResult,
    get_prompt_firewall
)

__all__ = [
    "authenticate_request",
    "get_configured_api_key",
    "get_current_user_claims",
    "get_current_user_optional",
    "get_current_org_id",
    "get_authorized_scope",
    "require_org_admin",
    "create_access_token",
    "decode_access_token",
    "hash_password",
    "verify_password",
    "CorrelationIdMiddleware",
    "CORRELATION_HEADER",
    "RateLimiterMiddleware",
    "http_exception_handler",
    "generic_exception_handler",
    "PromptInjectionFirewall",
    "PromptInjectionDetectedError",
    "InjectionScanResult",
    "get_prompt_firewall",
]
