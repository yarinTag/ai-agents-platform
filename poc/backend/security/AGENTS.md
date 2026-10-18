# AGENTS.md - Security & Production Hardening Service

## 1. Service Identity & Mission
The **Security & Production Hardening Service** (`poc/backend/security/`) enforces security boundaries, request authentication, JWT token lifecycle, rate limiting, request correlation tracking, and uniform exception responses across the AI Agents Platform API.

---

## 2. Core Capabilities & Specializations

* **JWT & Password Security Provider (`tokens.py`)**:
  * Pure standard-library implementation using HMAC-SHA256 and PBKDF2 for zero-dependency supply chain safety.
  * Issues and validates signed HS256 JWT access tokens (`create_access_token`, `decode_access_token`).
  * Enforces salted password hashing (`hash_password`, `verify_password`).
* **Multi-Tenant Authentication & Scoping (`auth.py`)**:
  * `authenticate_request`: Validates Bearer JWT tokens or API keys (`PLATFORM_API_KEY`). Unauthenticated requests are rejected with HTTP 401. Exempts public health, auth onboarding, and webhook endpoints.
  * `get_authorized_scope`: Computes authorized tenant organization and department IDs from user claims or database records.
  * `get_current_org_id`: Extracts current tenant organization ID from request state.
  * `get_current_user_optional`: Extracts user claims from request state if present.
  * `require_org_admin`: Dependency enforcing that the authenticated user possesses the `ORG_ADMIN` role; raises HTTP 403 otherwise.
  * `X-Department-ID`: Honors the `X-Department-ID` request header override if the department belongs to the user's authorized scope.
* **Rate Limiting & DoS Protection (`rate_limiter.py`)**:
  * `RateLimiterMiddleware` implements sliding-window in-memory throttling per client IP.
  * Default threshold: **2000 requests per minute** (configurable via `PLATFORM_RATE_LIMIT`).
  * Exempted routes: CORS pre-flight `OPTIONS`, `/health`, `/docs`, `/redoc`, `/openapi.json`, and the persistent SSE event stream (`/api/v1/events/stream`).
  * Rejects traffic exceeding capacity with HTTP 429 (`Too Many Requests`) and `Retry-After` header.
* **Request Correlation Tracking (`correlation.py`)**:
  * `CorrelationIdMiddleware` assigns a unique `X-Correlation-ID` (UUID) to every incoming request.
  * Injects correlation IDs into response headers and Python logging context for distributed tracing.
* **Structured Exception Handling (`errors.py`)**:
  * Uniform error payload formatting (`http_exception_handler` and `generic_exception_handler`).
  * Masks internal stack traces and database errors in production while logging full diagnostics.

---

## 3. Interfaces & Contracts

### Key Classes & Dependencies
```python
from poc.backend.security import (
    authenticate_request,
    require_org_admin,
    get_authorized_scope,
    get_current_user_optional,
    get_current_org_id,
    create_access_token,
    decode_access_token,
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
3. **Health & SSE Immunity**: Never apply rate limits to `/health` or persistent SSE connections (`/api/v1/events/stream`).
4. **Structured Error Consistency**: All error responses must adhere to `{ "detail": "...", "correlation_id": "...", "status_code": ... }`.

---

## 🔄 Mandatory `AGENTS.md` Synchronization Rule

> [!IMPORTANT]
> Whenever any security logic, token structure, auth dependency, rate limit configuration, or error handling in `poc/backend/security/` is modified, the developer or agent **MUST** update this `AGENTS.md` file within the **SAME commit**.
