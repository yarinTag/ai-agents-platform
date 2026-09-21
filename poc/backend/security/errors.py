"""
Standardized error formatting and exception handlers.
Ensures uniform error JSON responses across the entire REST API.
"""
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


async def http_exception_handler(request: Request, exc: HTTPException):
    """Formats HTTPException into a consistent JSON envelope with correlation tracking."""
    correlation_id = getattr(request.state, "correlation_id", None)
    detail = exc.detail
    message = detail if isinstance(detail, str) else "Request failed"
    return JSONResponse(
        status_code=exc.status_code,
        headers=getattr(exc, "headers", None),
        content={
            "detail": detail,
            "error": {
                "code": exc.status_code,
                "message": message,
                "detail": detail,
                "correlation_id": correlation_id,
                "timestamp": datetime.now().isoformat()
            }
        }
    )


async def generic_exception_handler(request: Request, exc: Exception):
    """Formats unhandled exceptions into a standardized 500 error envelope."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.exception(f"Unhandled server error [correlation_id={correlation_id}]: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": 500,
                "message": "Internal server error",
                "detail": str(exc),
                "correlation_id": correlation_id,
                "timestamp": datetime.now().isoformat()
            }
        }
    )
