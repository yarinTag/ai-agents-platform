# CLAUDE.md - AI Agents Platform Root Repository Guide

Welcome to the **AI Agents Platform** codebase. This repository implements an enterprise multi-tenant autonomous agent orchestration and governance platform featuring a zero-trust runtime security gateway suite, multi-provider BYOK direct LLM execution, modular persistence, virtual pixel office, real-time collaboration war room, and DAG workflow engine.

---

## 🧭 Monorepo Architecture & Parts 1–5 Module Map

### 1. Shared Layer (`poc/shared/`)
Centralized, zero-duplication cross-cutting primitives used across Backend, Workflows, Runtime, and Gateways:
* **`validators.py`**: Input validation, identifier sanitization, and schema guardrails.
* **`notifications.py`**: Unified outbound notification dispatcher (`dispatch_channel_message`, `dispatch_workflow_completion_notification`) supporting structured `WorkflowNotificationPolicy` modes (`FINAL_ONLY`, `START_AND_END`, `EVERY_STEP`, `ON_FAILURE_ONLY`) and per-step `notify_on_complete` summaries across Telegram and Slack.
* **`service_registry.py`**: Fault-tolerant `ServiceRegistry` (`ServiceSpec`, `mount_all`) that dynamically mounts FastAPI routers and isolates disabled or degraded services (`DISABLED_SERVICES`) without crashing the control plane.
* **`envelope_crypto.py`**: Per-tenant Envelope Encryption (`EnvelopeCryptoManager`) using AES-256-GCM (with deterministic stdlib AEAD Encrypt-then-MAC fallback), per-organization HKDF Data Encryption Keys (DEKs) wrapped by a rotatable master key (`PLATFORM_MASTER_KEY`), and SHA-256 `hash_invite_token()`.
* **`payload_sanitizer.py`**: Untrusted external ingress sanitizer (`sanitize_untrusted_ingress`) that strips prompt-injection vectors (hidden HTML comments, system/role override directives, Base64 instruction blobs) and wraps external content in `<untrusted_external_data>` tags.

### 2. Modular Persistence (`poc/persistence_modules/`)
Domain-decomposed SQLite (WAL) repository mixins composed into `DatabaseManager` (`poc/persistence.py`), plus production PostgreSQL RLS migration generators:
* **`organizations_repo.py`**: Multi-tenant Organizations and Departments CRUD (`OrganizationRepositoryMixin`).
* **`governance_repo.py`**: Department MCP access matrices, tool-level permissions, and real-time `HARD_STOP` budget enforcement (`GovernanceRepositoryMixin`).
* **`users_repo.py`**: RBAC Users, Department Memberships, and SHA-256 hashed single-use Invitation Tokens (`UsersRepositoryMixin`).
* **`workflows_repo.py`**: Autonomous Workflows, DAG execution records, and channel bindings (`WorkflowsRepositoryMixin`).
* **`llm_keys_repo.py`**: Tenant BYOK LLM API Key vault (`LLMKeysRepositoryMixin`) storing envelope-encrypted keys (`encrypted_key`) for `anthropic`, `openai`, and `nvidia_nim` alongside masked previews, custom `base_url`, and `default_model`.
* **`postgres_rls.py`**: `generate_postgres_rls_migrations()` producing PostgreSQL Row-Level Security (`ENABLE/FORCE ROW LEVEL SECURITY`) policies keyed on `current_setting('app.org_id', true)`, plus `AppendOnlyAuditRepositoryMixin` enforcing immutable `audit_logs` via SQLite `BEFORE UPDATE`/`BEFORE DELETE` triggers and SHA-256 `params_hash`.

### 3. Zero-Trust Sandbox (`poc/sandbox/`)
Hardware/container isolation boundary ensuring agent code never executes with host credentials or unrestricted network access:
* **`models.py`**: Typed `SandboxConfig`, `SandboxInstance`, `ResourceLimits` (CPU, memory, PIDs, read-only rootfs), and execution status models.
* **`protocol.py`**: Abstract `SandboxDriver` protocol for pluggable container/microVM backends.
* **`manager.py`**: `SandboxManager` lifecycle orchestrator enforcing sanitized subprocess environments (`subprocess_guard.py`), non-root execution, and emergency sandbox destruction on kill-switch activation.

### 4. Runtime Security Gateways (`poc/gateways/`)
Out-of-process / control-plane interception layer (`/api/v1/gateways`) mediating all sandbox-to-external interactions:
* **`secrets_broker.py`**: `SecretsBroker` issuing short-lived cryptographic `ScopedRunToken` (`rtk_<random>`) bound to `org_id`, `department_id`, `run_id`, `user_id`, `allowed_mcps`, `allowed_tools_by_mcp`, and `egress_allowlist`. Raw upstream secrets never enter sandboxes.
* **`tool_gateway.py`**: `RuntimeToolGateway` (`intercept_tool_call`) enforcing token validity, stripping model-spoofed identity arguments (`org_id`, `department_id`, `run_id`), verifying real-time department MCP permissions, blocking destructive tools (`delete_repo`, `drop_database`), and gating external write tools (`create_pull_request`, `send_message`, `merge_pull_request`) on Human-in-the-Loop (HITL) approval.
* **`egress_proxy.py`**: Default-deny `EgressProxy` blocking cloud metadata IPs (`169.254.169.254`, `fd00:ec2::254`, `metadata.google.internal`), loopback/RFC1918 private networks, unapproved domains, and outbound payloads exceeding 1 MiB.
* **`llm_proxy.py`**: `LLMProxy` enforcing model allowlists, prompt length ceilings, pre-call department `HARD_STOP` budget checks, and automated PII/credential redaction (`[REDACTED_EMAIL]`, `[REDACTED_SECRET]`).
* **`router.py`**: FastAPI endpoints (`/tokens/issue`, `/mcp/invoke`, `/egress/check`, `/llm/authorize`, `/kill-switch`, `/rls-policies`).

### 5. Multi-Provider Direct LLM Runtime (`poc/runtime/`)
* **`direct_llm_adapter.py`**: `DirectLLMAdapter` implementing the `RuntimeAdapter` protocol for direct HTTPS inference with **Anthropic** (Messages API), **OpenAI** (Chat Completions API), and **NVIDIA NIM** (OpenAI-compatible NIM endpoint). Supports native multi-turn Tool Calling loops routed through `RuntimeToolGateway`, per-organization BYOK key resolution via `LLMKeysRepositoryMixin`, and token/cost telemetry.
* **Additional Runtime Modules**: `RuntimeAdapter` protocol, `RuntimeRegistry`, `ModelPolicyResolver` (logical intelligence tiers), and CLI adapters (`poc/runtime/AGENTS.md`).

### 6. Core Application Services
* **Backend (`poc/backend/`)**: FastAPI control plane, Security (`poc/backend/security/AGENTS.md`), Cron Scheduler, Approvals, Chat, Memory, War Room, A2A Messages (`poc/backend/messages/AGENTS.md`), and Teams (`poc/backend/teams/AGENTS.md`).
* **Frontend (`poc/dashboard/`)**: React 18, Vite, Ant Design v5, TypeScript, Pixel Office Canvas Engine, and MCP/Governance panels (`OrgLLMKeysPanel.tsx`, `WorkflowNotificationPolicyCard.tsx`). See [`poc/dashboard/CLAUDE.md`](poc/dashboard/CLAUDE.md).
* **Orchestration & Workflows (`poc/orchestration/`, `poc/workflows/`)**: Hierarchical task delegation, `SupervisorResolver`, and multi-step DAG workflow engine.

---

## 🏛️ Strict Architectural Laws

1. **<= 250 Lines Per File**: Every newly created or refactored source file MUST remain `<= 250` lines with a single, well-defined responsibility.
2. **Rule of 2 in `poc/shared/`**: Any helper, validator, crypto primitive, sanitizer, or notification dispatcher used by 2 or more modules MUST live in `poc/shared/`—zero copy-pasted logic.
3. **Pluggable Services via `ServiceRegistry`**: All API routers are mounted through `shared.service_registry.service_registry` so individual services can be toggled via `DISABLED_SERVICES` or degrade gracefully without taking down the platform.
4. **Strict UI Design Tokens (`tokens.ts`)**: All frontend components in `poc/dashboard/src/` MUST import and use semantic tokens from `src/shared/theme/tokens.ts` (`tokens.colors`, `tokens.spacing`, `tokens.radii`, `tokens.typography`, `tokens.shadows`). Hardcoded hex colors in component files are strictly forbidden.
5. **Fail-Closed Zero-Trust Security**: Missing/expired tokens, unconfigured production secrets, unauthorized MCP tools, or unknown egress domains MUST immediately raise explicit exceptions or deny access.
6. **Zero Mocks Policy**: All backend tests run against real SQLite databases, real cryptographic primitives, and real FastAPI routers.

---

## ⚡ Primary Verification Workflows

```bash
# 1. Run Backend & Security Gateway test suites (real SQLite, zero mocks)
pytest poc/tests/ -v

# 2. Build Frontend (strict TypeScript compilation & bundle verification)
cd poc/dashboard && npm run build
```
