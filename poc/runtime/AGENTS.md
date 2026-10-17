# AGENTS.md - Runtime & Execution Service

## 1. Service Identity & Mission
The **Runtime & Execution Service** (`poc/runtime/`, `poc/runtime_adapter.py`, and `poc/runtime_providers.py`) manages the lifecycle of autonomous agent execution behind a clean, provider-agnostic abstraction. It decouples high-level orchestration from concrete LLM execution runtimes, resolves logical model capability tiers, bridges prompts into sandboxed subprocesses, parses streaming JSON events, intercepts clarification questions, and manages stateful session resumption.

---

## 2. Core Capabilities & Architecture

* **Provider-Agnostic Runtime Abstraction (`protocol.py` & `registry.py`)**:
  * Formal `@runtime_checkable` `RuntimeAdapter` protocol standardizing task execution lifecycle (`start_task`, `get_run_status`, `resume_task`, `cancel_run`, `list_runs`).
  * `RuntimeRegistry` manages registered engines (`claude_code` default), allowing alternative future runtimes (e.g. OpenAI, local LLM engines) without modifying orchestration or hierarchy logic.
* **Model Policy & Intelligence Tiers (`model_policy.py`)**:
  * Decouples agent definitions from vendor-specific model identifiers.
  * Exposes canonical `ModelTier` categories (`tier:architect`, `tier:worker`, `tier:developer`, `tier:executive`, `tier:fast`).
  * `ModelPolicyResolver` dynamically translates logical tiers to the appropriate provider model at execution time.
* **Process Sandboxing & Provider Routing (`runtime_providers.py` & `claude_adapter.py`)**:
  * Configures provider environments (`native`, `free_claude_code`, `anthropic_api`, `custom_gateway` such as LiteLLM).
  * Injects `ANTHROPIC_BASE_URL` and `ANTHROPIC_AUTH_TOKEN` transparently.
  * Enforces directory boundary restrictions via `--add-dir` pointing to the designated project workspace.
* **Stream-JSON Event Pipeline**:
  * Spawns dedicated daemon reader threads per process to consume stdout in real-time.
  * Emits typed events (`thought`, `tool_use`, `result`, `error`) to in-memory queues and persistent event streams.
* **Question Interception & Multi-Turn Resumption**:
  * Tracks `runtime_session_id` (and backward-compatible `claude_session_id`) across executions.
  * Intercepts `ask_supervisor` tool calls or unresolved questions in the model's output.
  * Rather than closing the task with exit code 0 as a false `COMPLETED`, it suspends execution into `WAITING_INPUT`.
  * Re-activates suspended tasks using `resume_task` with full conversational memory and file edit history.

---

## 3. Interfaces & Contracts

### Key Usage Pattern
```python
from backend.dependencies import get_runtime_adapter, get_model_policy_resolver
from runtime.model_policy import ModelTier

# 1. Obtain runtime adapter via DI bridge (returns RuntimeAdapter protocol)
adapter = get_runtime_adapter()

# 2. Resolve capability tier or pass directly
model_resolver = get_model_policy_resolver()
resolved_model = model_resolver.resolve(ModelTier.ARCHITECT, runtime_id="claude_code")

# 3. Start task (returns immediately with run_id)
run_id = adapter.start_task(
    agent_id="qa-specialist",
    project_id="shop-app",
    prompt="Run test suite and report failures"
)

# 4. Resume paused task after supervisor or human provides answer
resumed_id = adapter.resume_task(
    run_id=run_id,
    answer="Use the test database at localhost:5433"
)

# 5. Query status
run = adapter.get_run_status(run_id)
# run.status in (QUEUED, RUNNING, WAITING_INPUT, PENDING_APPROVAL, COMPLETED, FAILED)
```

---

## 4. Invariant Rules & Guardrails
1. **Provider-Agnostic Abstraction**: Orchestration and API layers must depend on `RuntimeAdapter` and `ModelPolicyResolver`, never directly coupling to subprocess flags or vendor-specific model strings.
2. **Never Fake Completion**: If a model asks a question or encounters an ambiguous requirement, the runtime MUST NOT mark the task as `COMPLETED`.
3. **Deterministic Cleanup**: Subprocesses must be terminated cleanly on stop events or process failure (`terminate` followed by `kill` after 5s timeout).
4. **Session Preservation**: Every execution must record its `runtime_session_id` to guarantee zero-loss restart capability.
5. **Non-Blocking Execution**: `start_task` and `resume_task` must return immediately with a `run_id` and execute actual inference inside background threads.
