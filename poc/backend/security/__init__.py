"""
Security and hardening modules for AI Agents Platform.
Includes authentication, request correlation, rate limiting, and structured error handling.
"""

from .auth import authenticate_request, get_configured_api_key
from .tokens import create_access_token, decode_access_token, hash_password, verify_password
from .correlation import CorrelationIdMiddleware, CORRELATION_HEADER
from .rate_limiter import RateLimiterMiddleware
from .errors import http_exception_handler, generic_exception_handler

__all__ = [
    "authenticate_request",
    "get_configured_api_key",
    "create_access_token",
    "decode_access_token",
    "hash_password",
    "verify_password",
    "CorrelationIdMiddleware",
    "CORRELATION_HEADER",
    "RateLimiterMiddleware",
    "http_exception_handler",
    "generic_exception_handler"
]
