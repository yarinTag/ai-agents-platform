# AGENTS.md - Backend Architecture & Service Guide

## 1. Service Identity & Mission
The **Backend Service** (`poc/backend/` and `poc/persistence.py`) forms the core server application for the AI Agents Platform. Built on FastAPI and SQLite (WAL mode), it coordinates multi-tenant organization administration, department budgeting guardrails, Model Context Protocol (MCP) integrations, plugin skill discovery, agent task execution, and real-time event distribution.

---

## 2. Core Architecture & Modules

### 1. REST API Layer (`poc/backend/api/`)
* **Organizations (`organizations.py`)**: Multi-tenant organization CRUD, department budgets with `HARD_STOP` policy, bulk member invitations with domain validation, role assignments (`ORG_ADMIN`, `MANAGER`, `OPERATOR`, `MEMBER`), and organization plugin settings (`plugins_source_mode`, `plugins_local_path`, `plugins_git_repo`).
* **MCP Hub (`mcp.py`)**: Catalog of standard MCP servers (`CATALOG_MCP_SERVERS`), connector configuration with credential masking, live GitHub/GitLab remote repository discovery across public and private repos (`/discover-resources`), multi-channel destination arrays (`allowed_channels`) for Slack and Telegram, live test dispatches (`/test-channel-message`), and department-level tool whitelisting.
* **Plugins & Skills (`skills.py`)**: Strict separation between local folder scanning and remote Git repository scanning, empty path safety (clean 0 skills without fallback), and 100% in-memory zero-clone GitHub REST API tree/blob scanning (`_scan_git_repo_via_api`, `_GIT_TREE_SCAN_CACHE`).
* **Workflows (`workflows.py`)**: Declarative YAML/JSON playbooks, AI playbook generator (`/generate`), format conversion (`/convert-format`), automatic dedicated runner agent provisioning (`wf-agent-{id}`), and Slack/Telegram channel bindings (`/{workflow_id}/channel-binding`).
* **Agents (`agents.py`)**: Organization- and department-scoped agent configurations, role archetypes, and reporting hierarchy trees.
* **Tasks (`tasks.py`)**: Agent task run lifecycle, execution logs, token usage, cost tracking, and multi-turn state resumption.
* **Projects & Filesystem (`projects.py`, `filesystem.py`)**: Project workspace settings and local directory browsing with automatic project type detection.

### 2. Security & Identity Layer (`poc/backend/security/`)
* **Pure HS256 JWT & PBKDF2 (`tokens.py`)**: Zero-external-dependency security provider using Python standard library `hmac`, `hashlib`, and `secrets`. Generates and verifies signed HS256 tokens and handles salted PBKDF2 password hashes.
* **Authentication & Scoping (`auth.py`)**: Enforces authentication via Bearer JWT or API key (`authenticate_request`). Resolves multi-tenant scopes (`get_authorized_scope`, `get_current_org_id`), enforces role requirements (`require_org_admin`), and respects active department overrides via `X-Department-ID` header.
* **Rate Limiting (`rate_limiter.py`)**: In-memory sliding window rate limiter (`RateLimiterMiddleware`, default 2000 req/min) exempting `OPTIONS` requests, health checks, docs, and the live SSE stream (`/api/v1/events/stream`).
* **Tracing & Errors (`correlation.py`, `errors.py`)**: Injects unique `X-Correlation-ID` into all requests and logs; masks internal stack traces in structured HTTP error responses.

### 3. Persistence & Database Management (`poc/persistence.py`)
* **Self-Healing Connection (`_get_connection()`)**: SQLite connection manager that automatically recreates directory paths and initializes database schema if the SQLite file was removed or unmounted at runtime.
* **Orphaned Record Claiming (`claim_orphaned_records()`)**: Automatically reassigns legacy or unattached records (`organization_id IS NULL`) to a registered tenant organization.
* **Concurrency & Safety**: Enforces Write-Ahead Logging (`PRAGMA journal_mode = WAL;`), foreign key constraints (`PRAGMA foreign_keys = ON;`), and a 5000ms busy timeout (`PRAGMA busy_timeout = 5000;`).

### 4. Background Workers & Real-Time Streams
* **Cron Engine (`poc/backend/scheduler/`)**: Headless background worker that periodically polls for due cron jobs and dispatches agent task runs.
* **Event Service & SSE (`poc/backend/events/`)**: In-memory `EventBus` pub/sub and persistent SQLite event store exposed via standard Server-Sent Events (`/api/v1/events/stream`).

---

## 3. Interfaces & Dependency Wiring

All service singletons and dependencies are wired cleanly through `poc/backend/dependencies.py`:
```python
from poc.backend.dependencies import (
    get_db_manager,
    get_runtime_adapter,
    get_orchestration_engine,
    get_event_service,
    get_event_bus,
    get_model_policy_resolver,
)
```

Application startup and graceful shutdown are managed in `poc/backend/main.py`:
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_services()      # Starts CronSchedulerEngine and EventService
    yield
    await shutdown_services()  # Stops background loops and releases connections
```

---

## 4. Invariant Rules & Guardrails

1. **Zero Mocks**: Integration tests run exclusively against real SQLite databases and FastAPI endpoints.
2. **Multi-Tenant Isolation**: Queries and writes for projects, agents, tasks, and workflows must respect `organization_id` and authorized `department_ids`.
3. **Pydantic v2 Standard**: Schema models must use `.model_dump()` and `ConfigDict(from_attributes=True)`.
4. **Resumable State**: Agent tasks that require clarification or hit approval gates must transition to `WAITING_INPUT` or `PENDING_APPROVAL` with `session_id` captured, never concluding prematurely as `COMPLETED`.

---

## 🔄 Mandatory `AGENTS.md` Synchronization Rule

> [!IMPORTANT]
> Whenever any backend logic, API route, database schema, security policy, or background worker behavior is modified, the developer or agent **MUST** update the corresponding directory's `AGENTS.md` (and `CLAUDE.md` where applicable) in the **SAME task/commit**. Unsynchronized code changes are strictly prohibited.

## Modular composition and capability availability
`router_registry.py` owns router descriptors and imports optional implementations independently. `PLATFORM_DISABLED_CAPABILITIES` is a comma-separated list of descriptor/service names. Disabled optional routers are not imported. Import failures are logged server-side and exposed as sanitized HTTP 503 responses with detail `{code: CAPABILITY_UNAVAILABLE, capability: name}`. Shared project-memory and auth-audit prefixes use specific fallback paths to avoid masking unrelated routes. Organizations/authentication remain required core. Existing route prefixes remain unchanged, including memory under `/api/v1/projects`.

`capabilities.py` separates availability (DISABLED, STARTING, READY, DEGRADED, UNAVAILABLE, STOPPING) from task states. Authenticated GET `/api/v1/capabilities` returns `{capabilities: {name: {state, reason}}}` without exception details or credentials. GET `/health` retains process-liveness semantics, not database/provider readiness.

`dependencies.py` is the composition root. Required storage readiness precedes independent optional runtime, orchestration, scheduler, intelligence and teams startup. Failed optional initialization does not abort unrelated startup; getters return explicit 503 rather than fake execution. Concrete compatibility exports load on demand. Scheduler shutdown is isolated; remaining background tasks are cancelled even if shutdown fails. This in-process separation does not isolate process crashes or memory exhaustion.

[Storage](../storage/AGENTS.md) owns SQL, records and connections. `poc/persistence.py` retains record exports, DatabaseManager and db_manager. Repository bound methods are resolved through an explicit legacy ownership map; class-level introspection differs, as documented in the storage guide.

### Lifecycle and read availability refinements
Scheduler router availability is distinct from scheduler-worker; teams router availability is distinct from team-coordinator. Unavailable runtime does not hide persisted task reads or stored schedule administration. Team creation/synthesis no longer constructs an unused orchestration dependency; dispatch obtains a runtime callable only when needed. Notification imports fail independently of workflow execution. Shutdown cancels known runtime runs, closes subscriber queues, releases the loaded indexer, clears service singletons and unregisters the runtime. STARTING/READY describe initialized adapters, not proven provider connectivity.

GET /health/ready returns HTTP 200 `{status: ready}` after a required SQLite connection responds to SELECT 1; it returns 503 `{status: unavailable}` on failure. Core event primitives are required infrastructure even if the optional events HTTP router is disabled. Organizations is required and cannot be disabled through configuration. Runtime wiring injects database/configuration, session persistence, event/chat publication and supervisor/intelligence callbacks. If orchestration is unavailable, clarification is persisted for HUMAN_OPERATOR and the task remains WAITING_INPUT.

get_skill_context is the composition adapter for required step/runtime skill enrichment; it enforces skills capability availability before loading skills_service. Workflow and runtime implementations receive this callback instead of importing that optional service directly.
