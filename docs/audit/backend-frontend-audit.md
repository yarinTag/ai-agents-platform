# Backend and Frontend Audit

## 1. Backend Architecture

### 1.1 Component Inventory

| Component | File | Status | Notes |
|-----------|------|--------|-------|
| FastAPI app | [`backend/main.py`](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/backend/main.py) | **VERIFIED FUNCTIONAL** | CORS, lifespan, 5 routers |
| Service init | [`backend/dependencies.py`](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/backend/dependencies.py) | **VERIFIED FUNCTIONAL** | Singleton access to config/db/runtime |
| Agent CRUD | [`backend/api/agents.py`](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/backend/api/agents.py) | **VERIFIED FUNCTIONAL** | Full CRUD with Pydantic validation |
| Task CRUD + execution | [`backend/api/tasks.py`](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/backend/api/tasks.py) | **VERIFIED FUNCTIONAL** | Create, list, cancel, SSE, logs |
| System events | [`backend/api/events.py`](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/backend/api/events.py) | **PARTIALLY FUNCTIONAL** | Stats/health work; WebSocket is mock |
| Project CRUD | [`backend/api/projects.py`](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/backend/api/projects.py) | **VERIFIED FUNCTIONAL** | Full CRUD |
| Skill CRUD | [`backend/api/skills.py`](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/backend/api/skills.py) | **VERIFIED FUNCTIONAL** | Full CRUD + plugin scanner |
| Config mgr | [`config.py`](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/config.py) | **VERIFIED FUNCTIONAL** | JSON file persistence |
| DB mgr | [`persistence.py`](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/persistence.py) | **VERIFIED FUNCTIONAL** | SQLite with 4 tables |
| Runtime adapter | [`runtime_adapter.py`](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/runtime_adapter.py) | **VERIFIED FUNCTIONAL** | With mock fallback caveat |
| API launcher | [`start_api.py`](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/start_api.py) | **VERIFIED FUNCTIONAL** | uvicorn on port 8000 |

### 1.2 Agent CRUD and Lifecycle

**Create** ([`agents.py` L101-126](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/backend/api/agents.py#L101-L126)):
- ID generated from name: `name.lower().replace(" ", "-")`
- Duplicate check against both config_manager and db_manager
- Saved to both JSON and SQLite

**Read** ([`agents.py` L86-98](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/backend/api/agents.py#L86-L98)):
- Merges agents from db_manager and config_manager
- config_manager entries override db entries (last-write-wins)

**Update** ([`agents.py` L146-169](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/backend/api/agents.py#L146-L169)):
- Partial update via `model_dump(exclude_unset=True)`
- Saves to both stores

**Delete** ([`agents.py` L172-206](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/backend/api/agents.py#L172-L206)):
- Case-insensitive fallback search
- Deletes from both stores
- Cascading delete: removes associated task_runs from DB

**Agent lifecycle states**: No formal lifecycle. Agents exist or don't. There is no "active/inactive" toggle or deployment concept.

### 1.3 Task Creation and Execution

**Create Task** ([`tasks.py` L93-153](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/backend/api/tasks.py#L93-L153)):
1. Validates agent exists (with case-insensitive fallback)
2. Extracts prompt from `prompt`, `input_data.task`, `input_data.prompt`, or defaults to "Execute agent mission"
3. Calls `runtime_adapter.start_task()`
4. Brief `asyncio.sleep(0.05)` to allow state transition
5. Saves initial run to DB
6. Returns TaskResponse

**List Tasks** ([`tasks.py` L156-198](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/backend/api/tasks.py#L156-L198)):
- Merges DB task_runs with live runtime_adapter runs
- Sorts by created_at descending
- Supports agent_id, project_id, status filters

**Cancel Task** ([`tasks.py` L230-260](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/backend/api/tasks.py#L230-L260)):
- Verifies task exists in DB
- Calls `runtime_adapter.cancel_run()`
- Returns updated status

### 1.4 Agent-to-Task Relationships

- **One-to-many**: Each task has exactly one `agent_id`
- **No multi-agent tasks**: No concept of a task involving multiple agents
- **No task dependencies**: Tasks are independent
- **No parent-child tasks**: No `parent_task_id` field

### 1.5 Parent-Child Relationships — NOT IMPLEMENTED

No hierarchical relationships exist between agents or tasks. The only grouping is by `department` string (used for office visualization layout).

### 1.6 Project Management

**VERIFIED FUNCTIONAL** — Full CRUD for projects with:
- Name, description, working_directory, instructions
- Skills list (array of skill IDs)
- Allowed tools list (defaults to `["read", "grep", "glob"]`)
- Working directory is used as `cwd` for subprocess and `--add-dir` flag

### 1.7 Skills and Tool Configuration

**VERIFIED FUNCTIONAL** — Full CRUD for skills with:
- Markdown content storage
- Optional YAML frontmatter parsing
- Global (project_id=NULL) or project-specific scoping
- File-based storage via ConfigManager + DB storage via DatabaseManager
- Plugin scanner that searches hardcoded local filesystem paths

### 1.8 Event Creation and Delivery

**SSE Streaming** ([`tasks.py` L263-391](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/backend/api/tasks.py#L263-L391)):
- Per-task SSE endpoint at `GET /api/v1/tasks/{run_id}/events`
- Bridges sync `queue.Queue` to async `asyncio.Queue`
- Event types: connected, event, heartbeat, update, close
- 30-second heartbeat timeout

**System Events** ([`events.py`](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/backend/api/events.py)):
- Stats endpoint aggregates agent/project/skill/task counts
- Health endpoint checks config_manager, db_manager, runtime_adapter
- Recent activity endpoint returns recent task_runs as activity items
- WebSocket endpoint: **MOCK** — only sends periodic heartbeats

### 1.9 Error Handling

- Standard `HTTPException` for known errors (404, 400)
- Generic `except Exception` blocks with `print()` warnings
- No structured error logging
- No global exception handler
- No request correlation IDs

### 1.10 Concurrency

- No explicit concurrency limits
- SQLite connections created per-call (not pooled)
- Runtime adapter uses unbounded thread creation
- No WAL mode configured for SQLite

### 1.11 Authentication and Authorization

**NOT IMPLEMENTED**. Zero authentication on any endpoint. CORS allows all origins.

---

## 2. Frontend Architecture

### 2.1 Dashboard Architecture — VERIFIED

```
App.tsx (ConfigProvider + BrowserRouter)
├── AppLayout.tsx (Flex layout)
│   ├── OfficeTopBar.tsx (Header with clock, nav links)
│   └── {children} (Route content)
├── Routes:
│   ├── / → OfficeView.tsx
│   │   ├── AgentsOfficeV3Canvas.tsx (Main office view)
│   │   │   └── AgentDeskDrawer.tsx (Click-to-open desk panel)
│   │   └── OfficeRightSidebar.tsx (Task queue, quick add)
│   ├── /flow → AgentFlowPage.tsx
│   │   └── AgentFlowDiagram.tsx (Pipeline node graph)
│   ├── /agents → Agents.tsx (CRUD table + modal)
│   ├── /skills → Skills.tsx (CRUD table + modal + scanner)
│   ├── /tasks → Tasks.tsx (CRUD table + modal)
│   ├── /projects → Projects.tsx (CRUD table + modal)
│   └── /dashboard → Dashboard.tsx (Stats cards + charts)
```

### 2.2 Office Visualization Components

#### `AgentsOfficeV3Canvas.tsx` (Primary — used in production)

**Rendering**: DOM-based with CSS pseudo-3D transforms (`perspective(600px) rotateX(20deg)`)
- SVG used only for walkway connections and animated particles
- No `<canvas>` API usage
- No pixel art sprites

**Agent States Visualized**:
| State | Visual | Trigger |
|-------|--------|---------|
| Working | Green border, glow, pulsing "WORKING" bubble | Has running task |
| Idle | Muted grey/slate styling | No active task |

**Layout**: Hardcoded `DEPARTMENTS` array with static `{x, y}` coordinates for 4 department platforms, each containing desk slots with relative offsets. Agents matched to desks by `department` string and name heuristics.

**Animations**:
- CSS `@keyframes pulse` on working badge
- SVG `<animate>` and `<animateMotion>` for energy particle flows along corridor paths
- No agent walking or movement between locations

**Data Source**: HTTP polling at 3-second intervals. **Hybrid real/mock**:
- Fetches real agents and tasks from backend API
- Artificially increments progress percentages via local `setInterval`
- "Dispatch Live Mission" button creates a real backend task

#### `OfficeCanvas.tsx` (Alternative — flat 2D)

Simple top-down floor plan grid. Functional but simpler than V3.

#### `IsometricOffice.tsx` (Alternative — card grid)

Responsive card grid with large isometric laptop icons. More like a dashboard than an office.

### 2.3 Agent Positioning — VERIFIED

Layout defined in `AgentsOfficeV3Canvas.tsx` via hardcoded department config:
```typescript
const DEPARTMENTS = [
  {
    name: 'Engineering', x: 200, y: 180,
    desks: [
      { relX: 20, relY: 50, label: 'LEAD' },
      { relX: 170, relY: 50, label: 'DEV-1' },
      // ...
    ]
  },
  // Architecture, QA & Testing, Research & Ops
];
```

Agent-to-desk matching uses `findAgentForDesk()` which matches by `agent.department` and then by name patterns (e.g., looking for "LEAD" in name).

### 2.4 Flow Diagram — VERIFIED

[`AgentFlowDiagram.tsx`](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/dashboard/src/components/flow/AgentFlowDiagram.tsx): Visual pipeline node graph showing agents as nodes with connections. Uses SVG for edges. Supports active/idle/waiting/error states per node.

### 2.5 Real-Time Communication — VERIFIED

**HTTP Polling only**. Despite backend SSE support, the frontend:
- Does NOT use SSE (`EventSource`)
- Does NOT use WebSocket
- Polls via `setInterval` every 3 seconds
- Each poll makes `getAgents()` + `getTasks()` + `getRecentActivity()` calls

### 2.6 State Management — VERIFIED

- **Local state only**: `useState` + `useEffect` per component
- **No global store**: No Redux, Zustand, MobX, or React Context
- **No shared cache**: Data refetched independently by each page
- **Props drilling**: Parent components pass data down via props

### 2.7 Forms and Dialogs — VERIFIED

| Form | Location | Fields |
|------|----------|--------|
| Create/Edit Agent | `Agents.tsx` | name, description, system_prompt, model, effort, department, skills, max_tokens, temperature |
| Create Task | `Tasks.tsx` | agent_id (select), prompt (textarea), project_id (select) |
| Create Project | `Projects.tsx` | name, description, working_directory, instructions, allowed_tools |
| Create Skill | `Skills.tsx` | name, description, content, project_id |
| Quick Task | `OfficeRightSidebar.tsx` | Free-text input + suggestion chips |
| Desk Command | `AgentDeskDrawer.tsx` | Command textarea with model/project selects |

### 2.8 Loading and Error States — VERIFIED

- Loading: `<Spin>` component + `loading` boolean state on buttons/tables
- Errors: `message.error('Failed to...')` toast notifications via Ant Design
- Empty states: Conditional JSX rendering with descriptive text

---

## 3. Integration Boundaries — VERIFIED

### 3.1 Actual Architecture

```
┌─────────────────────────────────────────────────────┐
│ Frontend (React 19 + Ant Design 6 + Vite 8)        │
│ Port: 5173 (dev) / static (prod)                   │
│                                                     │
│ Data: HTTP polling every 3s via Axios               │
│ Target: http://localhost:8000                       │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP (REST JSON)
                       ▼
┌─────────────────────────────────────────────────────┐
│ Backend (FastAPI 0.104.1 + uvicorn 0.24.0)          │
│ Port: 8000                                          │
│                                                     │
│ Services:                                           │
│  ├── ConfigManager (JSON files)                     │
│  ├── DatabaseManager (SQLite)                       │
│  └── ClaudeCodeRuntimeAdapter (subprocess)          │
│                                                     │
│ SSE: /api/v1/tasks/{id}/events (implemented,        │
│       not consumed by frontend)                     │
│ WS:  /api/v1/events/ws/system (mock heartbeat only) │
└──────────────────────┬──────────────────────────────┘
                       │ subprocess.Popen
                       ▼
┌─────────────────────────────────────────────────────┐
│ Claude CLI (`claude`)                               │
│ Flags: -p --output-format stream-json               │
│        --dangerously-skip-permissions --verbose      │
│        --add-dir <dir> [--model <model>]            │
│                                                     │
│ Environment:                                        │
│  ANTHROPIC_BASE_URL=http://127.0.0.1:8082          │
│  ANTHROPIC_AUTH_TOKEN=freecc                        │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP API
                       ▼
┌─────────────────────────────────────────────────────┐
│ Free Claude Code Proxy                              │
│ Port: 8082                                          │
│ Routes to: Claude API / potentially NVIDIA          │
└─────────────────────────────────────────────────────┘
```

### 3.2 Data Flow Gaps

| Gap | Impact |
|-----|--------|
| Frontend doesn't consume SSE | No real-time event display; stale 3s polling |
| Frontend doesn't use WebSocket | No live system updates |
| No global event aggregation | Can't monitor all agents simultaneously |
| No event replay on reconnect | Client loses events if connection drops |
| Events stored as JSON blob | Not queryable, not streamable retroactively |

---

## 4. Technical Debt Summary

### 4.1 Backend

1. **`sys.path.append`** in every API file — should use proper Python package structure
2. **Dual storage** (JSON + SQLite) with no reconciliation
3. **Duplicate config dirs** — `poc/config/` and `poc/backend/config/`
4. **Hardcoded proxy credentials** — `"freecc"` in source
5. **Hardcoded plugin paths** — Windows-specific paths in `skills.py` L178-182
6. **No Python package** — no `pyproject.toml`, `setup.py`, `__init__.py` at root
7. **`created_at`/`updated_at` stubs** — return empty strings, not actual timestamps
8. **No request validation** — task status filter uses `status.HTTP_400_BAD_REQUEST` which shadows the variable
9. **SQLite not WAL mode** — potential locking issues under concurrent access

### 4.2 Frontend

1. **No SSE/WebSocket consumption** — backend capabilities unused
2. **No global state** — redundant fetches across components
3. **Hardcoded API URL** — `http://localhost:8000` in api.ts
4. **Hardcoded model list** — no dynamic model discovery
5. **Mock progress** — artificial progress injection in office view
6. **No error boundaries** — React error boundaries not implemented
7. **Large bundle** — 1.2MB single chunk (Vite warns about code splitting)
8. **No tests** — zero frontend tests
9. **Hardcoded office layout** — department positions not configurable

---

## 5. Reusable Implementation Opportunities

| Opportunity | Existing Component | Extension Needed |
|-------------|-------------------|-----------------|
| Agent management API | agents.py, agents CRUD | Add hierarchy fields, agent templates |
| Task execution pipeline | tasks.py → runtime_adapter | Add orchestration, delegation |
| SSE infrastructure | tasks.py L263-391 | Fix content type, add global stream |
| Office visualization concept | AgentsOfficeV3Canvas.tsx | Replace CSS shapes with pixel art, add state machine |
| Agent desk interaction | AgentDeskDrawer.tsx | Connect to real-time events |
| API client layer | services/api.ts | Add SSE/WS clients |
| TypeScript types | types/*.ts | Add hierarchy, event types |
| Pydantic models | API request/response models | Add hierarchy, orchestration models |
| SQLite persistence | DatabaseManager | Add hierarchy tables, event log |
