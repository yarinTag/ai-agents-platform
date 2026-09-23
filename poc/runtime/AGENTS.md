# AGENTS.md - Runtime & Execution Service

## 1. Service Identity & Mission
The **Runtime & Execution Service** (`poc/runtime/` & `poc/runtime_adapter.py`) manages the physical lifecycle of autonomous agent execution. It bridges abstract prompts into sandboxed Claude Code CLI subprocesses, reads streaming JSON events, intercepts clarification questions, and handles seamless context resumption.

---

## 2. Core Capabilities & Specializations
* **Process Sandboxing & Environment Management**:
  * Configures Claude Code environment variables (`ANTHROPIC_BASE_URL`, `ANTHROPIC_AUTH_TOKEN`, `TERM=dumb`).
  * Enforces directory boundary restrictions via `--add-dir` pointing to the project's designated workspace.
* **Stream-JSON Event Pipeline**:
  * Spawns dedicated daemon reader threads per process to consume stdout in real-time.
  * Emits typed events (`thought`, `tool_use`, `result`, `error`) to in-memory queues and persistent event streams.
* **Question Interception & Session Continuity**:
  * Tracks `session_id` from the Claude Code subprocess stream.
  * Intercepts `ask_supervisor` tool calls or unresolved questions in the model's output.
  * Rather than closing the task with exit code 0 as a false `COMPLETED`, it suspends execution into `WAITING_INPUT`.
* **Stateful Resumption (`resume_task`)**:
  * Re-activates suspended tasks using `claude --resume <session_id> -p "Supervisor response: ..."` so agents preserve full conversational memory and file edit history.

---

## 3. Interfaces & Contracts

### Key Methods
```python
adapter = ClaudeCodeRuntimeAdapter()

# 1. Start fresh task
run_id = adapter.start_task(
    agent_id="qa-specialist",
    project_id="shop-app",
    prompt="Run test suite and report failures"
)

# 2. Resume paused task after supervisor or human provides answer
resumed_id = adapter.resume_task(
    run_id=run_id,
    answer="Use the test database at localhost:5433"
)

# 3. Query status
run = adapter.get_run_status(run_id)
# run.status in (QUEUED, RUNNING, WAITING_INPUT, PENDING_APPROVAL, COMPLETED, FAILED)
```

---

## 4. Invariant Rules & Guardrails
1. **Never Fake Completion**: If a model asks a question or encounters an ambiguous requirement, the runtime MUST NOT mark the task as `COMPLETED`.
2. **Deterministic Cleanup**: Subprocesses must be terminated cleanly on stop events or process failure (`terminate` followed by `kill` after 5s timeout).
3. **Session Preservation**: Every execution must record its `session_id` into `task_runs` to guarantee zero-loss restart capability.
4. **Non-Blocking Execution**: `start_task` and `resume_task` must return immediately with a `run_id` and execute actual inference inside background threads.
