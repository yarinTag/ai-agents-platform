# Existing System Audit

## 1. Repository Structure

```
ai-agents-platform/
├── GEMINI.md                          # Agent execution guidelines
├── poc/                               # Proof of concept (entire application)
│   ├── README.md                      # Project documentation
│   ├── requirements.txt               # Python dependencies
│   ├── config.py                      # Configuration management (AgentConfig, ProjectConfig, Skill)
│   ├── persistence.py                 # SQLite persistence layer (DatabaseManager)
│   ├── runtime_adapter.py             # Claude Code subprocess wrapper (ClaudeCodeRuntimeAdapter)
│   ├── start_api.py                   # API server launcher (uvicorn)
│   ├── config/                        # JSON config files
│   │   ├── agents.json                # Agent definitions (1 agent: "secuirty")
│   │   └── projects.json              # Project definitions (empty)
│   ├── data/
│   │   └── agents_platform.db         # SQLite database
│   ├── backend/                       # FastAPI application
│   │   ├── main.py                    # FastAPI app with CORS and router registration
│   │   ├── dependencies.py            # Singleton service initialization
│   │   ├── api/
│   │   │   ├── agents.py              # Agent CRUD endpoints
│   │   │   ├── tasks.py               # Task submission, cancellation, SSE streaming
│   │   │   ├── events.py              # System stats, health, WebSocket (mock)
│   │   │   ├── projects.py            # Project CRUD endpoints
│   │   │   └── skills.py              # Skill CRUD + plugin scanner
│   │   └── config/agents.json         # Duplicate agent config (different content)
│   ├── dashboard/                     # React frontend
│   │   ├── package.json               # Dependencies: React 19, Ant Design 6, Vite 8
│   │   ├── src/
│   │   │   ├── App.tsx                # Router with 7 routes
│   │   │   ├── services/api.ts        # Axios API client (localhost:8000)
│   │   │   ├── types/                 # TypeScript type definitions
│   │   │   ├── constants/models.ts    # AI model options (Default, Sonnet, Opus, Haiku, Fable)
│   │   │   ├── components/
│   │   │   │   ├── office/            # Office visualization components (3 variants)
│   │   │   │   ├── flow/              # Agent flow diagram
│   │   │   │   └── layout/            # App layout and top bar
│   │   │   └── pages/                 # 7 page components
│   │   └── dist/                      # Pre-built production output
│   ├── demo_poc.py                    # Direct PoC demo (no API)
│   ├── demo_api.py                    # API-based demo script
│   └── test_*.py, debug_*.py, etc.    # Test and diagnostic scripts
```

---

## 2. Runtime Analysis

### 2.1 Execution Flow — VERIFIED

The complete execution path from task creation to result:

```
POST /api/v1/tasks/ (TaskCreate payload)
    │
    ├─ tasks.py L104: Looks up AgentConfig from config_manager or db_manager
    ├─ tasks.py L128: Calls runtime_adapter.start_task(agent_id, project_id, prompt)
    │       │
    │       ├─ runtime_adapter.py L264: Looks up AgentConfig from config_manager
    │       ├─ runtime_adapter.py L278: Creates AgentRun record (status=QUEUED)
    │       ├─ runtime_adapter.py L290: Spawns daemon thread → _execute_task()
    │       │       │
    │       │       ├─ L323: Sets status = RUNNING
    │       │       ├─ L327: Builds claude command via _build_claude_command()
    │       │       ├─ L328: Builds environment via _build_claude_env()
    │       │       ├─ L339: subprocess.Popen(cmd, stdout=PIPE, stderr=PIPE, env, cwd)
    │       │       ├─ L358: Spawns _output_reader thread for stdout parsing
    │       │       ├─ L367: Event processing loop (queue.get with 0.1s timeout)
    │       │       │       ├─ "result" event → COMPLETED
    │       │       │       ├─ "error" event → FAILED
    │       │       │       └─ "end_of_output" → COMPLETED or FAILED
    │       │       │
    │       │       └─ L434: finally: saves to DB, stops threads, kills process
    │       │
    │       └─ Returns run_id (UUID)
    │
    ├─ tasks.py L134: asyncio.sleep(0.05) — brief wait for state transition
    └─ tasks.py L153: Returns TaskResponse with current status
```

### 2.2 Command Construction — VERIFIED

Built in [`_build_claude_command()`](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/runtime_adapter.py#L108-L156):

```
claude [--model <model>] [--resume <session_id>] [--fork-session]
       -p <prompt>
       --output-format stream-json
       --dangerously-skip-permissions
       --verbose
       --add-dir <working_directory>
```

### 2.3 Environment Variables — VERIFIED

Set in [`_build_claude_env()`](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/runtime_adapter.py#L91-L106):

| Variable | Value | Purpose |
|----------|-------|---------|
| `ANTHROPIC_BASE_URL` | `http://127.0.0.1:8082` | FCC proxy URL |
| `ANTHROPIC_AUTH_TOKEN` | `freecc` | FCC auth token |
| `CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY` | `1` | Enable model discovery |
| `CLAUDE_CODE_AUTO_COMPACT_WINDOW` | `190000` | Context window compaction |
| `DISABLE_AUTOUPDATER` | `1` | Suppress auto-update |
| `TERM` | `dumb` | Disable terminal formatting |

### 2.4 Process Lifecycle — VERIFIED

| Phase | Mechanism | Location |
|-------|-----------|----------|
| Tracking | `_processes: Dict[str, Popen]` keyed by run_id | L86 |
| Output | `_output_reader` thread reads stdout line-by-line | L181-237 |
| Events | `_event_queues: Dict[str, Queue]` per run | L87 |
| Stop signal | `_stop_events: Dict[str, Event]` per run | L89 |
| Cancellation | `terminate()` → wait(5s) → `kill()` | L484-520 |
| Cleanup | `finally:` block deletes from all dicts | L434-466 |

### 2.5 Mock Fallback — VERIFIED

> [!WARNING]
> Lines 409-434 of [`runtime_adapter.py`](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/runtime_adapter.py#L409-L434): When `subprocess.Popen` throws an exception (e.g., `claude` CLI not found), the code falls into an `except` block that:
> 1. Sleeps for 2.7 seconds total (simulating execution time)
> 2. Fabricates a fake `thought` event
> 3. Fabricates a fake `tool_use` event
> 4. Sets status to `COMPLETED` with a hardcoded success message
>
> This is unlabeled and can silently produce fake results in production.

### 2.6 Model Selection Flow — VERIFIED

```
AgentConfig.model (e.g., "fable", "sonnet", "opus")
    │
    ├─ Stored in agents table (persistence.py L53)
    ├─ Stored in agents.json (config.py L137)
    │
    └─ Used in _build_claude_command() (runtime_adapter.py L130):
       if agent_config.model and agent_config.model.lower() != "default":
           cmd.extend(["--model", agent_config.model.lower()])
```

- Model is per-agent, not per-task or per-session
- The model string is passed directly to the `claude` CLI
- The FCC proxy at `localhost:8082` is responsible for routing to the actual provider
- NVIDIA models would need to be supported by the FCC proxy — **NOT VERIFIED** in this codebase

### 2.7 Sub-Agent Capability — NOT IMPLEMENTED

| Question | Answer |
|----------|--------|
| Parent-child relationship in data model? | **No** — `agents` table has no `parent_id` column |
| Runtime sub-agent creation? | **No** — each `start_task` creates an independent process |
| Result forwarding between agents? | **No** — results are stored per-run only |
| Agent hierarchy tracking? | **No** — flat agent list with only `department` grouping |
| Tool/workspace restrictions per child? | **No** — `allowed_tools` field exists but is never enforced |

### 2.8 Capability Verification Summary

| Capability | Status |
|-----------|--------|
| Single-agent subprocess execution | **VERIFIED** |
| Model selection via --model flag | **VERIFIED** |
| Stream-json output parsing | **VERIFIED** |
| Event queuing and threading | **VERIFIED** |
| Process cancellation | **VERIFIED** |
| Session resume (--resume, --fork-session) | **VERIFIED** (code exists, not tested at runtime) |
| Concurrent execution | **VERIFIED** (thread-per-run architecture) |
| Result persistence to SQLite | **VERIFIED** |
| Sub-agent / nested agents | **NOT IMPLEMENTED** |
| Tool permission enforcement | **NOT IMPLEMENTED** |
| Secret management | **NOT IMPLEMENTED** |
| NVIDIA model execution | **NOT VERIFIED** — depends on FCC proxy |
| Authentication | **NOT IMPLEMENTED** |
| Rate limiting | **NOT IMPLEMENTED** |

---

## 3. Backend Analysis

### 3.1 API Endpoints — VERIFIED

| Endpoint | Method | Purpose | File |
|----------|--------|---------|------|
| `/` | GET | Root info | [`main.py`](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/backend/main.py#L55) |
| `/health` | GET | Health check | [`main.py`](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/backend/main.py#L65) |
| `/api/v1/agents/` | GET, POST | List/create agents | [`agents.py`](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/backend/api/agents.py) |
| `/api/v1/agents/{id}` | GET, PUT, DELETE | Agent CRUD | [`agents.py`](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/backend/api/agents.py) |
| `/api/v1/projects/` | GET, POST | List/create projects | [`projects.py`](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/backend/api/projects.py) |
| `/api/v1/projects/{id}` | GET, PUT, DELETE | Project CRUD | [`projects.py`](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/backend/api/projects.py) |
| `/api/v1/skills/` | GET, POST | List/create skills | [`skills.py`](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/backend/api/skills.py) |
| `/api/v1/skills/{id}` | GET, PUT, DELETE | Skill CRUD | [`skills.py`](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/backend/api/skills.py) |
| `/api/v1/skills/plugins/scan` | GET | Scan local plugins | [`skills.py`](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/backend/api/skills.py#L175) |
| `/api/v1/tasks/` | GET, POST | List/create tasks | [`tasks.py`](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/backend/api/tasks.py) |
| `/api/v1/tasks/{id}` | GET, DELETE | Task CRUD | [`tasks.py`](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/backend/api/tasks.py) |
| `/api/v1/tasks/{id}/cancel` | POST | Cancel running task | [`tasks.py`](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/backend/api/tasks.py#L230) |
| `/api/v1/tasks/{id}/events` | GET | SSE event stream | [`tasks.py`](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/backend/api/tasks.py#L263) |
| `/api/v1/tasks/{id}/logs` | GET | Historical task logs | [`tasks.py`](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/backend/api/tasks.py#L394) |
| `/api/v1/events/system/stats` | GET | System statistics | [`events.py`](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/backend/api/events.py#L23) |
| `/api/v1/events/system/health` | GET | Health details | [`events.py`](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/backend/api/events.py#L75) |
| `/api/v1/events/system/recent-activity` | GET | Activity feed | [`events.py`](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/backend/api/events.py#L144) |
| `/api/v1/events/ws/system` | WS | WebSocket (mock heartbeat) | [`events.py`](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/backend/api/events.py#L182) |

### 3.2 Data Model — VERIFIED

**Agent:** id, name, description, system_prompt, skills[], model, effort, max_tokens, temperature, repo_path, github_url, department, avatar

**Project:** id, name, description, working_directory, instructions, skills[], allowed_tools[]

**Skill:** id, name, description, content (markdown), project_id (nullable for global)

**TaskRun:** run_id, agent_id, project_id, prompt, status, created_at, started_at, ended_at, result, error, exit_code, events (JSON blob)

### 3.3 Dual Storage Issue — VERIFIED

Agents are stored in **both** `config/agents.json` (via ConfigManager) and `data/agents_platform.db` (via DatabaseManager). The API writes to both:
- [`agents.py` L123-124](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/backend/api/agents.py#L123-L124): `config_manager.register_agent(agent_config)` then `db_manager.save_agent(agent_config)`
- Reads merge both sources: [`agents.py` L93-98](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/backend/api/agents.py#L93-L98)

This creates potential divergence with no reconciliation mechanism.

### 3.4 Concurrency and Error Handling — PARTIALLY VERIFIED

- SQLite connections are per-call (not pooled), with no explicit WAL mode or busy timeout
- No global error handler or structured error responses beyond HTTPException
- No request rate limiting or concurrent execution caps

---

## 4. Frontend Analysis

### 4.1 Architecture — VERIFIED

| Technology | Version | Purpose |
|-----------|---------|---------|
| React | 19.2.8 | UI framework |
| Ant Design | 6.6.4 | Component library |
| Vite | 8.3.0 | Build tool |
| TypeScript | 7.0.2 | Type safety |
| React Router | 7.18.4 | Client-side routing |
| Axios | 1.20.0 | HTTP client |

### 4.2 Routes — VERIFIED

| Path | Component | Purpose |
|------|-----------|---------|
| `/` | `OfficeViewPage` | Default: office visualization |
| `/flow` | `AgentFlowPage` | Agent flow/pipeline diagram |
| `/agents` | `AgentsPage` | Agent CRUD management |
| `/skills` | `SkillsPage` | Skill management |
| `/tasks` | `TasksPage` | Task queue and history |
| `/projects` | `ProjectsPage` | Project management |
| `/dashboard` | `DashboardPage` | Statistics overview |

### 4.3 Office Visualization — VERIFIED

Three implementations exist:

1. **`OfficeCanvas.tsx`** — Flat 2D top-down grid layout
2. **`AgentsOfficeV3Canvas.tsx`** — Main view: pseudo-3D CSS transforms with SVG walkways, pan/zoom, interactive desks
3. **`IsometricOffice.tsx`** — Simplified card grid with isometric styling

**Key findings:**
- **No pixel art** — characters are CSS circles with letter initials
- **No sprite assets** — all visual elements are DOM/CSS
- **No agent movement animation** — agents are statically positioned at desks
- **State animations limited to**: pulsing "WORKING" badge, SVG energy particle flows
- **Layout is hardcoded** via `DEPARTMENTS` array with static x,y coordinates
- **Hybrid data**: fetches real agents/tasks via API but injects simulated progress percentages
- **Polling interval**: 3 seconds via `setInterval`
- **No SSE/WebSocket consumption** — despite backend SSE support

### 4.4 State Management — VERIFIED

- **Local React state only** (`useState`, `useEffect`)
- No global state store (no Redux, Zustand, or Context)
- Data fetched independently by each page/component
- No shared cache or optimistic updates

### 4.5 Agent Management UI — VERIFIED

- Agents: create, edit, delete via Modal forms with model selection dropdown
- Projects: CRUD via Modal forms
- Skills: CRUD + plugin scanner
- Tasks: create via Modal or sidebar quick-input, cancel, view output

---

## 5. Database Analysis

### 5.1 Schema — VERIFIED

```sql
-- agents: 14 columns including department and avatar
-- projects: 8 columns with working_directory and allowed_tools
-- skills: 7 columns with optional project_id FK
-- task_runs: 12 columns with events stored as JSON blob

-- Indexes on task_runs: agent_id, project_id, status, created_at
```

### 5.2 Missing for Target Architecture

| Missing Column/Table | Purpose |
|---------------------|---------|
| `agents.parent_id` | Agent hierarchy |
| `agents.role_type` | Manager vs Worker vs Specialist |
| `agents.max_concurrent` | Concurrency limits |
| `task_runs.parent_task_id` | Task delegation chains |
| `task_runs.assigned_by` | Who delegated the task |
| `events` table | Normalized event log (currently JSON blob in task_runs) |
| `approvals` table | Human approval gates |
| `agent_templates` table | Reusable agent definitions |

---

## 6. Integration Analysis

### 6.1 Current Architecture — VERIFIED

```
Frontend (React/Vite)
    │ HTTP polling (3s interval)
    ▼
Backend (FastAPI, port 8000)
    │ Python imports
    ▼
ConfigManager + DatabaseManager + RuntimeAdapter
    │ subprocess.Popen
    ▼
Claude CLI (`claude -p ... --output-format stream-json`)
    │ Environment: ANTHROPIC_BASE_URL=http://127.0.0.1:8082
    ▼
Free Claude Code Proxy (port 8082)
    │
    ▼
Model Provider (Claude API / potentially NVIDIA)
```

### 6.2 Missing Integration Points

- No WebSocket consumption on frontend despite backend support
- No SSE consumption on frontend despite backend support
- No global event aggregation across multiple concurrent runs
- No model discovery endpoint (frontend uses hardcoded model list)

---

## 7. Existing Tests — PARTIALLY VERIFIED

| File | Type | Status |
|------|------|--------|
| `test_setup.py` | Config/DB initialization | Diagnostic script, not proper test suite |
| `test_task.py` | Task execution test | Tests runtime adapter directly |
| `test_api.py` | API endpoint tests | Tests via HTTP requests |
| `test_claude_launch.py` | CLI launch test | Tests subprocess launch |
| `simple_test.py` | Basic import test | Minimal sanity check |
| `debug_task.py`, `debug_task2.py` | Debug harnesses | Not structured tests |
| `demo_poc.py`, `demo_api.py` | Demo scripts | Manual verification only |

**No automated test runner configured** — no pytest configuration, no test directory, no CI/CD pipeline.

---

## 8. Reusable Components

| Component | Can Reuse | Requires Extension |
|-----------|----------|-------------------|
| `ClaudeCodeRuntimeAdapter` | Core subprocess management, event parsing | Extract interface, remove mock fallback |
| `DatabaseManager` | SQLite CRUD pattern | Add hierarchy tables, event table |
| FastAPI router structure | API organization | Add WebSocket, global SSE |
| Pydantic models | Request validation | Add hierarchy fields |
| TypeScript types | Frontend type safety | Add parent/child, status enum |
| Office visualization concept | Layout and interaction patterns | Replace with real pixel art engine |
| API service layer | Axios configuration | Add SSE/WebSocket clients |

---

## 9. Technical Debt

1. **Dual storage** — agents in both JSON files and SQLite with no sync
2. **`sys.path.append`** — used in every API file instead of proper Python packaging
3. **Hardcoded paths** — plugin scanner references `C:\Users\taguo\...` paths
4. **No proper Python package** — no `pyproject.toml`, `setup.py`, or proper imports
5. **Mock fallback unlabeled** — silent fake execution masquerades as real
6. **`created_at`/`updated_at` always empty** — agent response always returns `""` for timestamps
7. **Duplicate config directories** — `poc/config/` and `poc/backend/config/` both contain `agents.json`
8. **No `.gitignore`** — committed `__pycache__`, `.pyc` files, and SQLite database
