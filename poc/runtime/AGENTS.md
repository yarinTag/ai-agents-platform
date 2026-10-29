# AGENTS.md - Runtime & Execution Service

## 1. Service Identity & Mission
The **Runtime & Execution Service** (`poc/runtime/`, `poc/runtime_adapter.py`, and `poc/runtime_providers.py`) manages the lifecycle of autonomous agent execution behind a clean, provider-agnostic abstraction. It decouples high-level orchestration from concrete LLM execution runtimes, resolves logical model capability tiers, bridges prompts into sandboxed subprocesses, parses streaming JSON events, intercepts clarification questions, and manages stateful session resumption.

---

## 2. Core Capabilities & Architecture

* **Provider-Agnostic Runtime Abstraction (`protocol.py` & `registry.py`)**:
  * Formal `@runtime_checkable` `RuntimeAdapter` protocol standardizing task execution lifecycle (`start_task`, `get_run_status`, `resume_task`, `cancel_run`, `list_runs`).
  * `RuntimeRegistry` manages registered engines (`claude_code` default), allowing alternative future runtimes (e.g. OpenAI, local LLM engines) without modifying orchestration or hierarchy logic.
* **Curated Enterprise Model Catalog (`poc/runtime/models.py`)**:
  * Exposes `MODEL_CATALOG` covering top-tier models across multiple providers:
    * **Anthropic**: Claude 4.5 Sonnet, Claude 4 Sonnet, Claude 4 Haiku.
    * **OpenAI**: GPT-4o, o3-mini.
    * **Google Gemini**: Gemini 2.5 Pro, Gemini 2.5 Flash.
    * **Local Ollama**: Llama 3.3 70B (Local), DeepSeek R1 (Local).
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

### Composed subprocess runtime

`poc/runtime_adapter.py` retains the compatibility exports `ClaudeCodeRuntimeAdapter`, `runtime_adapter`, `AgentRun`, `TaskStatus`, provider setting keys, `extract_supervisor_question`, `summarize_runtime_event` and `build_task_progress_payload`. The stateful adapter owns active run/process/queue/thread maps and retains start/resume/cancel/status/subscription entry points. It composes focused collaborators rather than inheriting implementation fragments:

| Module | Responsibility |
|---|---|
| command_builder.py | Runtime provider precedence, gateway settings, sanitized environment, workspace selection and CLI/system-prompt construction |
| questions.py | Structured permission/tool/text clarification recognition; direct and nested tool events share one input/question/options interpreter |
| progress.py | Runtime event summaries and task progress payloads |
| output_stream.py | Stream-JSON parsing, raw-output events, reader queue metadata and end-of-output signaling |
| execution.py | Subprocess launch, result/token/cost handling, session capture and one shared supervisor/waiting-state handler |
| finalization.py | Final timestamps, run/chat persistence, completion notification and resource-map cleanup |
| processes.py | Shared terminate/wait/kill policy used by execution cleanup and cancellation |
| subscriptions.py | Per-subscriber bounded queues, callback threads, real unsubscribe and run-close signaling; subscriber queues never consume executor input |
| services.py | RuntimePersistence/RuntimeConfiguration protocols and RuntimeServices integration ports |
| legacy_services.py | Lazy compatibility adapters for persistence/config/model policy/skills, supervisor resolution and optional backend event/completion integration |

`ClaudeCodeRuntimeAdapter(services: Optional[RuntimeServices] = None)` accepts explicit integration ports. `configure_services(services)` replaces them before runs start and updates command construction wiring. Application startup may use `dataclasses.replace(adapter.services, ...)` to retain default model/skills/session adapters while replacing event, supervisor and persistence integration.

Required RuntimeServices providers are `database()`, `configuration()`, `resolve_model(model)`, `skills_prompt(skills)` and `capture_session(run, session_id)`. Optional callbacks are `emit(**EventService.emit_kwargs)`, `publish_chat(run, persisted_message)`, `supervisor(**resolve_or_escalate_question_kwargs)` and `complete(run)`. The legacy `on_task_completed` callback takes precedence over `complete`. Missing event/chat/completion callbacks skip only their delivery; missing or failing supervisor resolution leaves the run in WAITING_INPUT addressed to HUMAN_OPERATOR, retaining its question/session for resumption. An AUTO_RESOLVED question preserves RUNNING; other resolver results preserve WAITING_INPUT and the explanatory result. No unavailable dependency creates a fabricated COMPLETED result.

Default services are lazy: importing or constructing the runtime facade does not import backend dependencies, initialize persistence or create a supervisor resolver. Concrete optional backend coupling is confined to legacy_services; explicitly composed runtime execution/command/reader modules do not import backend services. Legacy defaults retain the historical dynamic integration for standalone callers until the composition root supplies replacements.

The command builder continues to put the PoC root (the parent of `runtime/`) in subprocess PYTHONPATH, and its Windows fallback still resolves `poc/lms`, preserving path semantics after relocation. Output draining accepts either text lines from Popen(text=True) or bytes, avoiding an unconditional bytes decode on remaining text output. Event callbacks receive a fan-out after the executor appends each event to the canonical run. They no longer race the executor for its result/session events. Each subscriber has a 1000-event queue; overflow stops that optional subscriber and logs a warning rather than blocking execution. Unsubscribe removes its listener and stops its thread; finalization/cancellation close run listeners. The callback API does not replay historical events. Existing terminal states, session fields, CLI permission flags, provider precedence and persistence ordering are retained. Source extraction does not establish runtime resilience or behavioral verification; no tests, build, lint, import execution, type checking or application startup were run under the user's restriction.

### Key Usage Pattern
```python
from backend.dependencies import get_runtime_adapter, get_model_policy_resolver
from runtime.model_policy import ModelTier
from runtime.models import MODEL_CATALOG

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

---

## 🔄 Mandatory `AGENTS.md` Synchronization Rule

> [!IMPORTANT]
> Whenever any runtime adapter logic, model catalog entry, capability tier mapping, or subprocess lifecycle code in `poc/runtime/` is modified, the developer or agent **MUST** update this `AGENTS.md` file within the **SAME commit**.

## Final parent review corrections
Provider selection precedence is owned by runtime_providers.resolve_provider_selection and reused by setup reporting and command building; setup reporting does not import the concrete execution singleton. Runtime shutdown stops admission, cancels known runs, closes subscribers and joins tracked execution threads with bounded waits. Same-run execution attempts serialize across prior finalization so automatic session resumption cannot race old process-map cleanup. stderr is drained without retaining unbounded/secret content; termination waits are bounded. Subscriber queues remain independent of execution input; terminal subscriptions close and already-terminal runs do not create idle listeners. Explicit result is_error produces FAILED. Reader completion owns the output-end marker, avoiding premature failure before final output drains.

Unavailable supervisor callbacks leave WAITING_INPUT rather than failing or completing a clarification. Composed backend fallback stores a HUMAN_OPERATOR interaction. These corrections were reviewed in source only, not exercised.

Required declared agent skills no longer silently disappear on enrichment failure: missing/unresolved context raises an explicit runtime failure before subprocess launch. Optional backend wiring supplies the skill-context callback. This change is source-reviewed only.
