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


## Integration of current master capabilities

## Optional Playground runtime capability
`RuntimeCapabilities.supports_playground` defaults to false. `PlaygroundRuntimeAdapter` extends the base protocol with `start_playground_task(agent_id, task_id, prompt, workspace)`; existing adapters retain the base contract. ClaudeCodeAdapter advertises support and delegates to ClaudeCodeRuntimeAdapter. The command uses fresh print-mode inference, `--safe-mode`, an empty `--tools` inventory, `--strict-mcp-config` with empty servers, disabled hooks/skills discovery/Chrome, empty setting sources, `dontAsk`, and no session persistence. Agent system prompts and explicit skill text are retained; inherited hierarchy delegation instructions are omitted. The subprocess cwd is the ephemeral workspace. Permission bypass settings cannot override this command. Playground tasks cannot use ordinary start/resume paths. Model errors and missing-input requests fail locally without supervisor routing. Playground does not modify normal agent conversations or invoke orchestration completion callbacks. This requires a CLI supporting these flags; unsupported CLIs fail rather than retrying with broader permissions. These controls disable agent tools; they do not claim OS-level network isolation of the model provider client.

### Runtime diagnostics and buffered output
The stdout reader accepts text or byte streams for buffered output remaining after process exit, without calling decode on text. A dedicated daemon drains stderr into a bounded tail (30 lines, up to 2000 characters each), avoiding stderr pipe deadlocks; terminal task records include a stderr event and diagnostic failure text. The event consumer waits for reader completion/queued events before treating process exit as missing output. Playground task records checkpoint events at one-second intervals for live logs. Real subprocess regression tests exercise buffered text and large stderr streams without model calls.

Cancellation errors use neutral wording (Task cancelled) because cancellation can be initiated by timeout handling as well as an operator. Playground timeout errors name the timeout duration and direct the user to runtime events and the provider connection.

## Workflow Assistant model-only generation
AuthoringModelSelection (frozen model_id/provider_id) is separate from execution agents. Optional AuthoringRuntimeAdapter exposes get_authoring_models and infer_authoring(selection,prompt,system_prompt,response_schema,timeout_seconds,max_budget_usd,is_cancelled,authoring_context). Base RuntimeAdapter compatibility is unchanged. The configured provider and curated catalog/aliases determine available routing choices; runtime checks the pair before spawning. Unsupported upstream deployments fail visibly, with no model fallback. An ephemeral internal AgentConfig only adapts the existing CLI builder; it is never loaded from/saved to agent persistence.

Without authoring_context the inference remains tool-free. With a trusted parent-created context it creates a private mode-0600 context file and a strict MCP configuration for backend.workflow_assistant.mcp_server, launched by the current Python interpreter. safe-mode is removed because it suppresses MCP customizations; restricted mode, empty built-in tools, empty setting sources, disabled hooks/skills/Chrome and exact allowedTools limit access to workflow_catalog/workflow_schema/validate_workflow_yaml. Only that internal server is configured. The model never receives file/shell tools or external connector tools. Provider networking remains necessary; this is not OS-level network isolation.

AuthoringInferenceResult contains output,tokens,nullable cost_usd,cost_source,model,error_code/error_message. A new POSIX process group covers CLI and MCP descendants; termination/kill and temporary-directory cleanup occur on result, error, timeout or cancellation. No AgentRun, Office event, agent conversation or normal completion callback is created. The MCP server verifies current user rights/job RUNNING/deadline per call. The parent independently checks required tool calls and the selected validation_id and stored candidate hash against the current generation. Actual SDK stdio tests and live-provider smoke calls are separate checks.

### Integrated component ownership and verification limits

Model-only inference is implemented in `authoring.py`, exposed through facade methods `get_authoring_models`, `infer_authoring(selection, prompt, system_prompt, response_schema, timeout_seconds=120, max_budget_usd=None, is_cancelled=None, authoring_context=None)` and `_read_authoring_process`. It uses the existing injected command/model services and shared process maps/authoring lock, never ordinary AgentRun dispatch. Runtime shutdown also cancels authoring admission/reads and terminates tracked authoring process groups.

`playground.py` owns `start_playground_task(agent_id, task_id, prompt, workspace)`. Its threads are tracked by the existing runtime shutdown owner and serialized with existing per-run locks. `TaskExecutor` accepts `playground_workspace` and suppresses supervisor routing/session capture; finalization persists playground run state without normal conversation, chat notification or completion callbacks. The command builder has an explicit playground flag before normal permissions/customization injection. The bounded stderr reader now retains the upstream diagnostic tail; this supersedes the earlier note that diagnostics were drained without retained content. Buffered-output, process lifetime, subscription fan-out and source path fixes from the refactor are retained.

The upstream regression tests mentioned above were merged as source only. No tests, import execution, build, lint, startup or model inference were performed during conflict resolution; live behavior remains unverified.

## Direct HTTP providers (2026-10-31)
`runtime_providers` additionally registers `direct_anthropic`, `direct_openai`, `direct_nvidia`. They require server `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `NVIDIA_API_KEY` respectively, plus finite non-negative `<PROVIDER_ID_UPPERCASE>_INPUT_USD_PER_MILLION` and `_OUTPUT_USD_PER_MILLION`. Detection checks configuration, not live model access. Keys are not saved to settings or returned to the browser. Provider URLs are fixed HTTPS vendor endpoints. Existing `anthropic_api` remains the legacy CLI-with-API-key provider.
`direct_config` owns metadata/model validation/pricing; `direct_http` owns Messages and chat-completions wire formats; `direct_worker` owns a bounded 40-turn real tool-call loop; `direct_tools` owns local workspace tools; `direct_sessions` owns private persisted transcripts. Command construction selects `sys.executable -m runtime.direct_worker` for direct IDs. Default/CLI aliases/logical tiers use the saved `runtime_model_<provider_id>`; explicit model IDs are preserved (NVIDIA strips only the legacy `nvidia_nim/` prefix). No model deployment or tool-call support is fabricated.
Local inventory: Read/Write/Edit/Glob/Grep/Bash/AskUserQuestion filtered by the existing mapped allowedTools. File operations reject workspace traversal and symlink escape; Bash uses the assigned working directory but is not an OS filesystem/network sandbox. Shell execution without the existing skip-permission flag pauses for supervisor input. HTTP client keys are removed from the shell environment. No inherited CLI MCP servers/hooks/extensions are loaded. Unknown requested tools fail; tool errors return real errors. Playground has no tools or persisted session.
Worker events reuse the shared JSON session/tool/result contract, lifecycle persistence, cancellation and subscriber delivery. POSIX workers and descendants use a process group. Requests have bounded connection/read timeouts and no paid automatic retries; token deltas are not streamed, but tool/result events are emitted per response. API sessions use `api_<uuid>` IDs, private 0600 transcript files beneath database-adjacent runtime_sessions/hashed-tenant-agent-scope, bind provider/model/scope, and reject cross-method/model resumption. Fork copies context into a new ID. Start a new session after changing execution method.
Costs are calculated from configured token prices and returned usage, not an upstream invoice; ensure rates match each assigned model. Missing/invalid rates prevent direct inference. Result clarification is interpreted after token/cost extraction. No runtime verification was performed.

## Direct HTTP API providers & provider-scoped models (2026-10-31)
`DIRECT_PROVIDERS` in `poc/runtime/direct_config.py` defines `direct_nvidia` (`NVIDIA NIM`), `direct_anthropic` (`Anthropic`), `direct_openai` (`OpenAI`), and `direct_openrouter` (`OpenRouter`), along with `PROVIDER_MODELS` (including verified NVIDIA NIM endpoints `nvidia/nemotron-3.5-super-vl-120b-a12b`, `nvidia/nemotron-3-ultra-550b-a55b`, `nvidia/nemotron-3.5-lightning-30b-a3b`, `nvidia/nemotron-3.5-bolt-e4b`, `mistralai/mistral-large-4-1t-a52b`, and `poolside/laguna-xs-2.1`) and `DEFAULT_PROVIDER_MODEL`. `resolve_api_key(provider, db)` resolves API keys from server environment variables (`NVIDIA_API_KEY` / `NVIDIA_NIM_API_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `OPENROUTER_API_KEY`), platform settings (`runtime_api_key_<provider>`), or `~/.fcc/.env`. Outside unit tests, `rates(provider)` defaults to `[0.0, 0.0]` when token-price environment variables are omitted, and `resolve_provider_selection` maps legacy CLI provider selections to Direct HTTP API providers so runs execute via `runtime.direct_worker` rather than spawning the `claude` CLI binary. `resolve_model_for_provider` maps aliases (`default`, `sonnet`, `opus`, `haiku`, `fable`), logical tiers (`tier:*`), retired NVIDIA model IDs, and cross-provider model IDs to the active provider's configured model. `direct_http.py` falls back to `reasoning_content` when `content` is empty.

## New tool-free workflow chat inference
`workflow_chat.selection` captures the configured runtime provider/model/cost_source using existing direct-provider model resolution; `workflow_chat.infer` launches the existing command builder in tool-free playground mode, replaces the exercise prompt with a strict chat/schema/catalog prompt, disables inherited tools/MCP/hooks/session persistence and uses a temporary directory. This is independent of the removed authoring module. Runtime facade exposes workflow_chat_selection/infer_workflow_chat and the optional WorkflowChatRuntimeAdapter protocol documents the contract. No agent/config/task/session is persisted for planning.
Model processes are tracked in the runtime process map, use the existing max concurrency, check shutdown/cancellation/current permissions while waiting, and terminate their POSIX process group. Timeout=120s, response size bound=2 MB on completed output. Direct/normal CLI supports --json-schema; compatible gateways get the schema in the system prompt. API calls receive the remaining department budget; actual reported/configured costs and token usage return to the job record. Direct safe error messages are retained; CLI errors expose a generic login/model/quota message, not raw stderr or provider bodies. Static review only; no live model/CLI calls were performed.

Workflow chat prompt separation: authoring restrictions apply only to the conversation. Model guidance explicitly requires future execution instructions in prompt_template and forbids copying inactive-preview/no-tools/do-not-claim-execution disclaimers into runnable steps.

## Connector-only production workflow mode
connector_context.attach_connectors is called by TaskExecutor after command/environment construction. For wf_task_ records with a trusted workflow_tool_scopes row it requires Direct API, verifies current policy, supplies backend DB path/task ID only through child environment and appends --connector-only/empty --tools. DirectTools then constructs WorkflowToolExecutor in the backend worker and advertises only its narrowed schemas; no connector token/config is in model context. Ordinary unrelated tasks remain unchanged. Review tasks whose parent has a governed scope have an empty tool inventory. Connector workflow transcripts additionally bind the task ID in PLATFORM_API_SESSION_SCOPE, preventing cross-task continuation through a shared organization-level agent. Inherited connector context is cleared from all general environments, including chat/Playground. No CLI fallback for governed tools is enabled.
Direct worker checks authority before each model request; each tool operation checks it again server-side. Tool results are emitted as real events, and a required receipt check runs both in the worker and parent before COMPLETED. Connector errors fail the step rather than allowing a prose-only completion. External-data text/tool-result events cannot become supervisor/permission commands through heuristic parsing. Cancellation is persisted and a late result cannot overwrite CANCELLED. The captured connector scope expires at the step timeout capped at300s; expired scopes require a fresh workflow execution rather than inheriting broader authority. This bounds new operations, but does not undo already-dispatched provider calls. Runtime/process/HTTP checks were reviewed statically only.
