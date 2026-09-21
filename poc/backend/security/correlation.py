"""
Request correlation ID middleware.
Extracts or creates X-Correlation-ID for distributed tracing across logs, events, and runs.
"""
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request, Response

CORRELATION_HEADER = "X-Correlation-ID"


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Middleware that attaches a unique correlation ID to every incoming request and response."""

    async def dispatch(self, request: Request, call_next):
        correlation_id = request.headers.get(CORRELATION_HEADER)
        if not correlation_id:
            correlation_id = f"req_{uuid.uuid4().hex[:12]}"

        request.state.correlation_id = correlation_id

        response: Response = await call_next(request)
        response.headers[CORRELATION_HEADER] = correlation_id
        return response
