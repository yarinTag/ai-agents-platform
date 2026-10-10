# CLAUDE.md - Backend Guidelines (FastAPI & Services)

This document provides developer instructions, operational invariants, and coding standards for Claude Code working on `poc/backend` and the platform backend core.

---

## 🚀 Quick Commands

* **Run Entire Test Suite**: `pytest poc/tests/ -v`
* **Run Specific Test File**: `pytest poc/tests/<test_file>.py -v`
* **Run Server (Dev)**: `python -m uvicorn poc.backend.main:app --host 0.0.0.0 --port 8000 --reload`
* **Health Check**: `curl http://localhost:8000/health`

---

## 🏗️ Architecture & Core Principles

* **Framework**: FastAPI (Python 3.10+) with asynchronous endpoints (`async def`).
* **Database**: SQLite3 with Write-Ahead Logging (`PRAGMA journal_mode = WAL;`) and busy timeout (`busy_timeout = 5000;`) managed in `poc/persistence.py`.
* **Zero Mocks Policy**: All integration tests in `poc/tests/` use real SQLite databases and real FastAPI `TestClient`/`httpx.AsyncClient` instances. Do NOT introduce synthetic mock adapters that bypass real execution.
* **Centralized Import Bridge**: `poc/backend/dependencies.py` is the single authorized location to initialize dependencies and root-level imports. Never insert `sys.path.append` into router files.
* **Lifespan Management**: `poc/backend/main.py` uses `@asynccontextmanager async def lifespan(app: FastAPI)` to initialize singleton background workers (CronSchedulerEngine, EventService) on startup and shut them down gracefully.

---

## 📁 Directory Structure

```
poc/
├── backend/
│   ├── api/             # REST Routers (agents, tasks, schedules, approvals, chat, memories, war_room, events, fs)
│   ├── security/        # Auth, RateLimiter, CorrelationId, Error Handlers (see security/AGENTS.md)
│   ├── teams/           # Multi-Agent Teams router & coordination (see teams/AGENTS.md)
│   ├── messages/        # Agent-to-Agent (A2A) messaging router (see messages/AGENTS.md)
│   ├── cron_engine.py   # Async CronSchedulerEngine background polling worker
│   ├── dependencies.py  # Centralized dependency injection bridge
│   └── main.py          # FastAPI application entrypoint & lifespan
├── orchestration/       # HierarchyValidator, OrchestrationEngine, SupervisorResolver
├── runtime/             # RuntimeAdapter protocol, RuntimeRegistry, ModelPolicyResolver, ClaudeCodeAdapter
├── persistence.py       # DatabaseManager (SQLite schema, migrations, CRUD)
├── runtime_adapter.py   # ClaudeCodeRuntimeAdapter (Subprocess CLI, streaming, session resume)
├── runtime_providers.py # Provider Registry (Native, Anthropic API, Custom Gateway / LiteLLM)
└── tests/               # 13 Automated test suites (87 tests, zero mocks)
```

---

## 📐 Invariant Rules & Coding Conventions

1. **Pydantic v2 Compatibility**:
   * Always use `.model_dump()` instead of deprecated `.dict()`.
   * Use `ConfigDict(from_attributes=True)` instead of `class Config: from_attributes = True`.
   * For list validations, use `Field(..., min_length=1)` instead of deprecated `min_items=1`.
2. **Subprocess & Execution Safety**:
   * In `poc/runtime_adapter.py`, `start_task` is synchronous and non-blocking (spawns daemon threads for output reading).
   * Always capture `session_id` from Claude stream-json events to support multi-turn continuation with `--resume <session_id>`.
   * If a task result contains an unresolved question or missing parameters, transition to `TaskStatus.WAITING_INPUT` and invoke `SupervisorResolver`—do NOT mark as `COMPLETED`.
3. **Database Transactions & Foreign Keys**:
   * SQLite enforces `PRAGMA foreign_keys = ON;`.
   * When creating records referencing `agents(id)` or `task_runs(run_id)`, ensure parent entities exist first.
   * Project configurations are logical boundaries loaded via `ConfigManager` and persisted via `db_manager.save_project`.
4. **Events & EventBus**:
   * Publish events through `EventBus.publish(PlatformEvent(...))`.
   * Always supply `event_id=f"evt_{datetime.now().timestamp()}"`, `event_type`, and appropriate payloads.
