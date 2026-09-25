# AGENTS.md - Security & Production Hardening Service

## 1. Service Identity & Mission
The **Security & Production Hardening Service** (`poc/backend/security/`) enforces security boundaries, request authentication, rate limiting, request correlation tracking, and uniform exception responses across the AI Agents Platform API.

---

## 2. Core Capabilities & Specializations
* **API Authentication (`auth.py`)**:
  * Protects routes using `authenticate_request` FastAPI dependency (`auth_deps`).
  * Validates Bearer tokens and API keys against configured environment credentials (`PLATFORM_API_KEY`).
  * Exempts public health (`/health`) and documentation endpoints (`/docs`, `/redoc`).
* **Request Correlation Tracking (`correlation.py`)**:
  * `CorrelationIdMiddleware` assigns a unique `X-Correlation-ID` (UUID) to every incoming request if not provided.
  * Injects correlation IDs into response headers and Python logging context for distributed tracing.
* **Rate Limiting & DoS Protection (`rate_limiter.py`)**:
  * `RateLimiterMiddleware` implements sliding-window in-memory throttling per client IP.
  * Rejects traffic exceeding capacity with HTTP 429 (`Too Many Requests`) and `Retry-After` header.
* **Structured Exception Handling (`errors.py`)**:
  * Uniform error payload formatting (`http_exception_handler` and `generic_exception_handler`).
  * Masks internal stack traces and database errors in production while logging full diagnostics.

---

## 3. Interfaces & Contracts

### Key Classes & Dependencies
```python
from backend.security import (
    authenticate_request,
    CorrelationIdMiddleware,
    RateLimiterMiddleware,
    http_exception_handler,
    generic_exception_handler,
)

# 1. Protect routes in main.py
auth_deps = [Depends(authenticate_request)]
app.include_router(agents_router, prefix="/api/v1/agents", dependencies=auth_deps)

# 2. Middlewares (Order: Correlation -> RateLimiter -> CORS)
app.add_middleware(RateLimiterMiddleware)
app.add_middleware(CorrelationIdMiddleware)

# 3. Global error handlers
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)
```

---

## 4. Invariant Rules & Guardrails
1. **No Sensitive Data in Logs**: Never log plaintext API keys, authorization tokens, or raw credentials.
2. **Deterministic Correlation**: Every response header MUST include `X-Correlation-ID`.
3. **Health Check Immunity**: Never apply rate limits or authentication blockers to `/health`.
4. **Structured Error Consistency**: All error responses must adhere to `{ "detail": "...", "correlation_id": "...", "status_code": ... }`.
