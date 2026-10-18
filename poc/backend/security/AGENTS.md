# AGENTS.md - Security, Cryptography & Zero-Trust Gateways

## 1. Service Identity & Mission
The **Security & Production Hardening Architecture** (`poc/backend/security/`, `poc/shared/envelope_crypto.py`, `poc/gateways/`, `poc/persistence_modules/postgres_rls.py`) enforces defense-in-depth across Phases 0–3 of the AI Agents Platform. Every control-plane route, subprocess launch, tenant secret, MCP tool invocation, outbound network request, and LLM inference call operates under a **Fail-Closed Zero-Trust** posture.

---

## 2. Phase 0–3 Security Posture Overview

### Phase 0: Control-Plane Hardening & Subprocess Guard (`poc/backend/security/`)
* **Fail-Closed Authentication (`auth.py`)**:
  * `verify_production_security_posture()` raises `RuntimeError` at startup if `is_production_env()` is `True` (`ENV=production` or `PLATFORM_ENV=production`) and either `PLATFORM_API_KEY` or `PLATFORM_JWT_SECRET` is unset or set to a known default (`""`, `"default"`, `"changeme"`, `"secret"`).
  * `authenticate_request` validates signed JWT Bearer tokens (`decode_access_token`) or constant-time `hmac.compare_digest` API keys. If `PLATFORM_API_KEY` is unconfigured in production, requests fail closed with HTTP `503`.
* **JWT & Token Signing (`tokens.py`)**:
  * Issues and verifies HMAC-SHA256 JWT access tokens carrying `sub`, `email`, `org_id`, `role`, and `exp`. Rejects default secrets in production.
* **Subprocess Environment Sanitization (`subprocess_guard.py`)**:
  * `build_sanitized_subprocess_env()` never passes `os.environ` directly to child processes. It copies only safe OS fundamentals (`PATH`, `SYSTEMROOT`, `TEMP`, `TMP`, `HOME`, `LANG`) and explicitly allowed non-secret runtime variables (`SANDBOX_RUN_TOKEN`, `run_token`, `LLM_PROXY_URL`, `MCP_GATEWAY_URL`, `EGRESS_PROXY_URL`), stripping any key containing `SECRET`, `TOKEN`, `KEY`, `PASSWORD`, `DATABASE_URL`, or `PLATFORM_API_KEY`.
  * `validate_agent_execution_flags()` raises `PermissionError` if `dangerously_skip_permissions=True` is requested when `inside_isolated_sandbox=False`.
* **Correlation Tracking, Rate Limiting & Error Masking (`correlation.py`, `rate_limiter.py`, `errors.py`)**:
  * Assigns deterministic `X-Correlation-ID` headers, enforces per-IP sliding-window rate limits (HTTP `429`), and masks internal stack traces in error responses.

### Phase 1: Per-Tenant Envelope Cryptography & Ingress Sanitization (`poc/shared/`)
* **`EnvelopeCryptoManager` (`poc/shared/envelope_crypto.py`)**:
  * Encrypts all tenant secrets at rest (`mcp_connectors.encrypted_config`, `org_llm_keys.encrypted_key`) using AES-256-GCM authenticated encryption (with a zero-dependency stdlib CTR + HMAC-SHA256 Encrypt-then-MAC fallback).
  * Derives per-organization Data Encryption Keys (DEKs) bound to `org_id` as Associated Authenticated Data (AAD), wrapped under a rotatable master key (`PLATFORM_MASTER_KEY`). Cross-tenant decryption attempts (`org_b` attempting to decrypt `org_a` ciphertext) fail closed with `ValueError`.
  * `hash_invite_token()` hashes single-use invitation tokens with SHA-256 before persistence so plaintext invite tokens are never stored in SQLite/PostgreSQL.
* **Untrusted Ingress Sanitizer (`poc/shared/payload_sanitizer.py`)**:
  * `sanitize_untrusted_ingress()` strips hidden HTML comments, system/developer role-override prompt injections, and suspicious Base64 instruction payloads from webhook/channel inputs, wrapping sanitized content in `<untrusted_external_data source="...">` delimiters.

### Phase 2: Out-of-Process Runtime Security Gateways (`poc/gateways/`)
* **`SecretsBroker` & `ScopedRunToken` (`poc/gateways/secrets_broker.py`)**:
  * Issues short-lived cryptographic `ScopedRunToken` (`rtk_<random>`) bound to `org_id`, `department_id`, `run_id`, `user_id`, `allowed_mcps`, `allowed_tools_by_mcp`, and `egress_allowlist`.
  * Sandboxes never receive raw upstream credentials (GitHub PATs, Slack/Telegram tokens, or BYOK LLM keys). Upstream secrets remain inside `SecretsBroker` and are retrieved exclusively by trusted gateways via `get_upstream_secret(run_token, connector_id)`.
  * Supports instant revocation by token, `run_id`, or `org_id` (`/api/v1/gateways/kill-switch`).
* **`RuntimeToolGateway` (`poc/gateways/tool_gateway.py`)**:
  * Intercepts every MCP/tool call (`intercept_tool_call`).
  * Resolves `org_id`, `department_id`, `run_id`, and `user_id` strictly from the validated `ScopedRunToken`; strips and flags any model-supplied identity fields in `arguments` (`UNTRUSTED_IDENTITY_ARG_KEYS`).
  * Verifies real-time database permissions via `db.check_department_mcp_permission(department_id, connector_id, tool_name)`.
  * Hard-blocks destructive tools (`delete_repo`, `delete_organization`, `drop_database`, `destroy_infrastructure`) and enforces Human-in-the-Loop (`PENDING_APPROVAL`) gating on external write tools (`create_pull_request`, `merge_pull_request`, `push_files`, `send_message`, etc.) when required.
* **`EgressProxy` (`poc/gateways/egress_proxy.py`)**:
  * Default-deny outbound network proxy (`check_egress_request`).
  * Hard-blocks cloud metadata endpoints (`169.254.169.254`, `fd00:ec2::254`, `metadata.google.internal`, `100.100.100.200`), loopback/RFC1918 private networks (`localhost`, `127.0.0.1`, `10.*`, `192.168.*`, `172.16-31.*`), unapproved domains not in `ScopedRunToken.egress_allowlist`, and payloads exceeding `1_048_576` bytes (1 MiB).

### Phase 3: LLM Proxy, Append-Only Audit Trail & PostgreSQL RLS (`poc/gateways/llm_proxy.py`, `poc/persistence_modules/postgres_rls.py`)
* **`LLMProxy` (`poc/gateways/llm_proxy.py`)**:
  * Validates `ScopedRunToken`, checks model allowlists and prompt character ceilings (`100_000` chars), enforces real-time department `HARD_STOP` budgets (`db.check_department_budget`) BEFORE dispatching inference, and redacts PII/secrets (`[REDACTED_EMAIL]`, `[REDACTED_SECRET]`).
* **Immutable Append-Only `audit_logs` & PostgreSQL RLS (`poc/persistence_modules/postgres_rls.py`)**:
  * Installs SQLite `BEFORE UPDATE` and `BEFORE DELETE` triggers (`trg_audit_logs_immutable_update`, `trg_audit_logs_immutable_delete`) that abort any mutation or deletion on `audit_logs`.
  * Records structured security events (`record_security_audit_event`) with deterministic SHA-256 `params_hash` (`compute_params_hash`) so raw credentials are never written to audit logs.
  * `generate_postgres_rls_migrations()` generates `ENABLE/FORCE ROW LEVEL SECURITY` policies using `current_setting('app.org_id', true)` across all 8 multi-tenant tables (`organizations`, `departments`, `users`, `department_members`, `department_mcp_access`, `workflows`, `workflow_executions`, `audit_logs`).

---

## 3. Invariant Security Rules
1. **Zero Raw Secrets in Sandboxes or Logs**: Never pass raw API keys, PATs, or bot tokens into subprocess environments, prompt payloads, or `audit_logs`.
2. **Never Trust Model-Supplied Identity**: Always derive `org_id`, `department_id`, `run_id`, and `user_id` from `ScopedRunToken` or verified JWT claims.
3. **Fail-Closed Everywhere**: Any missing token, expired TTL, cross-tenant AAD mismatch, unallowed domain, or exceeded `HARD_STOP` budget must immediately raise `PermissionError` / `ValueError` or return HTTP `401`/`403`/`503`.
