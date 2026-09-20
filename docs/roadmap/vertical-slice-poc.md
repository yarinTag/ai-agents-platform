# Vertical Slice POC Plan

## 1. Objective

Prove the end-to-end architecture with the **smallest real workflow** that validates:
- Agent hierarchy (manager + child)
- Task delegation through orchestration
- Real runtime execution via Claude Code CLI
- Event streaming to the frontend
- Visual representation in the office UI

---

## 2. The Workflow

```
User creates a task: "Review the README.md and suggest improvements"
        │
        ▼
Root manager agent receives the task
        │
        ▼
Manager delegates to "Documentation Review" child agent
        │
        ▼
Child agent executes via Claude Code CLI (real subprocess)
    ├── Claude reads README.md (real file operation)
    ├── Claude generates review suggestions (real model output)
    └── Events stream: thought → tool_use → result
        │
        ▼
Backend persists events to event_log table
Backend streams events via SSE
        │
        ▼
Office UI shows:
    ├── Child agent at desk → WORKING animation
    ├── Event log updates in real-time
    └── On completion: child walks to manager desk
        │
        ▼
Manager receives child's result
Manager produces final summary
        │
        ▼
Office shows:
    ├── Manager → WORKING (processing child result)
    ├── Manager → COMPLETED
    └── Child → returns to desk → IDLE
        │
        ▼
Task marked as completed with final result
```

---

## 3. Scope — What's In

### 3.1 Backend

| Component | What to Build |
|-----------|--------------|
| Agent hierarchy | 2 agents: "Doc Manager" (parent) + "Doc Reviewer" (child) |
| Orchestration | Minimal delegator: manager delegates first child task, collects result |
| RuntimeAdapter | Wrap existing `ClaudeCodeRuntimeAdapter` with protocol |
| EventBus | Minimal in-process pub/sub with `event_log` persistence |
| Global SSE | Single endpoint streaming all events |
| Database | `agents` with parent_id, `tasks` with parent_task_id, `event_log` table |

### 3.2 Frontend

| Component | What to Build |
|-----------|--------------|
| SSE client | `EventSource` connection to global SSE endpoint |
| Office view | Minimal canvas update showing 2 agents with state transitions |
| Agent states | IDLE → WORKING → REPORTING → IDLE cycle |
| Movement | Simple agent movement from desk to manager desk on completion |
| Info panel | Show current task and real-time events for selected agent |

### 3.3 Runtime

| Component | What to Build |
|-----------|--------------|
| Real execution | Claude Code CLI subprocess with `stream-json` output |
| Real task | Read a file from the project directory and produce analysis |
| Event capture | Parse stream-json events and publish to EventBus |

---

## 4. Scope — What's Out

| Excluded | Reason |
|----------|--------|
| Multiple providers (NVIDIA) | POC validates architecture with one provider |
| Dynamic delegation | Manager assigns to a specific preconfigured child |
| Approval gates | Not needed for read-only file review |
| Agent templates | Agents preconfigured, not created from templates |
| Full pixel art sprites | Use simple colored shapes with state indicators |
| Authentication | POC runs locally |
| Concurrent children | Manager delegates to exactly one child |
| Retry/escalation | Simple pass/fail in POC |
| Character selection | Agents have fixed visual representation |

---

## 5. Prerequisites

### 5.1 Environment

- [ ] Claude Code CLI (`claude`) installed and in PATH
- [ ] Free Claude Code proxy running on `localhost:8082`
- [ ] Python 3.10+ with FastAPI, uvicorn
- [ ] Node.js 18+ with npm
- [ ] A real project directory with a `README.md` file to review

### 5.2 Completed Phases

- [ ] Phase 0 (code hygiene) — at minimum: mock fallback removed, imports fixed
- [ ] Phase 1 (partial) — RuntimeAdapter protocol and EventBus

---

## 6. Implementation Steps

### Step 1: Create the Two Agents

```python
# Seed data — Doc Manager
manager = AgentConfig(
    id="doc-manager",
    name="Documentation Manager",
    description="Manages documentation review tasks",
    system_prompt="You are a documentation manager. When given a review task, "
                  "summarize the results from your team's review.",
    model="default",
    role_type="manager",
    parent_id=None,
    department="Engineering",
)

# Seed data — Doc Reviewer (child)
reviewer = AgentConfig(
    id="doc-reviewer",
    name="Documentation Reviewer",
    description="Reviews documentation for clarity and completeness",
    system_prompt="You are a documentation reviewer. Read the specified file "
                  "and provide specific suggestions for improvement. "
                  "Focus on clarity, completeness, and accuracy.",
    model="default",
    role_type="worker",
    parent_id="doc-manager",
    department="Engineering",
)
```

### Step 2: Create Minimal Orchestrator

```python
class MinimalOrchestrator:
    """POC orchestrator — single manager + single child delegation."""

    def __init__(self, runtime: RuntimeAdapter, event_bus: EventBus):
        self.runtime = runtime
        self.event_bus = event_bus

    async def submit_task(self, task: Task) -> str:
        """Submit a task to the assigned agent."""
        agent = get_agent(task.agent_id)

        if agent.role_type == "manager":
            return await self._handle_manager_task(task, agent)
        else:
            return await self._handle_worker_task(task, agent)

    async def _handle_manager_task(self, task, manager):
        # 1. Find child agent
        children = get_children(manager.id)
        if not children:
            # Manager executes directly if no children
            return await self._handle_worker_task(task, manager)

        child = children[0]

        # 2. Delegate to child
        child_task = create_child_task(
            prompt=task.prompt,
            agent_id=child.id,
            parent_task_id=task.id,
            assigned_by=manager.id
        )
        self.event_bus.publish(event("task.delegated", task_id=task.id, child_task_id=child_task.id))

        # 3. Execute child task
        child_result = await self._handle_worker_task(child_task, child)

        # 4. Feed result to manager for final summary
        summary_prompt = f"Your team member reviewed the documentation and found:\n\n{child_result}\n\nProvide a brief executive summary."

        manager_execution_id = self.runtime.start_execution(
            agent_config=manager,
            prompt=summary_prompt
        )

        # 5. Wait for manager result
        manager_result = await self._wait_for_completion(manager_execution_id)

        # 6. Complete the task
        task.status = "completed"
        task.result = manager_result
        return manager_result

    async def _handle_worker_task(self, task, agent):
        # Direct execution via runtime
        project = get_project(task.project_id) if task.project_id else None
        execution_id = self.runtime.start_execution(
            agent_config=agent,
            project_config=project,
            prompt=task.prompt
        )
        self.event_bus.publish(event("execution.started", task_id=task.id, execution_id=execution_id))

        result = await self._wait_for_completion(execution_id)
        return result
```

### Step 3: Create EventBus with SSE

```python
class POCEventBus:
    def __init__(self, db_manager):
        self._subscribers = []
        self._db = db_manager

    def publish(self, event: PlatformEvent):
        self._db.save_event(event)  # Persist
        for handler in self._subscribers:
            handler(event)          # Notify

    def subscribe(self, handler):
        self._subscribers.append(handler)
        return lambda: self._subscribers.remove(handler)
```

### Step 4: Create Global SSE Endpoint

```python
@router.get("/stream")
async def event_stream():
    queue = asyncio.Queue()

    def handler(event):
        queue.put_nowait(event)

    unsubscribe = event_bus.subscribe(handler)

    async def generate():
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30)
                    yield f"event: {event.event_type}\ndata: {json.dumps(event.to_dict())}\n\n"
                except asyncio.TimeoutError:
                    yield f"event: heartbeat\ndata: {{}}\n\n"
        finally:
            unsubscribe()

    return StreamingResponse(generate(), media_type="text/event-stream")
```

### Step 5: Create Minimal Office Canvas Update

```typescript
// SSE client
const eventSource = new EventSource('/api/v1/events/stream');

eventSource.addEventListener('execution.started', (e) => {
  const data = JSON.parse(e.data);
  setAgentState(data.agent_id, 'working');
});

eventSource.addEventListener('task.completed', (e) => {
  const data = JSON.parse(e.data);
  setAgentState(data.agent_id, 'moving_to_manager');
  // After animation completes:
  setTimeout(() => setAgentState(data.agent_id, 'idle'), 3000);
});
```

### Step 6: Create Visual State Transitions

For the POC, modify the existing `AgentsOfficeV3Canvas.tsx` to:
1. Replace polling with SSE connection
2. Map agent states to visual indicators:
   - IDLE: grey badge
   - WORKING: green pulsing badge + typing dots
   - MOVING_TO_MANAGER: animated position change
   - REPORTING: speech bubble at manager
   - ERROR: red badge

---

## 7. Success Criteria

### 7.1 Must Pass (POC is valid)

| # | Criterion | Verification |
|---|-----------|-------------|
| 1 | User submits task via API | `POST /api/v1/tasks/` returns 201 with task ID |
| 2 | Manager agent receives task | Event `task.assigned` for doc-manager in event_log |
| 3 | Manager delegates to child | Event `task.delegated` with child task ID |
| 4 | Child executes real Claude Code subprocess | `subprocess.Popen` creates process, process reads actual file |
| 5 | Runtime emits real stream-json events | Events with types `thought`, `tool_use`, `result` from actual CLI |
| 6 | Events persisted to event_log | `SELECT * FROM event_log WHERE task_id = ?` returns events |
| 7 | Events stream via SSE | `EventSource` receives events in real-time |
| 8 | Office shows child agent working | Visual state changes from IDLE to WORKING |
| 9 | Child result returned to manager | Manager's execution receives child result as input |
| 10 | Manager produces final result | Task completed with summary result |
| 11 | Office shows workflow completion | Agent returns to idle state after reporting |

### 7.2 Should Pass (POC is robust)

| # | Criterion |
|---|-----------|
| 12 | SSE reconnection replays missed events |
| 13 | Cancelling the task terminates child process |
| 14 | Child execution failure is reported to manager |
| 15 | Multiple POC runs don't interfere with each other |

### 7.3 Nice to Have (POC is polished)

| # | Criterion |
|---|-----------|
| 16 | Agent walk animation from desk to manager |
| 17 | Event log panel shows events in real-time |
| 18 | Task result visible in desk drawer |

---

## 8. Limitations

| Limitation | Explanation |
|-----------|-------------|
| Single child agent | Manager delegates to exactly one preconfigured child |
| No dynamic delegation | Manager doesn't choose which agent to use |
| No retry on failure | If child fails, task fails |
| No concurrent children | One child executes at a time |
| No approval gates | Task executes without human approval |
| Minimal pixel art | Uses enhanced CSS shapes, not full sprite sheets |
| No authentication | Runs on localhost without auth |
| No model switching | Both agents use default model |
| File read only | Child agent reviews a file but doesn't modify it |

---

## 9. Test Plan

### 9.1 Unit Tests

```python
# test_orchestrator.py
def test_manager_delegates_to_child():
    """Manager with children delegates task to first child."""

def test_worker_executes_directly():
    """Worker with no children executes task directly."""

def test_child_result_forwarded_to_manager():
    """Child result is included in manager's summary prompt."""

def test_delegation_creates_child_task():
    """Delegation creates a new task with parent_task_id set."""

# test_event_bus.py
def test_publish_persists_to_db():
    """Published events are saved to event_log table."""

def test_subscribe_receives_events():
    """Subscriber handler is called for published events."""

def test_replay_returns_events_since_timestamp():
    """Replay returns events after the given timestamp."""
```

### 9.2 Integration Tests

```python
# test_poc_integration.py
def test_end_to_end_with_mock_adapter():
    """Full flow with MockAdapter (no real CLI)."""
    # 1. Create manager + child agents
    # 2. Submit task
    # 3. Verify delegation events
    # 4. Verify child execution events (mock)
    # 5. Verify result forwarding
    # 6. Verify task completion

def test_end_to_end_with_real_adapter():
    """Full flow with real Claude Code CLI (requires FCC running)."""
    # Same as above but with real execution
    # Mark as @pytest.mark.integration (skippable in CI)
```

### 9.3 Frontend Tests

```typescript
// eventStream.test.ts
test('SSE client receives and dispatches events')
test('SSE client reconnects on disconnection')
test('Agent state machine transitions correctly')
```

---

## 10. File Changes Summary

### New Files

| File | Purpose |
|------|---------|
| `poc/runtime/protocol.py` | RuntimeAdapter protocol |
| `poc/runtime/claude_adapter.py` | Wrapped existing adapter |
| `poc/runtime/mock_adapter.py` | Explicitly labeled mock |
| `poc/events/bus.py` | In-process event bus |
| `poc/events/models.py` | Event types and structures |
| `poc/orchestration/engine.py` | Minimal orchestrator |
| `poc/backend/api/orchestration.py` | Orchestration API endpoint |
| `poc/tests/test_orchestrator.py` | Orchestrator unit tests |
| `poc/tests/test_event_bus.py` | EventBus unit tests |
| `poc/tests/test_poc_integration.py` | Integration tests |
| `dashboard/src/services/eventStream.ts` | SSE client |
| `dashboard/src/engine/AgentStateMachine.ts` | Visual state machine |

### Modified Files

| File | Changes |
|------|---------|
| `persistence.py` | Add event_log table, hierarchy columns |
| `config.py` | Add parent_id, role_type to AgentConfig |
| `backend/api/events.py` | Add global SSE endpoint |
| `backend/api/tasks.py` | Connect to EventBus |
| `backend/dependencies.py` | Register EventBus, orchestrator |
| `backend/main.py` | Add orchestration router |
| `dashboard/src/pages/OfficeView.tsx` | SSE instead of polling |
| `dashboard/src/components/office/AgentsOfficeV3Canvas.tsx` | State-driven visuals |
| `dashboard/src/types/agent.ts` | Add hierarchy types |
| `dashboard/src/services/api.ts` | Add orchestration API calls |

---

## 11. Estimated Effort

| Component | Effort |
|-----------|--------|
| RuntimeAdapter protocol + wrapper | 0.5 day |
| EventBus + event_log table | 0.5 day |
| Global SSE endpoint | 0.5 day |
| Database schema extensions | 0.5 day |
| Minimal orchestrator | 1-2 days |
| Frontend SSE client | 0.5 day |
| Office visual state updates | 1 day |
| Seed data + testing | 1 day |
| **Total** | **~5-7 days** |

---

## 12. Definition of Done

The POC is complete when:

1. ✅ A user submits a task through the API
2. ✅ The task reaches a manager agent
3. ✅ The manager delegates to a child agent
4. ✅ The child executes a **real** Claude Code subprocess (not a mock)
5. ✅ The runtime emits **real** stream-json events
6. ✅ Events are persisted to the `event_log` table
7. ✅ Events stream to the frontend via SSE
8. ✅ The office UI shows the child agent working
9. ✅ The child reports its result back through the orchestrator
10. ✅ The manager receives the result and produces a summary
11. ✅ The office UI reflects the completed workflow
12. ✅ All unit tests pass
13. ✅ Integration test passes with real adapter (when FCC is available)
