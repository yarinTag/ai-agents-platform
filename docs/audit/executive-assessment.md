# Executive Architecture Assessment

## Current System Summary

The AI Agents Platform is a **functional proof-of-concept** built around the Free Claude Code (FCC) wrapper. It provides:

- A **Python backend** (FastAPI) with REST API for managing agents, projects, skills, and tasks
- A **runtime adapter** that launches Claude Code as a subprocess with `--output-format stream-json`
- A **SQLite persistence layer** storing agents, projects, skills, and task run history
- A **React dashboard** (Vite + Ant Design) with an office-style visualization, CRUD management pages, and a flow diagram view
- **Model routing through the FCC proxy** on `localhost:8082`, which transparently handles model selection including NVIDIA models

The system is in **POC stage** — it works end-to-end for single-agent task execution through the Claude Code CLI, with real subprocess management, streaming event capture, and process lifecycle handling.

---

## What Can Be Reused

| Component | Reuse Potential | Evidence |
|-----------|----------------|----------|
| `ClaudeCodeRuntimeAdapter` | **HIGH** — core subprocess management, stream-json parsing, event queuing, and process lifecycle are solid | [`runtime_adapter.py`](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/runtime_adapter.py) |
| `ConfigManager` + `AgentConfig` | **HIGH** — clean dataclass-based config with JSON persistence | [`config.py`](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/config.py) |
| `DatabaseManager` + SQLite schema | **MEDIUM** — good foundation but needs hierarchy columns and event tables | [`persistence.py`](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/persistence.py) |
| FastAPI backend structure | **HIGH** — well-organized API routers with proper dependency injection | [`backend/main.py`](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/backend/main.py) |
| SSE event streaming | **MEDIUM** — implemented but needs refactoring for multi-agent event aggregation | [`backend/api/tasks.py`](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/backend/api/tasks.py#L263-L391) |
| Dashboard page structure | **HIGH** — 7 routes with CRUD forms, table views, and modals all functional | [`App.tsx`](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/dashboard/src/App.tsx) |
| Office visualization concept | **MEDIUM** — DOM-based pseudo-3D rendering works but needs real pixel art and state-driven animation | [`AgentsOfficeV3Canvas.tsx`](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/dashboard/src/components/office/AgentsOfficeV3Canvas.tsx) |
| TypeScript types | **HIGH** — clean type definitions that map to backend entities | `types/*.ts` |

---

## What Is Missing

### Critical (Required for AI Agents Office vision)

| Capability | Status | Impact |
|-----------|--------|--------|
| Agent hierarchy (parent-child) | **NOT IMPLEMENTED** | Cannot build manager/sub-agent chains |
| Orchestration engine | **NOT IMPLEMENTED** | No task delegation, result collection, or escalation |
| Multi-agent coordination | **NOT IMPLEMENTED** | Each task runs as isolated single-agent execution |
| Real-time state propagation | **PARTIALLY IMPLEMENTED** | SSE exists per-task but no global event bus |
| Pixel art assets and animation engine | **NOT IMPLEMENTED** | Current office uses CSS shapes, not actual pixel art |
| Agent movement and state-driven visualization | **NOT IMPLEMENTED** | No walk-to-manager or desk-assignment animations |
| Authentication and authorization | **NOT IMPLEMENTED** | API completely open |
| Project isolation and workspace boundaries | **PARTIALLY IMPLEMENTED** | `--add-dir` used but `allowed_tools` not enforced |
| Human approval gates | **NOT IMPLEMENTED** | `--dangerously-skip-permissions` always set |

### Important (Required for production platform)

| Capability | Status |
|-----------|--------|
| Tool permission enforcement | NOT IMPLEMENTED — `ProjectConfig.allowed_tools` exists but is ignored |
| Secret/credential management | NOT IMPLEMENTED — proxy credentials hardcoded |
| Concurrent execution limits | NOT IMPLEMENTED — unbounded thread creation |
| Session discovery / monitoring external runs | NOT IMPLEMENTED |
| Agent templates / reusable definitions | NOT IMPLEMENTED |
| Error recovery and retry logic | NOT IMPLEMENTED |
| Audit logging | NOT IMPLEMENTED |

---

## Major Architectural Risks

### 1. Mock Fallback in Runtime Adapter

> [!CAUTION]
> Lines 409–434 of [`runtime_adapter.py`](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/runtime_adapter.py#L409-L434) contain a **silent mock fallback**. If the Claude Code CLI fails to start, the adapter fabricates fake "thought" and "tool_use" events and returns a fake success result. This can mask real failures and produce misleading office visualization.

### 2. `--dangerously-skip-permissions` Always Enabled

The runtime always passes `--dangerously-skip-permissions` ([line 141](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/runtime_adapter.py#L141)), bypassing Claude Code's permission system. For a multi-agent platform with sub-agents, this is a significant security risk.

### 3. No Agent Hierarchy in Data Model

The `agents` table and `AgentConfig` dataclass have no `parent_id`, `manager_id`, or role hierarchy fields. Building orchestration on top requires schema migration.

### 4. In-Memory State with No Replication

`ClaudeCodeRuntimeAdapter._runs` is a plain Python dict. Active run state is lost on server restart. SSE subscribers cannot reconnect and resume.

### 5. Dual Config/DB Storage

Agent data is written to both JSON files (`config_manager`) and SQLite (`db_manager`), with no clear source of truth when they diverge.

---

## Recommended Integration Strategy

**Wrap, don't replace** the existing Claude Code runtime adapter:

```
┌─────────────────────────────────────────────┐
│              Orchestration Layer             │
│  (NEW: hierarchy, delegation, result flow)  │
├─────────────────────────────────────────────┤
│           Runtime Adapter Interface          │
│            (NEW: abstract protocol)          │
├──────────────────┬──────────────────────────┤
│ ClaudeCodeAdapter│  Future: DirectAPI,      │
│ (EXISTING, wrap) │  NVIDIA NIM, etc.        │
└──────────────────┴──────────────────────────┘
```

1. **Keep** `ClaudeCodeRuntimeAdapter` as the primary execution engine
2. **Extract** a `RuntimeAdapter` protocol/interface from its public API
3. **Add** an orchestration layer above the adapter that manages hierarchy, delegation, and result collection
4. **Extend** the database schema with parent-child relationships and a proper event log table
5. **Add** a global event bus (in-process, not Kafka/Redis) for real-time state propagation
6. **Build** the pixel art visualization as a state-driven renderer consuming backend events

---

## Feasibility Assessment

| Aspect | Assessment | Evidence |
|--------|-----------|----------|
| Single-agent execution | **WORKS** | Subprocess management, stream-json parsing verified in source |
| Model selection via FCC proxy | **WORKS** | `--model` flag passed to CLI, proxy handles routing |
| NVIDIA model support | **VERIFIED POSSIBLE** — depends on FCC proxy capability | Config allows arbitrary model strings; actual proxy availability not tested |
| Concurrent execution | **WORKS** — per-thread isolation | Each run gets its own thread, process, and event queue |
| Session resume | **IMPLEMENTED** — `--resume` and `--fork-session` flags supported | [`runtime_adapter.py` L133-136](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/runtime_adapter.py#L133-L136) |
| Sub-agent orchestration | **NOT IMPLEMENTED** — must be built from scratch | No hierarchy in data model or runtime |
| Pixel art office | **MUST BE BUILT** — current office is CSS pseudo-3D, not pixel art | No sprite assets exist |
| Real-time visualization | **PARTIALLY READY** — SSE infrastructure exists, needs global event aggregation | |

---

## Explicit Assumptions and Unknowns

### Assumptions
- The Free Claude Code proxy at `localhost:8082` supports multiple model providers including NVIDIA
- The `claude` CLI is installed and accessible in the system PATH
- Claude Code's `stream-json` output format provides structured event types (`result`, `error`, `tool_use`, `thought`, etc.)

### Unknowns Requiring Investigation
- **NVIDIA model compatibility**: Whether NVIDIA models support the same tool-use and streaming formats as Claude models through FCC — REQUIRES TESTING
- **Claude Code sub-agent protocol**: Whether Claude Code has native support for spawning sub-agents that the platform could intercept — REQUIRES DOCUMENTATION REVIEW
- **FCC proxy model discovery**: Whether the `CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY` env var exposes available models programmatically — REQUIRES TESTING
- **Concurrent process limits**: Maximum number of simultaneous Claude Code processes the system can handle — REQUIRES LOAD TESTING
