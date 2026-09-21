"""
In-memory sliding window rate limiter per client IP.
Enforces requests-per-minute limits to prevent abuse and denial of service.
"""
import time
import os
from collections import defaultdict
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """Sliding-window in-memory rate limiter."""
    _instances = []

    def __init__(self, app, default_requests_per_minute: int = 120):
        super().__init__(app)
        self.default_rpm = default_requests_per_minute
        self.history = defaultdict(list)
        self.exempt_paths = {"/health", "/docs", "/redoc", "/openapi.json"}
        RateLimiterMiddleware._instances.append(self)

    @classmethod
    def clear_history(cls):
        """Reset rate limiter state (useful for tests and administrative resets)."""
        for inst in cls._instances:
            inst.history.clear()

    def get_limit(self) -> int:
        env_limit = os.getenv("PLATFORM_RATE_LIMIT")
        if env_limit is not None:
            try:
                return int(env_limit)
            except ValueError:
                pass
        return self.default_rpm

    async def dispatch(self, request: Request, call_next):
        rpm = self.get_limit()
        if rpm <= 0 or request.url.path in self.exempt_paths:
            return await call_next(request)

        # Identify client by IP
        client_ip = request.client.host if request.client else "127.0.0.1"
        now = time.time()
        window_start = now - 60.0

        # Filter out timestamps outside current 60s window
        valid_timestamps = [t for t in self.history[client_ip] if t > window_start]

        if len(valid_timestamps) >= rpm:
            oldest = valid_timestamps[0]
            retry_after = max(1, int(60.0 - (now - oldest)))
            correlation_id = getattr(request.state, "correlation_id", None)
            return JSONResponse(
                status_code=429,
                headers={"Retry-After": str(retry_after)},
                content={
                    "error": {
                        "code": 429,
                        "message": f"Rate limit exceeded ({rpm} req/min). Retry after {retry_after} seconds.",
                        "detail": "Too many requests. Please throttle your client dispatches.",
                        "correlation_id": correlation_id,
                        "retry_after": retry_after
                    }
                }
            )

        valid_timestamps.append(now)
        self.history[client_ip] = valid_timestamps

        return await call_next(request)
