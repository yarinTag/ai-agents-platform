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
* **Maker-Checker Reviews & Evaluations**: Intercepts critical milestones requiring human or managerial sign-off before downstream stages proceed. Captures `RunEvaluation` ratings and feedback.
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
