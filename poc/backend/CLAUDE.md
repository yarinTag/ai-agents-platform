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

### Workflow playground contracts
The tool-free playground endpoint returns 202 and runs locally via BackgroundTasks, not RabbitMQ. Keep its fresh IDs/hash namespace and capability check; never fall back to ordinary unrestricted execution. Execution detail includes step_runs and enforces workflow scope. Run isolated contract tests with `.venv/bin/python -m pytest --noconftest poc/tests/test_workflow_playground.py -q`; the shared conftest resets the default application database and is intentionally not loaded for this suite. Real model inference is a separate smoke check, not covered by these tests.

Tool-free playgrounds skip connector-grant prechecks for declared MCP dependencies, while ordinary runs still reject ungranted connectors. Do not grant production connector access to make a tool-free exercise runnable. The playground contract suite covers workflow and step declarations for both modes.

Execution detail now exposes persisted runtime diagnostics per step (last 500 events), under the same workflow tenant/department scope. Step log rows are created before runtime launch and finalized in place. Runtime stdout/stderr regression checks use real local subprocesses and require no provider calls. The standalone logs route is `/workflows/:workflowId/logs`.

Workflow origin is computed from workflow_step_runs plus recursive task lineage. Do not mark a shared agent as workflow-only to isolate a particular run. Task snapshot scope and SSE payload origin must agree. Origin tests run against isolated real SQLite/FastAPI with --noconftest. Plugin scan refresh=true explicitly bypasses the Git tree scan cache; source edits and manual refresh must invalidate client cache.

### Workflow update invariants
Workflow updates and history inserts must share one transaction. Use exclude_unset request data to preserve omitted settings, allow explicit clearing of nullable fields, and reject tenant reassignment. expected_revision mismatches return 409 with drafts retained in the client. Workflow YAML/JSON conversion must validate DAGs while preserving unknown extension fields and metadata. Schema migration captures a single legacy baseline; do not claim earlier history exists. Tests are in test_workflow_revisions.py and run with --noconftest.
