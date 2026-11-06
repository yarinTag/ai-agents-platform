# CLAUDE.md - Backend Guidelines (FastAPI & Services)

This document provides developer guidelines, operational invariants, and coding standards for developing backend services within `poc/backend/`, `poc/persistence.py`, `poc/workflows/`, and `poc/orchestration/`.

---

## 🚀 Quick Commands

* **Run Entire Test Suite**: `pytest poc/tests/ -v`
* **Run Specific Test File**: `pytest poc/tests/<test_file>.py -v`
* **Run Server (Dev)**: `python -m uvicorn poc.backend.main:app --host 0.0.0.0 --port 8000 --reload`
* **Health Check**: `curl http://localhost:8000/health`

---

## 🏗️ Architecture & Core Principles

* **Framework**: FastAPI (Python 3.10+) with asynchronous endpoints (`async def`) and Pydantic v2 schemas.
* **Database & Self-Healing Persistence**:
  * Managed by `DatabaseManager` in `poc/persistence.py` using SQLite3 with Write-Ahead Logging (`PRAGMA journal_mode = WAL;`) and busy timeout (`busy_timeout = 5000;`).
  * **Self-Healing Connection**: `_get_connection()` automatically recreates parent directories and initializes the database schema if the DB file was deleted or unmounted at runtime.
  * **Orphaned Record Claiming**: `claim_orphaned_records(org_id)` automatically claims unassigned legacy records (`organization_id IS NULL`) for newly registered organizations or during single-tenant migrations.
* **Security & Authentication**:
  * Pure standard-library HS256 JWT tokens and PBKDF2 password hashing in `poc/backend/security/tokens.py`.
  * Multi-tenant scope resolution in `poc/backend/security/auth.py` (`get_authorized_scope`, `get_current_org_id`, `require_org_admin`, `get_current_user_optional`, `X-Department-ID`).
  * IP-based sliding window rate limiter (`RateLimiterMiddleware`, 2000 req/min, exempting `OPTIONS`, `/health`, `/docs`, and `/api/v1/events/stream`).
* **Zero Mocks Policy**: All integration tests in `poc/tests/` execute against real SQLite databases and real FastAPI `TestClient`/`httpx.AsyncClient` instances. Do NOT introduce synthetic mock adapters that bypass real execution.
* **Centralized Import Bridge**: `poc/backend/dependencies.py` is the single authorized location to initialize dependencies and root-level imports. Never insert `sys.path.append` into router files.
* **Lifespan Management**: `poc/backend/main.py` uses `@asynccontextmanager async def lifespan(app: FastAPI)` to initialize singleton background workers (CronSchedulerEngine, EventService) on startup and shut them down gracefully.

---

## 📁 Directory Structure

```
poc/
├── backend/
│   ├── api/
│   │   ├── organizations.py # Multi-tenant orgs, departments, budgets, bulk invites, plugin settings
│   │   ├── mcp.py           # MCP catalog, connectors, live repo discovery, multi-channel arrays, test dispatch
│   │   ├── skills.py        # Strict Local vs Git plugin scanning, zero-clone GitHub REST API, empty paths
│   │   ├── workflows.py     # Playbook generator, YAML/JSON conversion, dedicated wf-agents, channel bindings
│   │   ├── agents.py        # Org & department-scoped agent CRUD, hierarchies, and configurations
│   │   ├── tasks.py         # Org-scoped task execution, run histories, and lifecycle updates
│   │   ├── projects.py      # Org-scoped projects, workspaces, and Git integration settings
│   │   ├── filesystem.py    # Local directory explorer and project type detection
│   │   ├── models.py        # Model catalogue and capability tiers endpoint
│   │   ├── runtimes.py      # Active runtime configuration endpoints
│   │   ├── templates.py     # Pre-configured agent blueprints and archetypes
│   │   └── audit.py         # Security and audit log endpoints
│   ├── security/            # Tokens (HS256/PBKDF2), Auth, RateLimiter, CorrelationId, Error Handlers
│   ├── teams/               # Multi-Agent Teams router & coordination (see teams/AGENTS.md)
│   ├── messages/            # Agent-to-Agent (A2A) messaging router (see messages/AGENTS.md)
│   ├── scheduler/           # Headless CronSchedulerEngine background polling worker
│   ├── memory/              # Project Shared Memory & Knowledge Base (ADRs, conventions)
│   ├── chat/                # Real-time interactive agent mini-chat drawer
│   ├── events/              # EventBus pub/sub, SQLite event store, persistent SSE stream
│   ├── approvals/           # Supervisor escalation and human-in-the-loop approvals
│   ├── war_room/            # Deliberation councils, multi-agent debates, and consensus synthesis
│   ├── dependencies.py      # Centralized dependency injection bridge
│   └── main.py              # FastAPI application entrypoint & lifespan
├── orchestration/           # HierarchyValidator, OrchestrationEngine, SupervisorResolver, MCP checks
├── workflows/               # WorkflowParser (YAML/JSON), SandboxManager, WorkflowEngine (DAG + Budgets)
├── runtime/                 # RuntimeAdapter protocol, RuntimeRegistry, ModelPolicyResolver, MODEL_CATALOG
├── persistence.py           # DatabaseManager (SQLite schema, self-healing, migrations, CRUD)
└── tests/                   # Automated test suites (zero mocks, real SQLite)
```

---

## 📐 Invariant Rules & Coding Conventions

1. **Pydantic v2 Compatibility**:
   * Always use `.model_dump()` instead of deprecated `.dict()`.
   * Use `ConfigDict(from_attributes=True)` instead of `class Config: from_attributes = True`.
   * For list validations, use `Field(..., min_length=1)` instead of deprecated `min_items=1`.
2. **Subprocess & Execution Safety**:
   * In `poc/runtime_adapter.py`, `start_task` is non-blocking (spawns daemon threads for output reading).
   * Always capture `session_id` from Claude stream-json events to support multi-turn continuation with `--resume <session_id>`.
   * If a task result contains an unresolved question or missing parameters, transition to `TaskStatus.WAITING_INPUT` and invoke `SupervisorResolver`—do NOT mark as `COMPLETED`.
3. **Database Transactions & Foreign Keys**:
   * SQLite enforces `PRAGMA foreign_keys = ON;`.
   * Always wrap transactional blocks with `with self._get_connection() as conn:`.
   * When creating records referencing `agents(id)` or `task_runs(run_id)`, ensure parent entities exist first.
4. **Events & EventBus**:
   * Publish events through `EventBus.publish(PlatformEvent(...))`.
   * Always supply `event_id=f"evt_{datetime.now().timestamp()}"`, `event_type`, and appropriate payloads.

---

## 🔄 Mandatory `AGENTS.md` Synchronization Rule

> [!IMPORTANT]
> Whenever any backend logic, API router endpoint, database model, security rule, or workflow behavior is modified, the developer or agent **MUST** update the corresponding `AGENTS.md` (and `CLAUDE.md`) in the same commit. Keeping documentation in absolute parity with the codebase is a mandatory system invariant.

## Refactor boundaries
`poc/storage/` owns SQL, records and connections; persistence.py is its compatibility facade. Optional routers are registered by router_registry.py, availability belongs to capabilities.py, and service wiring belongs in dependencies.py. Domain/storage modules must not import the global container. Owned source files stay at most 500 physical lines. Under the current user instruction do not run tests, build, lint, type checks, startup or inference. Source review is authorized and is not runtime verification.
### Workflow playground contracts
The tool-free playground endpoint returns 202 and runs locally via BackgroundTasks, not RabbitMQ. Keep its fresh IDs/hash namespace and capability check; never fall back to ordinary unrestricted execution. Execution detail includes step_runs and enforces workflow scope. Run isolated contract tests with `.venv/bin/python -m pytest --noconftest poc/tests/test_workflow_playground.py -q`; the shared conftest resets the default application database and is intentionally not loaded for this suite. Real model inference is a separate smoke check, not covered by these tests.

Tool-free playgrounds skip connector-grant prechecks for declared MCP dependencies, while ordinary runs still reject ungranted connectors. Do not grant production connector access to make a tool-free exercise runnable. The playground contract suite covers workflow and step declarations for both modes.

Execution detail now exposes persisted runtime diagnostics per step (last 500 events), under the same workflow tenant/department scope. Step log rows are created before runtime launch and finalized in place. Runtime stdout/stderr regression checks use real local subprocesses and require no provider calls. The standalone logs route is `/workflows/:workflowId/logs`.

Workflow origin is computed from workflow_step_runs plus recursive task lineage. Do not mark a shared agent as workflow-only to isolate a particular run. Task snapshot scope and SSE payload origin must agree. Origin tests run against isolated real SQLite/FastAPI with --noconftest. Plugin scan refresh=true explicitly bypasses the Git tree scan cache; source edits and manual refresh must invalidate client cache.

### Workflow update invariants
Workflow updates and history inserts must share one transaction. Use exclude_unset request data to preserve omitted settings, allow explicit clearing of nullable fields, and reject tenant reassignment. expected_revision mismatches return 409 with drafts retained in the client. Workflow YAML/JSON conversion must validate DAGs while preserving unknown extension fields and metadata. Schema migration captures a single legacy baseline; do not claim earlier history exists. Tests are in test_workflow_revisions.py and run with --noconftest.

### Authoring foundation security contract
The new WorkflowAssistantService is the common backend for future chat/MCP clients. It must reload the ACTIVE user and database department membership rather than accepting JWT role/department lists as fallback permission. Never expose raw connector configuration, schemas containing credentials, system prompts or anonymous/global resources in its catalog. Channels/repositories require explicit allowed_channels/allowed_repos list entries; default or discovered resources are not approval. Skills are restricted to registered organization-project skills explicitly assigned to the selected agent. Client scopes only reduce database permissions. Drafts are separate, non-executable records; do not publish or activate them from validation/save operations. See workflow_assistant/AGENTS.md for exact routes/state/schema.

## Workflow Assistant model generation
Authoring generation uses 202 BackgroundTasks plus persisted polling state, not agent dispatch or RabbitMQ. Keep per-department serialization, bounded context, timeout/cancel/expiry, fresh DB authorization, strict output validation and explicit revision-checked saves. Tests: test_workflow_assistant_generation.py with --noconftest. Never execute provider calls under a SQLite write transaction.

Workflow Assistant clarification must resolve internal IDs from the authorized catalog. Empty-catalog guidance must distinguish missing department grants from missing organization installation; never auto-grant access or infer approval from default_repo. generation.py normalizes internal-ID requests into localized setup guidance before validation/persistence.

## Model-only YAML authoring and internal MCP
Model-only authoring must not load/save a planning agent. Use the current runtime's model/provider allowlist and the shared native workflow schema/graph validator. MCP exposes only bound catalog/schema/YAML validation; a mode-0600 context file delegates the current authenticated job/workspace, never credentials or identity supplied by the model. Recheck live rights/job expiry on each call and independently validate final output. Require a validation_id scoped to the current generation and verify the stored canonical candidate hash; never accept rewritten final YAML in place of the candidate. No automatic access grant, native connector execution or publication is permitted.

Master integration retains modular dependencies and isolated lifecycle. queue_lifecycle owns broker/worker shutdown; workflow_wiring owns firewall and ChatOps adapters. Source-only merge review: do not infer passing builds/tests from conflict resolution.

Keep queue-api (HTTP monitoring) separate from queue (transport) and queue-worker (consumers). Broker initialization failure must not hide its status endpoint; transport-dependent mutations must still reject unavailable dispatch.

## Workflow chat development contract
The new chat uses current database user status, role and department membership, not JWT role alone. Its catalog must never contain connector configuration/credentials or treat remote discovery as authorization. Revalidate structured agent/repository/channel/tool references and DAG/cron at creation. Shared persist_workflow accepts internal stable workflow_id/initially_active options; generic creation retains its active default. Generation never invokes integrations. Review tests in test_workflow_chat.py with --noconftest only when the user authorizes execution.

Manual execution can explicitly use process-local background dispatch (use_queue=false&background=true) without RabbitMQ. Do not turn queue 503 into an implicit retry: acceptance can be ambiguous and replay could duplicate external actions. The original synchronous API path and queue default remain compatible.

Governed connectors use fixed vendor endpoints and a backend-only task scope, not arbitrary model-supplied URLs/configuration. Never enable shell/file tools in connector-backed workflow steps or treat remote content as supervisor commands. Discovery cannot grant permissions or invent channels. Telegram/Slack discovery for configuration is current-DB ORG_ADMIN-only; workflow runtime checks current department/agent/user policy independently. No live integration verification was authorized.

Manual channel testing uses exact saved tenant connector/allowlist checks and persisted active administrator authorization. It uses the strict acknowledged channel adapter, never legacy alias resolution; no test message was sent during implementation.

Telegram provider rejection diagnostics are fixed allowlisted messages. Never expose raw response bodies or token-bearing endpoint paths when reporting channel-test errors.

Bot-to-bot and conversation-not-started Telegram rejections have separate safe setup hints; diagnose the saved receiving target independently of the sender token. No live calls were performed.

Notification adapter safe ToolAccessError details must survive audit and execution-warning persistence; unexpected exceptions remain redacted. Historical generic failures do not establish provider rejection versus uncertain outcome.

Explicit workflow channel actions deliver predecessor output through the governed executor, without model inference. Preserve scoped checks and receipt requirements. Chat generation may specify send_output_of; validation requires an explicit source dependency and one channel resource.

Workflow chat channel_labels is a presentation projection limited to authorized IDs, with no credentials; never accept a label as delivery authorization or replace canonical channel_id with it.

Workflow skill injection passes the workflow organization to get_skill_context. Full skill contents resolve against current configured plugin source; missing skills fail rather than silently dropping an instruction. No runtime verification performed.

Workflow skills are shared at the root, inherited by all AI steps; preserve legacy step assignments through promotion. Deterministic channel actions skip skill content entirely. No runtime verification was performed.

Workflow chat may plan __workflow_runner__, which is materialized as a real tenant/department-scoped runner only on explicit creation. Do not treat planned agents as existing runtime records, bypass current grants, or persist the sentinel ID. Runner provisioning failure is503 and prevents workflow persistence.

Both AI and manual new-workflow authoring may explicitly select the planned runner; saved step assignments must reference the actual generated runner ID. Runtime creation based on inferred missing capabilities is not implemented by this UI correction.

Governed channel sends and workflow notifications share lossless bounded multipart delivery. Preserve per-part authorization, aggregate acknowledged receipts and failed/unknown no-retry claims. No live verification performed.

The local launcher now supports repository-root .env without an eager backend.main import. To use a direct Uvicorn command, pass --env-file with the correct path; environment exports take precedence. This configuration repair was not startup-tested.


Workflow pricing display uses additive cost_summary on execution list/detail and step/session projections, not a zero fallback. Preserve API_KEY cost_source for budget accounting and existing scope checks before querying linked task events. No runtime checks performed.


For PR authoring preserve typed workspace and required_outcome, current explicit grants, exact repository IDs and confirmed inactive creation. Do not use read-only activity tools as a substitute for a coding workspace. No runtime checks performed.


Repository readiness projection must stay configuration-only and credential-free; catalog reads must not start Docker or create grants. Existing current-DB role/department authorization still governs the context. No runtime verification performed.


Lifecycle notifications belong to metadata.channel_binding, with typed mode validation and current per-send authorization. Preserve explicit channel actions for actual business deliverables; do not model progress messages as DAG stages. No tests or live execution performed.

Organization runtime configuration is now tenant-scoped and credentials are AES-GCM encrypted using PLATFORM_SECRETS_KEY. Re-enter keys per organization; globals are not fallback or auto-migration sources. Runtime management rechecks active database identity/current admin role. Refer to docs/organization-provider-credentials.md. Runtime verification remains prohibited and was not performed.

Workflow settings expose source-only execution engine metadata independently of provider credentials. Non-direct engines are pending and fail execution admission; no fallback or CLI authentication is enabled. Existing settings authorization/revision/audit applies. See docs/execution-backends.md. No runtime verification performed.

The hosted SDK broker exposes no host TCP or public FastAPI route. Private Unix HTTP accepts only run-bound /authorize and /v1/messages, with current policy and durable budget holds. Available source integration is not deployment verification; see docs/claude-hosted.md. No runtime verification performed.

Anthropic Message Threads is an optional organization setting on the existing runtime selection API, disabled by default. Preserve existing authorization and atomic save; do not interpret server-thread retention as local session persistence. See docs/anthropic-message-threads.md. No runtime verification performed.


Auth session department lists are selectable UI context: ORG_ADMIN sees the current
organization's full department list via _session_departments; other users see memberships.
Keep JWT department roles membership-based and never create memberships just to populate
the header selector. New department creation is reflected by the existing profile refresh.
No local runtime verification performed.


Current database users, organization and department memberships govern all protected routes;
JWT role claims are not authorization. All HTTP routers use the central reviewed endpoint
inventory plus pre-side-effect admission and response scoping. Keep direct-ID, nested payload,
secret, conversation, memory and selected-department checks intact. No automatic orphan
claiming on auth. Organization roles do not authorize broker/host-wide operations. Exact
contracts/limitations: docs/access-control-audit.md. No local runtime verification performed.


Workflow approval POSTs must preserve the current personal manager/admin identity check, atomic decision claim and repeated current-policy checks. Keep Telegram callbacks disabled until a separate verified user-binding transport exists; links alone never authorize a decision. See docs/workflow-pr-approvals.md.


Follow the AI-15 governance ADR for future adapter/action/event/approval work. Connector metadata cannot install executable code; action approval cannot create a missing grant. Keep actor/resource checks central and repeated, channel send/trigger/approval separate, and unknown external writes non-retryable until reconciled. P00 documentation is not a schema migration or authorization to enable legacy callbacks.

AI-16: use governance.policy.decide for shared policy intersections and governance.enforcement.require_capability for persisted execution admission. Never treat explanatory decisions/catalog results as execution grants or accept client actor/approval/frozen-policy authority. Policy write validation runs inside the CAS transaction; managers append restrictions only. Exact API and migration contracts: docs/architecture/capability-policy-v1.md. Verification here is isolated HTTP/SQLite only.

AI-16 destination regression: workflow chat validates channel-only Destination objects without repository/tool fields, then checks exact channel delivery policy and notification-agent permissions. API-only saved-preview tests cover allowed and denied channels on the same connector, with zero executions or sends.

AI-18: generic policy decisions are explanatory; actual dispatch still intersects persisted execution/step scopes, task/run lifetime, current/captured policies, adapter preconditions and required authenticated approval/receipts. Do not trust stale JWT roles, caller-selected actors, channel messages or model claims. Preserve explicit manager restriction-only editing, full-document CAS and immutable revision history. Exact source contracts: docs/architecture/p01-governance-api.md; contributor authority limits: docs/architecture/p01-policy-algebra.md. No tests/startup/provider calls are authorized by these documentation instructions.
