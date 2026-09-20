# Runtime and Wrapper Audit

## 1. Execution Flow

### 1.1 How Execution Starts

The entry point is the HTTP endpoint `POST /api/v1/tasks/` defined in [`tasks.py`](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/backend/api/tasks.py#L93-L153).

```python
# tasks.py L128
run_id = runtime_adapter.start_task(
    agent_id=agent.id,
    project_id=task_data.project_id,
    prompt=prompt
)
```

This calls [`ClaudeCodeRuntimeAdapter.start_task()`](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/runtime_adapter.py#L239-L297) which:
1. Resolves `AgentConfig` from `config_manager` (L264-266)
2. Optionally resolves `ProjectConfig` (L268-272)
3. Generates UUID `run_id` (L275)
4. Creates `AgentRun` record with status `QUEUED` (L278-285)
5. Stores in memory dict `_runs[run_id]` (L287)
6. Spawns daemon thread executing `_execute_task()` (L290-295)
7. Returns `run_id` immediately (L297)

### 1.2 Process Launch

Inside [`_execute_task()`](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/runtime_adapter.py#L299-L466):

```python
# L339-348
process = subprocess.Popen(
    cmd,                          # Built by _build_claude_command()
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    env=env,                      # Built by _build_claude_env()
    cwd=work_dir,                 # From ProjectConfig or os.getcwd()
    text=True,
    bufsize=1,
    universal_newlines=True
)
```

### 1.3 Output Stream Processing

A separate [`_output_reader`](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/runtime_adapter.py#L181-L237) thread reads stdout line-by-line:

```python
while not stop_event.is_set() and process.poll() is None:
    line = process.stdout.readline()
    if line:
        event = self._parse_claude_output_line(line)  # JSON parse
        if event:
            event['_timestamp'] = time.time()
            event['_run_id'] = run_id
            event_queue.put(event)
```

Events are consumed in `_execute_task()` main loop with 0.1s timeout polling.

### 1.4 Event Types Handled

| Event Type | Action | Location |
|-----------|--------|----------|
| `result` | Sets status=COMPLETED, stores result | L376-380 |
| `error` | Sets status=FAILED, stores error message | L381-385 |
| `end_of_output` | Marks completion based on whether result exists | L387-392 |
| `raw` (JSON parse fail) | Stored as `{"type": "raw", "content": ...}` | L176-178 |
| All others | Appended to `run.events` list | L373 |

### 1.5 Process Cleanup

The `finally` block (L434-466) ensures:
1. `ended_at` timestamp set
2. Task run saved to SQLite via `db_manager.save_task_run(run)`
3. `_stop_events[run_id]` signaled
4. Process terminated: `terminate()` → `wait(5s)` → `kill()` if needed
5. All dict entries cleaned up (`_processes`, `_event_queues`, `_reader_threads`, `_stop_events`)

---

## 2. Model Selection Flow

### 2.1 Where Models Are Defined

Models are defined per-agent in [`AgentConfig.model`](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/config.py#L20):

```python
@dataclass
class AgentConfig:
    model: str = "default"  # e.g., "sonnet", "opus", "fable"
```

### 2.2 How Models Reach the CLI

In [`_build_claude_command()`](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/runtime_adapter.py#L130-L131):

```python
if agent_config.model and agent_config.model.lower() != "default":
    cmd.extend(["--model", agent_config.model.lower()])
```

### 2.3 How the FCC Proxy Routes Models

The environment sets `ANTHROPIC_BASE_URL=http://127.0.0.1:8082`. The Claude CLI sends API requests to this proxy, which:
- Intercepts model selection from the `--model` flag
- Routes to the appropriate provider backend
- `CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY=1` enables the proxy to advertise available models

### 2.4 NVIDIA Model Compatibility

**Status: NOT VERIFIED**

The architecture allows passing arbitrary model strings (e.g., `nvidia_nim/nvidia/nemotron-3-super-120b-a12b`) to the CLI. Whether the FCC proxy supports NVIDIA models depends on:
1. FCC proxy configuration (not in this codebase)
2. Whether NVIDIA models support Claude Code's tool-use protocol
3. Whether streaming output format is compatible

The existing `agents.json` shows `"model": "fable"` — which is a Claude model routed through FCC.

**Frontend model list** in [`models.ts`](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/dashboard/src/constants/models.ts) only includes Claude models:
```typescript
export const AI_MODELS: ModelOption[] = [
  { label: 'Default', value: 'default' },
  { label: 'Sonnet', value: 'sonnet' },
  { label: 'Opus', value: 'opus' },
  { label: 'Haiku', value: 'haiku' },
  { label: 'Fable', value: 'fable' },
];
```

NVIDIA models are **not listed** in the frontend but could be passed through the API.

### 2.5 Model Selection Persistence

- **SQLite**: `agents.model` column persisted ([`persistence.py` L53](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/persistence.py#L53))
- **JSON config**: `model` field in `agents.json`
- **Per-agent only**: No per-task or per-session model override

### 2.6 Model Override for Child Agents

**NOT IMPLEMENTED**. There is no child agent concept, so model override per child does not exist. However, the architecture of passing model through `AgentConfig` makes this straightforward to add — create a child `AgentConfig` with a different model string.

---

## 3. Sub-Agent Capability Analysis

### 3.1 Current State: Flat Architecture

The system has **no concept of agent hierarchy**:

1. **Data model** — `AgentConfig` and the `agents` table have no `parent_id`, `manager_id`, `role_type`, or hierarchy fields
2. **Runtime** — each `start_task()` creates an independent process. There is no mechanism for one agent's execution to spawn or control another agent
3. **Result flow** — task results are stored per-run in `task_runs`. No mechanism for forwarding results from one agent to another
4. **Orchestration** — the system executes exactly what the user submits: one prompt → one agent → one subprocess

### 3.2 Three Types of Sub-Agents (Distinction)

| Type | Description | Current Status |
|------|-------------|---------------|
| **Runtime-native sub-agents** | Claude Code CLI internally spawning sub-agents | **UNKNOWN** — depends on Claude Code capabilities, not controlled by this platform |
| **Application-managed agents** | Platform orchestration spawning multiple agents | **NOT IMPLEMENTED** — no orchestrator exists |
| **Model-generated delegation** | The model's own output requesting delegation | **NOT IMPLEMENTED** — no mechanism to intercept and act on delegation instructions |

### 3.3 What Claude Code Supports Natively

Based on the CLI flags used:
- `--resume <session_id>` and `--fork-session` ([L133-136](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/runtime_adapter.py#L133-L136)) — **session management exists**, which is a prerequisite for session-based sub-agent tracking
- `--output-format stream-json` — provides structured event output that could potentially include sub-agent events if Claude Code emits them

**Whether Claude Code CLI emits sub-agent events in its stream-json output is UNKNOWN and requires investigation.**

---

## 4. Verified API Boundaries

### 4.1 Runtime Adapter Public API

```python
class ClaudeCodeRuntimeAdapter:
    def start_task(agent_id, project_id, prompt, session_id?, fork_session?) -> str  # returns run_id
    def get_run_status(run_id) -> Optional[AgentRun]
    def list_runs() -> List[AgentRun]
    def cancel_run(run_id) -> bool
    def subscribe_to_events(run_id, handler) -> Callable[[], None]  # returns unsubscribe fn
```

### 4.2 SSE Event Stream

The SSE endpoint at `/api/v1/tasks/{run_id}/events` ([`tasks.py` L263-391](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/backend/api/tasks.py#L263-L391)):
- Bridges the sync `subscribe_to_events()` queue to async SSE via `asyncio.Queue`
- Sends `connected`, `event`, `heartbeat`, `update`, and `close` SSE event types
- 30-second heartbeat timeout
- Terminates on `end_of_output`, `result`, or `error` events

**Issue**: The SSE endpoint uses `StreamingResponse` with `media_type="text/plain"` ([L383](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/backend/api/tasks.py#L383)) but sets `Content-Type: text/event-stream` in headers. The `media_type` parameter overrides the header, potentially causing incorrect content type. Also, events are yielded as dicts rather than properly formatted SSE text (`data: ...\n\n`).

---

## 5. Limitations

### 5.1 Runtime Limitations

1. **Single runtime only** — hardcoded to Claude Code CLI via subprocess
2. **No runtime abstraction** — no protocol/interface for swappable runtimes
3. **In-memory state** — all active run tracking is in Python dicts, lost on restart
4. **No reconnection** — if SSE client disconnects, no replay of missed events
5. **Thread-per-run** — scalability limited by OS thread limits
6. **No rate limiting** — unlimited concurrent subprocess launches
7. **Stderr ignored** — `stderr=subprocess.PIPE` but never read (potential deadlock for large stderr)

### 5.2 Security Limitations

1. **`--dangerously-skip-permissions`** always set — no permission control
2. **Proxy credentials hardcoded** — `"freecc"` auth token in source
3. **No API authentication** — all endpoints publicly accessible
4. **No workspace boundary enforcement** — `allowed_tools` ignored
5. **No audit trail** — no logging of what tools agents execute

### 5.3 Observability Limitations

1. **Events are a JSON blob** — stored as single TEXT column, not queryable
2. **No event IDs** — events have timestamps but no unique identifiers
3. **No event ordering guarantee** — Python Queue is FIFO but cross-run ordering undefined
4. **No event persistence during execution** — events only saved to DB after run completes

---

## 6. Recommended Integration Approach

### 6.1 Keep the Runtime Adapter

The `ClaudeCodeRuntimeAdapter` works correctly for its intended purpose. Do not replace it. Instead:

1. **Extract a `RuntimeAdapter` Protocol**:
   ```python
   class RuntimeAdapter(Protocol):
       def start_task(self, agent_id, project_id, prompt, ...) -> str: ...
       def get_run_status(self, run_id) -> Optional[AgentRun]: ...
       def cancel_run(self, run_id) -> bool: ...
       def subscribe_to_events(self, run_id, handler) -> Callable: ...
   ```

2. **Wrap for orchestration**: Create an `OrchestratedRuntime` that adds hierarchy tracking around the existing adapter

3. **Remove the mock fallback**: Replace lines 409-434 with proper error propagation

4. **Add event persistence**: Save events to a normalized table during execution, not just at completion

### 6.2 Add Orchestration Above the Runtime

```
User Task → Orchestrator → Assigns to Manager Agent
                              │
                              ├─ Manager runs via RuntimeAdapter
                              │   └─ Manager's output may contain delegation instructions
                              │
                              ├─ Orchestrator parses manager output
                              │
                              └─ Spawns child tasks via RuntimeAdapter
                                  └─ Child results fed back to manager
```

### 6.3 Session Discovery (Monitoring External Runs)

For the requirement to monitor Claude Code sessions not started by this platform:
- **REQUIRES INVESTIGATION**: Whether Claude Code stores session metadata in a discoverable location
- **REQUIRES INVESTIGATION**: Whether FCC proxy exposes active session information
- This is a separate capability from orchestration and should not block the core platform

---

## 7. Evidence References

| Finding | Source |
|---------|--------|
| Subprocess launch | [`runtime_adapter.py` L339-348](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/runtime_adapter.py#L339-L348) |
| Mock fallback | [`runtime_adapter.py` L409-434](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/runtime_adapter.py#L409-L434) |
| Model flag injection | [`runtime_adapter.py` L130-131](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/runtime_adapter.py#L130-L131) |
| Env vars for FCC | [`runtime_adapter.py` L91-106](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/runtime_adapter.py#L91-L106) |
| Cancellation | [`runtime_adapter.py` L484-520](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/runtime_adapter.py#L484-L520) |
| SSE endpoint | [`tasks.py` L263-391](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/backend/api/tasks.py#L263-L391) |
| No parent_id | [`persistence.py` L46-64](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/persistence.py#L46-L64) |
| Dual storage | [`agents.py` L123-124](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/backend/api/agents.py#L123-L124) |
| allowed_tools ignored | [`config.py` L57](file:///c:/Users/taguo/Desktop/ai-agents-platform/poc/config.py#L57) vs no usage in runtime_adapter.py |
