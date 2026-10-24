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

## Tool-free playground execution
`execute_workflow(..., playground=True)` requires a runtime advertising `supports_playground`; unsupported runtimes fail before sandbox/run creation. It forces `trigger_type=PLAYGROUND`, namespaces hashes with `playground:{workflow_id}`, creates an empty ephemeral directory without copying the source workspace, and uses the existing DAG and budgets. Each step calls `start_playground_task(..., workspace=...)`; task IDs begin `pg_task_`. Existing configured agents are required; no fallback agent is substituted. Failures and timeouts produce FAILED step/run records, not fabricated success. Runtime launch errors are persisted as failed step output. Sandbox paths are populated on queued records and cleanup follows execution. Playground suppresses channel completion notifications, external HITL escalation and automatic maker-checker launches. Missing input requires a fresh run; dashboard approval/resume and durable recovery are outside this initial mode. Agent/step skills remain prompt context; live tools do not run. Production execution behavior remains the default.

### Playground MCP declarations
Workflow-level and step-level `mcp_servers` remain declarative metadata in tool-free playground runs and do not require department connector grants, because no connector or tool is invoked. Both governance prechecks remain mandatory for ordinary executions. Tenant/department authorization, runtime capability enforcement, budget checks, prompt scanning, and empty runtime tool/MCP inventories still apply. Regression tests cover both declaration scopes without live model calls.

### Step log lifecycle
Each step inserts a workflow_step_runs row in RUNNING status, with task_run_id, formatted input and started_at, before launching its runtime task. Completion updates that same row with final status/output/token counts/cost/completed_at. Active steps therefore appear in execution inspection while inference is running instead of only after completion. Scoped execution detail joins persisted runtime events/errors for the log viewer.

Direct engine playground launches also generate pg_exec_ IDs. Model timeouts include the configured wait duration and point to runtime/provider diagnostics.

## Execution origin for shared agents
Live workflow step IDs now use wf_task_ (playground keeps pg_task_). Existing legacy IDs are classified through workflow_step_runs, so prefixes are not the source of truth. Step tasks always inherit their configured agent organization. Maker-checker task records are created before dispatch with parent_task_id/root_task_id referencing the originating step; reviewers and delegated descendants remain workflow activity. Shared agent definitions are not reclassified as workflow agents. Persistence resolves workflow_execution_id/workflow_id through direct step records and parent/root lineage; UI office scoping hides these executions while keeping global Tasks and workflow logs available.
