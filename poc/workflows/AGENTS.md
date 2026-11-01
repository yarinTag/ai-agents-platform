# AGENTS.md - Workflows Engine & Playbooks Service

## 1. Service Identity & Mission
The **Workflows Engine & Playbooks Service** (`poc/workflows/` and `poc/backend/api/workflows.py`) is the autonomous workflow automation engine of the AI Agents Platform. It compiles declarative multi-agent playbooks into directed acyclic graph (DAG) executions, enforces department budget caps (`HARD_STOP`), manages ephemeral sandboxes, coordinates parallel stages, and delivers real-time notifications to communication channels.

---

## 2. Core Components & Architecture

### 1. Workflow Engine (`engine.py`)
* **Topological DAG Execution**: Resolves step dependencies (`depends_on`) to construct a valid execution schedule. Steps with satisfied prerequisites execute immediately; steps waiting on upstream outputs remain queued.
* **Parallel Multi-Agent Stages**: Leverages `concurrent.futures` to dispatch independent workflow steps concurrently across multiple specialist agents.
* **Department Budget Enforcement (`HARD_STOP`)**:
  * Evaluates current department spend against `monthly_budget_usd`.
  * If the budget is exhausted, halts execution immediately and raises `BudgetExceededError`, preventing cost overruns.
* **Department MCP Governance Checks**:
  * Verifies that any MCP tools required by workflow steps are permitted under `department_mcp_access`.
  * Blocks unauthorized tool calls with `MCPGovernanceViolationError`.
* **Conditional Trigger Rules**: Evaluates step condition expressions against parent step outputs to conditionally skip or execute downstream branches.
* **Idempotency & Deduplication Engine (`compute_execution_hash`)**: Generates deterministic SHA-256 payload hashes (`workflow_id + payload`). Detects matching active (`QUEUED`, `RUNNING`) or recently `COMPLETED` runs, returning cached deduplicated results to eliminate duplicate compute and prevent token waste.
* **Asynchronous Queue Dispatch**: Integrates with RabbitMQ (`platform.workflows.execution`) for decoupled execution of heavy playbooks with fast HTTP `202 Accepted` response times.
* **Maker-Checker Reviews & Evaluations**: Intercepts critical milestones requiring human or managerial sign-off before downstream stages proceed. Captures `RunEvaluation` ratings and feedback.
* **Active HITL ChatOps Gating**: When a step enters `WAITING_INPUT` or `PENDING_APPROVAL`, automatically formats and dispatches interactive approval messages (Telegram Inline Keyboards and Slack Block Kit buttons) to bound channels, extending step timeouts until human resolution.
* **Channel Notifications**: Formats and dispatches execution lifecycle events (started, step completed, failed, finished) to bound Slack and Telegram channels via integrated MCP connectors.

### 2. Workflow Parser (`parser.py`)
* **Declarative Schema Definitions**:
  * `WorkflowDefinition`: Represents the complete playbook containing metadata, triggers, department scope, and steps.
  * `WorkflowStepDefinition`: Represents an individual step, specifying `step_key`, `name`, `agent_id`, `prompt`, `depends_on`, `condition`, `timeout_seconds`, and required `skills`.
* **Bidirectional Format Translation**: Seamlessly parses and converts between YAML and JSON representations without data loss.
* **Dependency Validation**: Validates step graph integrity, preventing circular references or undefined step dependencies.

### 3. Sandbox Manager (`sandbox.py`)
* **Isolated Execution Environments**: Manages execution boundaries for workflow tasks through `SandboxManager` and `SandboxSession`.
* **Modes of Isolation**:
  * **Ephemeral Workspace Directories**: Creates isolated temporary directories with automatic cleanup on workflow termination.
  * **Docker Containers**: Provisions sandboxed container environments for executing untrusted code or isolated build pipelines.
* **Environment Injection**: Securely injects scoped environment variables, API credentials, and project paths into sandbox sessions.

---

## 3. Interfaces & Execution Flow

```python
from poc.workflows import WorkflowParser, WorkflowEngine, SandboxManager

# 1. Parse playbook
parser = WorkflowParser()
workflow_def = parser.parse_yaml(playbook_yaml_str)

# 2. Initialize execution engine
engine = WorkflowEngine(
    db_manager=db_manager,
    runtime_adapter=runtime_adapter,
    sandbox_manager=SandboxManager()
)

# 3. Execute workflow DAG
execution = await engine.execute_workflow(
    workflow_id=workflow_def.id,
    inputs={"target_branch": "feature/payments"},
    department_id="dept_engineering"
)
# Returns WorkflowExecution record with step outputs, tokens, and cost breakdown
```

---

## 4. Invariant Rules & Guardrails

1. **Hard Budget Stops**: If a department's monthly spend meets or exceeds `monthly_budget_usd` under `HARD_STOP`, no new workflow executions or subtasks may proceed.
2. **Dedicated Runner Agents**: Every registered workflow must have an associated dedicated runner agent (`wf-agent-{id}`) configured with the workflow's default skills and scope.
3. **No Unchecked MCP Invocations**: Steps executing external MCP actions must pass department-level whitelisting checks.
4. **Deterministic Sandbox Cleanup**: All temporary filesystem sandboxes and ephemeral containers must be cleanly disposed of regardless of execution success or failure.

---

## 🔄 Mandatory `AGENTS.md` Synchronization Rule

> [!IMPORTANT]
> Whenever any logic in `poc/workflows/` (`engine.py`, `parser.py`, `sandbox.py`) or its corresponding API router (`poc/backend/api/workflows.py`) is modified, the developer or agent **MUST** update this `AGENTS.md` file in the **SAME commit**.

## Execution component ownership
engine.py remains WorkflowEngine lifecycle/coordinator and public compatibility exports. execution_models.py owns execution results and policy errors; conditions.py owns pure trigger evaluation; stages.py owns DAG-stage planning; step_runner.py owns step prompt rendering, governance checks, runtime invocation and result capture. WorkflowEngine delegates step execution through a composed WorkflowStepRunner, preserving existing method entry points. No schema or endpoint changes are introduced by this extraction. Source files stay at most 500 physical lines; runtime compatibility is unverified because tests/build/startup are not authorized.

## Truthful states and optional notifications
WorkflowStepRunner now records actual COMPLETED/FAILED/CANCELLED or pause states; runtime absence/start failure/timeout cannot become COMPLETED. Pause states stop later dependent stages and leave workflow/step completed_at unset. This is not a new automatic whole-workflow resume mechanism; existing task sessions remain resumable. Step SQL is owned by WorkflowsRepository.save_workflow_step_run. Runtime changes assigned to the public engine are passed to its composed step runner. Missing budget authorization defaults to denial. The unused full orchestration dependency is no longer constructed by backend workflow wiring.

WorkflowNotifier is injected by the composition root and receives connector lookup/delivery callbacks. Notifications use shared integrations/channels and audit call_notify_{execution_id} as STARTED then COMPLETED/FAILED. Existing calls are not automatically resent. Missing notification implementation/connector or delivery failure does not change execution outcome, and does not claim successful delivery. No schema/outbox/exactly-once guarantee is introduced. Public engine error/result imports remain compatible; parser imports no longer eagerly load the execution engine.

WorkflowStore/WorkflowNotifications define the narrow injected contracts. Stage planning rejects duplicate keys, unknown dependencies and cycles rather than silently running an invalid graph sequentially. This correction is source-reviewed only.

Step skill context is injected by the composition root; the step runner no longer imports skills_service. An executing step with configured skills and no context provider fails explicitly. A missing runtime still records its own failure without loading optional skill context.
## Tool-free playground execution
`execute_workflow(..., playground=True)` requires a runtime advertising `supports_playground`; unsupported runtimes fail before sandbox/run creation. It forces `trigger_type=PLAYGROUND`, namespaces hashes with `playground:{workflow_id}`, creates an empty ephemeral directory without copying the source workspace, and uses the existing DAG and budgets. Each step calls `start_playground_task(..., workspace=...)`; task IDs begin `pg_task_`. Existing configured agents are required; no fallback agent is substituted. Failures and timeouts produce FAILED step/run records, not fabricated success. Runtime launch errors are persisted as failed step output. Sandbox paths are populated on queued records and cleanup follows execution. Playground suppresses channel completion notifications, external HITL escalation and automatic maker-checker launches. Missing input requires a fresh run; dashboard approval/resume and durable recovery are outside this initial mode. Agent/step skills remain prompt context; live tools do not run. Production execution behavior remains the default.

### Playground MCP declarations
Workflow-level and step-level `mcp_servers` remain declarative metadata in tool-free playground runs and do not require department connector grants, because no connector or tool is invoked. Both governance prechecks remain mandatory for ordinary executions. Tenant/department authorization, runtime capability enforcement, budget checks, prompt scanning, and empty runtime tool/MCP inventories still apply. Regression tests cover both declaration scopes without live model calls.

### Step log lifecycle
Each step inserts a workflow_step_runs row in RUNNING status, with task_run_id, formatted input and started_at, before launching its runtime task. Completion updates that same row with final status/output/token counts/cost/completed_at. Active steps therefore appear in execution inspection while inference is running instead of only after completion. Scoped execution detail joins persisted runtime events/errors for the log viewer.

Direct engine playground launches also generate pg_exec_ IDs. Model timeouts include the configured wait duration and point to runtime/provider diagnostics.

## Execution origin for shared agents
Live workflow step IDs now use wf_task_ (playground keeps pg_task_). Existing legacy IDs are classified through workflow_step_runs, so prefixes are not the source of truth. Step tasks always inherit their configured agent organization. Maker-checker task records are created before dispatch with parent_task_id/root_task_id referencing the originating step; reviewers and delegated descendants remain workflow activity. Shared agent definitions are not reclassified as workflow agents. Persistence resolves workflow_execution_id/workflow_id through direct step records and parent/root lineage; UI office scoping hides these executions while keeping global Tasks and workflow logs available.

## Revision-aware workflow authoring
Existing workflows retain their database ID, webhook token and dedicated runner identity during editing. Version 1 is saved at creation; effective configuration updates append full snapshots with changed fields/actor/summary under an atomic transaction. API validation rejects duplicate step identifiers, missing dependencies and cycles before saving. Explicit step keys in WorkflowParser are preserved verbatim rather than slugified, keeping depends_on and prompt output references stable; generated fallback keys still use the existing name-based slug. compute_execution_hash accepts optional revision; API and engine paths pass the current saved revision so definition edits do not reuse old results. Playground/office origin behavior is unchanged. Revision history is configuration history; it does not retroactively assign immutable definition snapshots to previously queued or completed runs.

## Merge into modular execution
engine.compute_execution_hash includes saved revision; playground has a distinct namespace. Prequeued execution IDs/status/hash/sandbox_path are reused. step_runner accepts playground_workspace, saves RUNNING origin before runtime dispatch, upserts the same step ID with observed state/error/usage, and fails missing runtime/timeouts. Prompt/output checks and optional approval delivery arrive as injected callbacks from backend/workflow_wiring. Live human approval waits at most1800 seconds; playground additional-input requests cancel/fail and never launch reviewer/notification callbacks. Reviewers inherit parent/root lineage. DAG validation remains strict.

agent_scope checks configured step/reviewer ownership before dispatch: exact workflow organization; non-admin authenticated users must have the agent department, unattended triggers require the workflow department. Auto-provision uses the workflow tenant/department, never the first global agent. Failed checks settle execution FAILED.

## Workflow Assistant authoring schema removal (2026-10-31)
`poc/workflows/authoring_schema.py` and `poc/workflows/workflow-authoring.schema.yaml` have been removed alongside `poc/backend/workflow_assistant/`. `validate_workflow_definition` in `poc/workflows/parser.py` remains the shared DAG validator for workflow creation and editing.

## Friendly chat-created workflows
Create with AI is a new model-only planning UI/API under the existing workflows capability. Strict candidates are translated into native step key/agent/prompt/depends_on/mcp_servers/params and metadata.channel_binding. Exact declared resources are validated from current department grants/configured allowlists and carried into step instructions plus params.authorized_resources. Channel delivery is ON_COMPLETE with trigger_enabled=false; webhook_enabled=false; optional cron is parsed with croniter. Unknown agents/connectors/resources/tools, invalid dependencies/cycles and invalid cron block creation. The shared creation path provisions a dedicated runner and saves the workflow initially inactive. No workflow is executed or activated by the chat.

Playground diagnosis: pg_exec_ runs intentionally have no live connector access. A configured repository reference is data, not an attached runtime tool. Chat authoring validation now rejects known preview-only disclaimers inside future execution prompts; existing workflow definitions are not automatically migrated.

Manual production executions can be dispatched locally through /execute?use_queue=false&background=true using the same engine and a precreated QUEUED record. This is real execution, not Playground, and preserves tool/governance/budget checks. RabbitMQ queue dispatch remains a separate explicit option; local dispatch adds no MCP tool implementation.

## Real governed connector execution
Before the DAG starts, WorkflowEngine captures an immutable execution tool context (organization/department/initiator + channel binding) and preflights every step's supported provider/tools/resources/current permissions and notification destination. Invalid required step scopes fail the execution before model dispatch; optional delivery failures are recorded separately. WorkflowStepRunner saves the task, prepares its per-task scope from the captured definition, then starts the normal runtime. Connector workflows also scope tool-free analysis steps; reviews of their data cannot use shell/file tools. Playground skips all live scope preparation and notifications.
Supported operations currently read GitHub.com activity and send literal plain-text Telegram/Slack messages to exact approved IDs. The native authorized_resources array narrows each step; legacy connector-only definitions use their configured resource allowlists as the upper bound. Unsupported declared tools/providers, missing credentials/grants and display-name channel aliases fail explicitly. The exact known sentence “This is an inactive preview; do not claim execution.” is stripped only from production formatted step input for compatibility; saved workflow definitions/revisions and Playground prompts are unchanged.
WorkflowNotifier now uses the captured binding and governed notification_guard instead of choosing the first connector by provider. It rechecks current rights and requires delivery acknowledgement, preserves no-auto-retry audit semantics, and skips a destination already delivered by an explicit workflow step. The notifier constructor/call signatures remain compatible; injected legacy deliver/lookup functions are retained attributes but no longer provide governed delivery. Notification failure remains best-effort and is audited separately from step completion. No integration or model was executed for verification.

Completion notifications remain optional: invalid/denied destinations produce a stored notification_error warning and no send, while authorized GitHub/model steps continue. An explicit channel-send step remains a required operation and fails on missing access. Explicit authorized_resources narrows legacy per-step connector supersets, so a copied Telegram declaration alone cannot create a delivery tool. Scope preflight is authoritative for required steps; optional delivery warnings are separate from execution.error_message.

Completion notification failures retain safe connector diagnostics via notification_guard and notification_error. Main workflow COMPLETED remains distinct from delivery failure. No resend or runtime verification was performed for the diagnostic correction.

## Deterministic channel action steps
`channel_action.py` owns explicit `params.channel_action` with strict fields:
`action: send_channel_message`, `connector_id`, `channel_id`, `source_step`.
The source must be in depends_on. Only its nonempty output is delivered; output
up to60,000 characters is preserved and delivered as numbered bounded parts; larger reports fail explicitly without truncation.
No prompt parsing or model decision triggers sends. After saving RUNNING task/step
and prepare_scope, step_runner dispatches this action through WorkflowToolExecutor
instead of model inference. Exactly one scoped delivery tool and one destination
are required. All live tenant/initiator/agent/department/resource checks, atomic
no-retry call claims and provider acknowledgements remain mandatory. The task
becomes COMPLETED only after receipt verification and a still-RUNNING check.
Failure follows normal failed-step recording; Playground rejects delivery actions
without invoking tools. Native definition validation checks action structure and
source dependency. Existing tool-calling model steps retain their behavior unless
explicitly converted. No tests, application or provider calls were executed.

WorkflowStepRunner passes workflow.organization_id when resolving explicit step skills. Plugin workflow skill IDs are checked against that organization source and full content injected before the prompt guard/model launch. Analysis skills belong on model steps, not deterministic channel delivery steps.

## Shared workflow skills (supersedes per-step selection UI)
All AI steps inherit the deduplicated union of definition.skills and legacy
steps[*].skills, normalized by skill_inheritance.workflow_skill_ids. Supported
native entries are string IDs or attached-skill objects with id/location. Missing
IDs fail explicitly. WorkflowStepRunner resolves these through the organization
plugin source before model invocation; server channel_action steps skip skill
loading entirely. Legacy step assignments remain readable but are now shared.
New authoring writes only workflow-level skills. No execution/tests were run.

Long report delivery no longer truncates source output at3500 or completion-notification output at2500 characters. Channel actions preserve <=60000 characters and the shared adapter numbers/splits long reports. Oversize reports fail explicitly, partial acknowledgement fails the delivery, and historical runs are never resent.

## Repository workspaces (`repo_sandbox.py`)
Steps that run or change code declare `params.workspace` {connector_id, repository, ref?, mode: read|write, pr_title?} (strict; validated at save by validate_workflow_definition and before execution by prepare_execution_context). Workspace steps cannot declare mcp_servers or channel_action and cannot run in Playground. The step runner calls integrations.repo_workspace.open_workspace instead of prepare_scope. That call authorizes, clones on the host, and starts a container via repo_sandbox.start_container. In write mode, after a COMPLETED step it calls publish_workspace (new agent/... branch + draft PR) and appends the PR URL to the step result. Publish failure fails the step. close_workspace always runs in `finally`. repo_sandbox requires Docker on POSIX and a digest-pinned PLATFORM_SANDBOX_IMAGE, with no fallback. Containers use --network none, --cap-drop ALL, no-new-privileges, read-only root, tmpfs /tmp 512m, 256 pids, 2g memory, 2 CPUs, non-root user (uid 1000 with chown when the backend is root), sleep 3600, and mount only the worktree at /workspace/repo. The legacy per-execution SandboxManager above is unchanged and is not the isolation boundary for these steps. See docs/repo-workspaces.md. Static review only; Docker was not run.
