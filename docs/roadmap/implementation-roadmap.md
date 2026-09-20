# Implementation Roadmap

## Guiding Principle

Each phase delivers a working, testable increment. No phase depends on completion of all parts of a previous phase — only on specific capabilities.

---

## Phase 0 — Codebase Hygiene and Baseline (Week 1)

### Objective
Clean up technical debt, establish proper Python packaging, resolve dual-storage issue, and create a solid foundation for incremental development.

### Scope
- Create proper Python package structure with `pyproject.toml`
- Add `.gitignore` for `__pycache__`, `.pyc`, `*.db`, `node_modules`
- Eliminate `sys.path.append` hacks in all API files
- Resolve dual storage: make SQLite the single source of truth, JSON config as import-only seed
- Remove hardcoded Windows paths from `skills.py` plugin scanner
- Remove mock fallback from `runtime_adapter.py` (lines 409-434) — replace with proper error propagation
- Add proper error logging (Python `logging` module)
- Fix `created_at`/`updated_at` responses to return actual timestamps from DB
- Fix SSE content type in `tasks.py`
- Configure SQLite WAL mode for better concurrent access

### Files/Modules to Change
- `poc/` → restructure as Python package
- [`runtime_adapter.py`](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/runtime_adapter.py) — remove mock fallback
- [`persistence.py`](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/persistence.py) — add WAL mode
- [`backend/dependencies.py`](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/backend/dependencies.py) — remove sys.path hacks
- All `backend/api/*.py` files — fix imports
- [`backend/api/skills.py`](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/backend/api/skills.py) — remove hardcoded paths
- [`backend/api/tasks.py`](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/backend/api/tasks.py) — fix SSE content type
- [`backend/api/agents.py`](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/backend/api/agents.py) — fix timestamps

### Dependencies
- None (first phase)

### Risks
- Restructuring imports may break existing `demo_poc.py` and test scripts
- Removing mock fallback means execution will fail if Claude CLI is unavailable

### Validation
- `python -m pytest` (once test structure established)
- `python start_api.py` starts without errors
- `npm run build` in dashboard still succeeds
- Existing CRUD operations work via API
- Creating a task with invalid agent returns proper error (not mock success)

### Acceptance Criteria
- [ ] No `sys.path.append` in any production code
- [ ] SQLite is sole source of truth for agents, projects, skills
- [ ] Mock fallback removed; execution errors are surfaced, not hidden
- [ ] All API responses include real timestamps
- [ ] `.gitignore` excludes `__pycache__`, `*.pyc`, `*.db`, `node_modules`, `dist`

### Out of Scope
- Agent hierarchy, orchestration, pixel art, new features

---

## Phase 1 — Runtime Adapter Protocol and Event Foundation (Week 2)

### Objective
Extract the `RuntimeAdapter` protocol, add the in-process event bus, create the `event_log` table, and refactor SSE to stream from the event bus.

### Scope
- Define `RuntimeAdapter` protocol (abstract interface)
- Wrap existing `ClaudeCodeRuntimeAdapter` to implement the protocol
- Create `RuntimeCapabilities` dataclass
- Create `PlatformEvent` dataclass and `EventType` enum
- Create in-process `EventBus` class
- Create `event_log` table in SQLite
- Refactor `tasks.py` SSE endpoint to stream from EventBus instead of per-run queue
- Add global SSE endpoint: `GET /api/v1/events/stream`
- Add event replay capability (query `event_log` by timestamp)
- Create a `MockAdapter` (explicitly labeled, for testing only)

### Files/Modules to Change
- **NEW**: `poc/runtime/protocol.py` — RuntimeAdapter protocol
- **NEW**: `poc/runtime/claude_adapter.py` — wraps existing adapter
- **NEW**: `poc/events/bus.py` — EventBus
- **NEW**: `poc/events/models.py` — event types and structures
- [`persistence.py`](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/persistence.py) — add `event_log` table
- [`backend/api/tasks.py`](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/backend/api/tasks.py) — refactor SSE
- [`backend/api/events.py`](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/backend/api/events.py) — add global SSE stream
- [`backend/dependencies.py`](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/backend/dependencies.py) — register EventBus

### Dependencies
- Phase 0 (clean imports, proper packaging)

### Risks
- Event bus must handle high-frequency events without blocking execution threads
- SQLite write performance for event log during heavy execution

### Validation
- Start a task → events appear in `event_log` table
- SSE endpoint streams events in real-time
- Disconnecting and reconnecting SSE with `?since=<timestamp>` replays missed events
- MockAdapter produces clearly labeled mock events

### Acceptance Criteria
- [ ] `RuntimeAdapter` protocol defined with documented methods
- [ ] `ClaudeCodeAdapter` wraps existing adapter without changing behavior
- [ ] Events persisted to `event_log` table during execution (not just after)
- [ ] Global SSE endpoint works with agent_id/task_id filters
- [ ] Event replay works from timestamp

### Out of Scope
- Agent hierarchy, orchestration, pixel art

---

## Phase 2 — Agent Hierarchy and Database Migration (Week 3)

### Objective
Add parent-child relationships to the agent data model, extend the database schema, create hierarchy API endpoints, and enable building agent teams.

### Scope
- Extend `AgentConfig` with `parent_id`, `role_type`, `max_concurrent_children`
- Extend `agents` table with hierarchy columns (ALTER TABLE)
- Add hierarchy validation (no circular references, depth limits)
- Add API endpoints: `GET /api/v1/agents/{id}/children`, `GET /api/v1/agents/{id}/hierarchy`
- Extend task model with `parent_task_id`, `assigned_by`, `root_task_id`
- Extend `task_runs` table with delegation columns
- Create `agent_templates` table and seed with defaults
- Add agent template CRUD endpoints
- Update frontend agent types with hierarchy fields
- Update agent creation form to include parent selection and role type

### Files/Modules to Change
- [`config.py`](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/config.py) — extend `AgentConfig`
- [`persistence.py`](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/persistence.py) — ALTER TABLE, new templates table
- [`backend/api/agents.py`](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/backend/api/agents.py) — hierarchy endpoints
- **NEW**: `backend/api/templates.py` — agent template CRUD
- [`dashboard/src/types/agent.ts`](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/dashboard/src/types/agent.ts) — add hierarchy types
- [`dashboard/src/pages/Agents.tsx`](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/dashboard/src/pages/Agents.tsx) — add hierarchy UI
- [`dashboard/src/services/api.ts`](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/dashboard/src/services/api.ts) — add hierarchy API calls

### Dependencies
- Phase 0 (schema migration patterns)
- Phase 1 (event types for hierarchy changes)

### Risks
- Existing agents have no parent_id — migration must handle NULL parents gracefully
- Frontend hierarchy visualization complexity

### Validation
- Create manager agent with child agents via API
- Query hierarchy returns correct tree structure
- Circular reference prevention works
- Existing agents still function with NULL parent_id

### Acceptance Criteria
- [ ] Agents have parent_id and role_type fields
- [ ] Hierarchy API returns tree structure
- [ ] Agent templates can be created and used to instantiate agents
- [ ] Tasks have parent_task_id for delegation tracking
- [ ] Frontend shows parent agent in agent creation form

### Out of Scope
- Orchestration engine (hierarchy exists but no automatic delegation yet), pixel art

---

## Phase 3 — Orchestration Engine (Weeks 4-5)

### Objective
Build the orchestration layer that enables a manager agent to delegate tasks to child agents, collect results, and report back through the chain.

### Scope
- Create `OrchestrationEngine` class
- Implement task delegation logic (manager → child agents)
- Implement result collection and forwarding
- Implement failure handling (retry, escalate, abort policies)
- Implement concurrency control (max concurrent children)
- Implement timeout enforcement
- Create approval gates (for sensitive operations)
- Create `approvals` table
- Add orchestration API endpoints
- Connect orchestration events to EventBus

### Files/Modules to Change
- **NEW**: `poc/orchestration/engine.py` — main orchestration logic
- **NEW**: `poc/orchestration/delegator.py` — task delegation
- **NEW**: `poc/orchestration/collector.py` — result collection
- **NEW**: `poc/orchestration/policies.py` — retry, timeout, concurrency policies
- **NEW**: `poc/backend/api/orchestration.py` — orchestration API
- [`persistence.py`](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/persistence.py) — add `approvals` table
- [`backend/main.py`](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/backend/main.py) — register orchestration router

### Dependencies
- Phase 1 (RuntimeAdapter protocol, EventBus)
- Phase 2 (agent hierarchy, task delegation fields)

### Risks
- **Highest-risk phase**: orchestration is the most complex new capability
- Delegation output parsing depends on model response format — requires robust parsing
- Concurrent child execution may overwhelm system resources
- Deadlock potential: manager waiting for child that's waiting for parent

### Validation
- Submit a task to a manager agent → manager delegates to child → child executes → result flows back to manager
- Concurrent child limit enforced (3rd child waits when limit is 2)
- Timeout cancels stalled child execution
- Approval gate pauses execution until approved
- Failed child triggers retry or escalation based on policy

### Acceptance Criteria
- [ ] End-to-end delegation: task → manager → child → result → manager → completion
- [ ] Concurrency limits enforced
- [ ] Timeouts work
- [ ] Approval gates work
- [ ] Failure policies (retry, escalate, abort) are configurable
- [ ] All orchestration events appear in EventBus and event_log

### Out of Scope
- Pixel art office, dynamic delegation (auto-selecting which agent to use)

---

## Phase 4 — Pixel Art Office Foundation (Weeks 6-7)

### Objective
Replace the current CSS pseudo-3D office with a real pixel art Canvas-based visualization that renders agent state from the EventBus.

### Scope
- Create HTML5 Canvas rendering engine for the office scene
- Design and create pixel art sprite sheets (agents, furniture, floor tiles)
- Implement sprite animation system (idle, working, walking, error states)
- Implement office layout engine (configurable desk/department positions)
- Connect to global SSE endpoint for real-time state updates
- Implement agent state-to-visual mapping (deterministic)
- Implement agent movement (walking from desk to manager desk and back)
- Implement click-to-select agent (canvas hit testing)
- Keep DOM overlays for tooltips, drawers, and control panels
- Keep existing `AgentDeskDrawer` but connect to real-time events

### Files/Modules to Change
- **NEW**: `dashboard/src/components/office/PixelOfficeCanvas.tsx` — main Canvas component
- **NEW**: `dashboard/src/engine/PixelRenderer.ts` — Canvas rendering engine
- **NEW**: `dashboard/src/engine/SpriteSystem.ts` — sprite loading and animation
- **NEW**: `dashboard/src/engine/OfficeLayout.ts` — configurable layout manager
- **NEW**: `dashboard/src/engine/AgentStateMachine.ts` — visual state machine
- **NEW**: `dashboard/src/services/eventStream.ts` — SSE client
- **NEW**: `dashboard/src/assets/sprites/` — pixel art assets
- [`dashboard/src/pages/OfficeView.tsx`](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/dashboard/src/pages/OfficeView.tsx) — integrate new canvas
- [`dashboard/src/constants/models.ts`](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/dashboard/src/constants/models.ts) — dynamic model list from API

### Dependencies
- Phase 1 (EventBus, global SSE)
- Phase 2 (agent hierarchy for visual layout)
- Phase 3 (orchestration events for state transitions)

### Risks
- Pixel art asset creation is a significant art/design effort
- Canvas hit testing requires careful implementation
- Animation frame rate must stay smooth (60fps target)
- Sprite sheet memory usage for many agents

### Validation
- Office renders with pixel art agents at assigned desks
- Starting a task shows agent working animation
- Task completion shows agent walking to manager
- Error state shows error visual
- Clicking agent opens desk drawer with real-time info
- SSE disconnection shows reconnecting indicator

### Acceptance Criteria
- [ ] Canvas-based pixel art office renders correctly
- [ ] Agent sprites animate based on backend state (not simulated)
- [ ] At least 4 agent states visually distinct (idle, working, walking, error)
- [ ] Agent walks to manager desk on task completion
- [ ] Real-time updates via SSE (no polling)
- [ ] Works with at least 10 concurrent agents without frame drops

### Out of Scope
- Multiple office floors/rooms, 3D effects, custom sprite editor

---

## Phase 5 — Agent Management Platform (Week 8)

### Objective
Build the agent builder/management UI that allows creating agent teams, defining hierarchies, selecting characters, and managing configurations visually.

### Scope
- Agent builder wizard (step-by-step agent creation)
- Hierarchy visualization and editor (drag-and-drop parent assignment)
- Character/avatar selector (choose pixel art sprite)
- Model selection with dynamic model discovery from backend
- Agent template gallery
- Project agent assignment (which agents work on which project)
- Bulk operations (create team from template)

### Files/Modules to Change
- **NEW**: `dashboard/src/pages/AgentBuilder.tsx`
- **NEW**: `dashboard/src/components/agents/HierarchyEditor.tsx`
- **NEW**: `dashboard/src/components/agents/CharacterSelector.tsx`
- **NEW**: `dashboard/src/components/agents/TemplateGallery.tsx`
- Updated: agent API endpoints for hierarchy management
- Updated: App.tsx with new routes

### Dependencies
- Phase 2 (hierarchy data model)
- Phase 4 (pixel art sprites for character selection)

### Risks
- Hierarchy editor UX complexity
- Template system must be flexible without being overwhelming

### Validation
- Create a full team from template (manager + 3 workers)
- Assign characters to agents, see them in office
- Edit hierarchy by changing parent assignments
- New agent appears at desk in office view

### Acceptance Criteria
- [ ] Agent builder wizard creates fully configured agent
- [ ] Hierarchy editor visualizes and allows editing parent-child relationships
- [ ] Character selector shows available sprites
- [ ] Template gallery shows reusable agent definitions
- [ ] Model selection shows dynamically discovered models

### Out of Scope
- Custom sprite upload, AI-generated agent personas

---

## Phase 6 — Security, Authentication, and Production Hardening (Week 9-10)

### Objective
Add authentication, authorization, security boundaries, and operational hardening.

### Scope
- API authentication (API key-based, upgradeable to JWT)
- Agent tool permission enforcement at runtime
- Make `--dangerously-skip-permissions` configurable per-agent
- Remove hardcoded credentials from source
- Add environment variable-based credential management
- Add audit logging for all agent actions
- Add concurrent execution limits
- Add rate limiting on API endpoints
- Add request correlation IDs
- Add structured error responses
- Security review of prompt injection risks

### Dependencies
- All previous phases (security is applied across the board)

### Risks
- Adding authentication may break existing frontend without careful coordination
- Tool permission enforcement requires understanding Claude Code's permission model

### Validation
- Unauthenticated requests rejected
- Agent cannot execute tools outside its permission set
- Audit log captures all task executions
- Rate limiting prevents abuse
- Credentials not visible in logs or API responses

### Acceptance Criteria
- [ ] API requires authentication
- [ ] Agent tool permissions enforced
- [ ] `--dangerously-skip-permissions` not used by default
- [ ] No credentials in source code
- [ ] Audit log for all executions
- [ ] Rate limiting active

### Out of Scope
- Multi-tenant architecture, SSO integration, fine-grained RBAC

---

## Phase Summary

| Phase | Duration | Focus | Key Deliverable |
|-------|----------|-------|-----------------|
| 0 | 1 week | Hygiene | Clean codebase, proper packaging |
| 1 | 1 week | Foundation | RuntimeAdapter protocol, EventBus, global SSE |
| 2 | 1 week | Data model | Agent hierarchy, task delegation, templates |
| 3 | 2 weeks | Core feature | Orchestration engine with delegation and result flow |
| 4 | 2 weeks | Visualization | Pixel art office with real-time state rendering |
| 5 | 1 week | Management | Agent builder, hierarchy editor, template gallery |
| 6 | 2 weeks | Hardening | Auth, permissions, audit, rate limiting |

**Total estimated: 10 weeks for full platform**

**Minimum viable vertical slice: Phases 0-3 (5 weeks)** — delivers a working orchestration platform with real execution, even without pixel art.
