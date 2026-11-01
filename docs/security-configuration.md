# Security configuration (required environment)

The hardening release fails closed. Set these variables **before** upgrading a
deployment. Missing values stop the server, or disable only the affected
integration, rather than falling back to an insecure default.

| Variable | Required when | Effect if missing |
|---|---|---|
| `JWT_SECRET_KEY` (≥ 32 chars) | Always, unless `PLATFORM_DEV_MODE=1` | The server refuses to start. The old built-in fallback key is gone. |
| `PLATFORM_DEV_MODE=1` | Local development only | Signs tokens with a random per-process key: tokens stop working on restart and across worker processes. |
| `PLATFORM_CORS_ORIGINS` | Any browser origin other than `http://localhost:5173` / `http://127.0.0.1:5173` | The browser blocks dashboard requests from that origin. `*` is ignored. |
| `PLATFORM_API_KEY_ORG_ID` | `PLATFORM_API_KEY` is used | API-key requests are rejected (401). The key acts as ORG_ADMIN of this one organization only. |
| `PLATFORM_DEV_ORG_ID` | `ALLOW_UNAUTHENTICATED_DEV=true` (which now also needs `PLATFORM_DEV_MODE=1`) | Open dev access is rejected. |
| `TELEGRAM_WEBHOOK_SECRET` | Telegram approval buttons | `/api/v1/approvals/telegram-callback` returns 503. Register it with `setWebhook(secret_token=...)`. |
| `SLACK_SIGNING_SECRET` | Slack approval buttons | `/api/v1/approvals/slack-callback` returns 503. Use the Slack app's signing secret. |

## What changed

- **JWT:** no hardcoded secret. Malformed tokens are rejected instead of causing a 500.
- **Credentials in URLs:** `?token=` is accepted only on `GET /api/v1/events/stream`, because browser `EventSource` cannot send headers. `?api_key=` is no longer accepted. API keys are compared in constant time.
- **No unscoped callers:** API-key and open-dev requests now carry a bound organization. Every authenticated request therefore has an organization, so router checks written as `if org_id and ...` always run.
- **Service callers:** API-key/dev claims have no user (`sub`). Workflow runs they trigger are service executions, and user-session endpoints such as `/auth/me`, workflow chat and channel discovery reject them. `/auth/me` can no longer self-heal a user from them.
- **Departments:** membership comes from the database only; the stale JWT `departments` fallback was removed. `X-Department-ID` only selects among already-authorized departments, so an ORG_ADMIN cannot add another organization's department. `GET /api/v1/organizations/departments` ignores any foreign `organization_id` and returns 403 for it.
- **Live events:** `/api/v1/events/stream` (live and replay) sends only events whose task, agent or project belongs to the caller's organization. Non-admins also only see department-scoped events for their own departments. Events that can't be attributed to an organization are dropped. `/system/stats` is limited to the organization, and `/system/health` no longer reports cross-tenant counts.
- **Approvals:** Telegram callbacks must carry the secret token header. Slack callbacks must carry a valid `v0` HMAC signature less than 5 minutes old.
- **Permission grants:** resuming a task no longer turns off permission checks because the answer contains words like "ok", "yes" or "allow". Only an explicit "approve" decision through the approvals API passes `grant_permissions=True`.
- **CORS:** explicit origin list; never `*` combined with credentials.

## Not changed yet (known follow-ups)

- Records with a NULL `organization_id` (legacy rows) are still readable by any organization in some routers, for example `if org_id and resource.organization_id and ...`. Claim them with `claim_orphaned_records` before running multiple tenants.
- Routes still trust the JWT `role` without reloading it from the database. A demoted admin keeps admin rights until the token expires (24h).
- Chat members who can see an approval message can press its buttons. Responders are not yet mapped to platform approvers.
- The rate limiter is per process and keyed by client IP.

Tests: `poc/tests/platform_test_env.py` is loaded through pytest `addopts`. It sets `PLATFORM_DEV_MODE=1` for test runs only and works with `python -m pytest`. No tests, builds or startup were run for this change.
