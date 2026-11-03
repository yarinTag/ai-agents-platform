# CLAUDE.md - AI Agents Platform Root Repository Guide

Welcome to the **AI Agents Platform** monorepo. This platform is an enterprise-grade autonomous agent management, workflow execution, and multi-tenant governance system featuring an interactive pixel office canvas, real-time collaboration war rooms, scheduled cron runners, DAG workflow orchestration, MCP integration hubs, and hierarchical supervisor delegation.

---

## 🏛️ Complete System Architecture

```
                                  [ Enterprise Tenant / Organization ]
                                                  │
                 ┌────────────────────────────────┴────────────────────────────────┐
                 ▼                                                                 ▼
      [ Department A (Budget Cap) ]                                     [ Department B (Budget Cap) ]
                 │                                                                 │
      ┌──────────┴──────────┐                                           ┌──────────┴──────────┐
      ▼                     ▼                                           ▼                     ▼
[ Members / Roles ]   [ Autonomous Agents ]                       [ Members / Roles ]   [ Autonomous Agents ]
(ORG_ADMIN, MANAGER,   (Hierarchy Trees,                           (ORG_ADMIN, MANAGER,   (Hierarchy Trees,
 OPERATOR, MEMBER)      Dedicated wf-agents)                        OPERATOR, MEMBER)      Dedicated wf-agents)
      │                     │                                           │                     │
      └──────────┬──────────┘                                           └──────────┬──────────┘
                 │                                                                 │
                 ▼                                                                 ▼
      [ Department MCP Access ] ─── (Allowed Tools Filtering) ─── [ Catalog & Custom MCP Servers ]
```

### 1. Multi-Tenant Enterprise Organization Hierarchy
* **Organization (`organizations`)**: High-level multi-tenant boundary with dedicated domain routing, global settings, and isolated SQLite/enterprise tenancy.
* **Departments (`departments`)**: Sub-divisions within organizations with dedicated monthly spending budgets (`monthly_budget_usd`), automated cost alerting thresholds (`alert_threshold_pct`), and hard-stop enforcement policies (`HARD_STOP`).
* **Members & RBAC (`users`, `department_members`)**: Enterprise roles:
  * `ORG_ADMIN`: Organization-wide oversight, department CRUD, global MCP grants, and member administration.
  * `MANAGER`: Department supervision, budget monitoring, and workflow authorization.
  * `OPERATOR`: Interactive task dispatching, approval resolution, and agent management.
  * `MEMBER`: Read-only reporting and workspace collaboration.
* **Autonomous Agents (`agents`)**: Autonomous AI entities scoped to organizations and departments with reporting hierarchies (`parent_id`, `allowed_child_ids`), runtime policies, and memory context.

### 2. MCP Hub & Tool Governance
* **Live Repository Discovery**: Live GitHub and GitLab personal access token (PAT) discovery (`/api/v1/mcp/discover-resources`) that scans public and private repositories without local disk cloning.
* **Multi-Channel Arrays**: Native support for array-based dispatch targets (`allowed_channels`) across Telegram chats and Slack channels with live test dispatch verification (`/api/v1/mcp/test-channel-message`).
* **Department MCP Governance**: Fine-grained tool-level permission grants (`department_mcp_access`) allowing organizations to whitelist specific tools (e.g. `["git_status", "git_diff"]`) while blocking dangerous actions (`git_commit`, `push`) for specific departments.

### 3. Plugins Hub (Local Directory vs Git Repository)
* **Strict Source Separation**: Dedicated modes (`local` vs `git`) for plugin skill discovery:
  * **Local Directory Mode**: Discovers skills from a configured local filesystem folder (`plugins_local_path`).
  * **Git Repository Mode**: Scans remote Git repositories (`plugins_git_repo`).
* **Optional Empty Paths**: Explicit support for "Clear Path" / "Clear Repo"; when a source path is empty, the scanner cleanly returns 0 skills without falling back to unintended system directories.
* **In-Memory Zero-Clone Scanning**: 100% in-memory scanning via GitHub REST API tree and blob endpoints (`_scan_git_repo_via_api`, cached in `_GIT_TREE_SCAN_CACHE`) to detect `SKILL.md` and plugin manifests without writing to disk.

### 4. Workflows Engine & Playbooks
* **Declarative Playbooks**: Expressed in YAML or JSON, supporting bidirectional conversion (`/api/v1/workflows/convert-format`).
* **AI Playbook Generator**: Natural language workflow generator (`/api/v1/workflows/generate`) synthesizing complete multi-step playbooks from user intent.
* **Dedicated Runner Agents**: Automatically instantiates isolated background execution agents (`wf-agent-{id}`) with customized skills, environment variables, and sandbox boundaries.
* **Visual DAG Canvas**: Interactive DAG visualization rendering topological steps, parallel multi-agent stages, conditional evaluation, and step status transitions.
* **Multi-Channel Bindings**: Native webhook triggers (`/api/v1/workflows/webhook/{token}`) and two-way channel bindings (`POST/DELETE /{workflow_id}/channel-binding`) to deliver automated workflow status notifications to Slack/Telegram.

### 5. Frontend Dashboard & Robotics
* **Enterprise Organization Page**: `/organization` located under `ORGANIZATION & GOVERNANCE` in `AppSidebar`, providing member management, department budgets, MCP access grants, and audit trails.
* **Robotic Reusable Components**: Standardized UI component kit (`RoboticHeader`, `RoboticCard`, `RoboticButton`, `RoboticBadge`, `RoboticInput`, `RoboticModal`, `RoboticTable`) ensuring consistent sci-fi/enterprise aesthetic across all views.
* **Curated Model Catalog**: Unified model selector with capability tiers across Anthropic Claude 4/4.5, OpenAI GPT-4o/o3, Google Gemini 2.5, and Local Ollama models.
* **Full Internationalization (i18n)**: Comprehensive English (`en.ts`) and Hebrew (`he.ts`) localization covering all navigation items, workflow steps, org governance, and status badges.

---

## 🧭 Monorepo Structure & Quick Navigation

* **Backend Core (`poc/backend/`)**: FastAPI, SQLite3 (WAL), Cron Scheduler, SSE EventBus. See [`poc/backend/CLAUDE.md`](poc/backend/CLAUDE.md) & [`poc/backend/AGENTS.md`](poc/backend/AGENTS.md).
* **REST API Routers (`poc/backend/api/`)**: Organizations, MCP Hub, Skills/Plugins, Workflows, Agents, Tasks, Projects, Filesystem. See [`poc/backend/api/AGENTS.md`](poc/backend/api/AGENTS.md).
* **Security & Auth (`poc/backend/security/`)**: Pure HS256 JWT, PBKDF2 password hashing, rate limiting (2000 req/min), tenant scoping. See [`poc/backend/security/AGENTS.md`](poc/backend/security/AGENTS.md).
* **Workflows Engine (`poc/workflows/`)**: Topological DAG execution, parallel stages, ephemeral/Docker sandboxing, budget caps. See [`poc/workflows/AGENTS.md`](poc/workflows/AGENTS.md).
* **Runtime Abstraction (`poc/runtime/`)**: Provider-agnostic `RuntimeAdapter`, `ModelPolicyResolver`, and `MODEL_CATALOG`. See [`poc/runtime/AGENTS.md`](poc/runtime/AGENTS.md).
* **Orchestration & Hierarchy (`poc/orchestration/`)**: Multi-agent task trees, hierarchy depth validation, `SupervisorResolver`. See [`poc/orchestration/AGENTS.md`](poc/orchestration/AGENTS.md).
* **Frontend Dashboard (`poc/dashboard/`)**: React 18, Vite, Ant Design, TypeScript, Pixel Office Canvas. See [`poc/dashboard/CLAUDE.md`](poc/dashboard/CLAUDE.md) & [`poc/dashboard/AGENTS.md`](poc/dashboard/AGENTS.md).
* **Data & Persistence (`poc/persistence.py`)**: SQLite schema migrations, self-healing connections, and orphaned record claiming.

---

## 📚 Complete `AGENTS.md` Documentation Index

| Layer | Documentation File | Scope / Responsibilities |
| :--- | :--- | :--- |
| **Root** | [`AGENTS.md`](AGENTS.md) | Platform overview, monorepo directory map, system invariants & sync rules |
| **Root** | [`CLAUDE.md`](CLAUDE.md) | Developer guide, architecture breakdown, verification workflows |
| **Backend Core** | [`poc/backend/AGENTS.md`](poc/backend/AGENTS.md) | Backend service architecture, startup lifespan, dependency injection |
| **Backend Core** | [`poc/backend/CLAUDE.md`](poc/backend/CLAUDE.md) | Backend developer guidelines, testing policies, coding conventions |
| **REST APIs** | [`poc/backend/api/AGENTS.md`](poc/backend/api/AGENTS.md) | Complete documentation of all REST routers, endpoints, and schemas |
| **Security** | [`poc/backend/security/AGENTS.md`](poc/backend/security/AGENTS.md) | JWT tokens, RBAC dependencies, rate limiter middleware, error masks |
| **Workflows** | [`poc/workflows/AGENTS.md`](poc/workflows/AGENTS.md) | WorkflowEngine, WorkflowParser, SandboxManager, DAG execution |
| **Runtime** | [`poc/runtime/AGENTS.md`](poc/runtime/AGENTS.md) | RuntimeAdapter protocol, model tiers, and curated `MODEL_CATALOG` |
| **Orchestration**| [`poc/orchestration/AGENTS.md`](poc/orchestration/AGENTS.md)| Delegation rules, supervisor hierarchy, department MCP checks |
| **Messaging** | [`poc/backend/messages/AGENTS.md`](poc/backend/messages/AGENTS.md)| Agent-to-Agent (A2A) threaded communication and message validation |
| **Teams** | [`poc/backend/teams/AGENTS.md`](poc/backend/teams/AGENTS.md) | Multi-agent team coordination, missions, and result synthesis |
| **Memory** | [`poc/backend/memory/AGENTS.md`](poc/backend/memory/AGENTS.md) | Shared project memory (ADRs, conventions, insights, prompt injection) |
| **Chat** | [`poc/backend/chat/AGENTS.md`](poc/backend/chat/AGENTS.md) | Real-time agent chat drawer, blocker resolution, and streaming |
| **Scheduler** | [`poc/backend/scheduler/AGENTS.md`](poc/backend/scheduler/AGENTS.md)| Cron engine, background polling, and scheduled task triggers |
| **Events** | [`poc/backend/events/AGENTS.md`](poc/backend/events/AGENTS.md) | EventBus pub/sub, SQLite event store, persistent SSE streaming |
| **Approvals** | [`poc/backend/approvals/AGENTS.md`](poc/backend/approvals/AGENTS.md)| Human-in-the-loop permission requests and supervisor escalation |
| **War Room** | [`poc/backend/war_room/AGENTS.md`](poc/backend/war_room/AGENTS.md)| Multi-agent deliberation councils, debate rounds, consensus synthesis|
| **UI Dashboard** | [`poc/dashboard/AGENTS.md`](poc/dashboard/AGENTS.md) | Frontend architecture, React 18, AntD theme, state management |
| **UI Dashboard** | [`poc/dashboard/CLAUDE.md`](poc/dashboard/CLAUDE.md) | Frontend guidelines, build rules, strict TypeScript validation |
| **UI Components**| [`poc/dashboard/src/components/AGENTS.md`](poc/dashboard/src/components/AGENTS.md) | Reusable `Robotic` UI component library and layouts |
| **UI Pages** | [`poc/dashboard/src/pages/AGENTS.md`](poc/dashboard/src/pages/AGENTS.md) | Route pages (Organization, Workflows, MCP, War Room, Office) |
| **UI Context** | [`poc/dashboard/src/context/AGENTS.md`](poc/dashboard/src/context/AGENTS.md) | React context providers (AuthContext, OfficeContext, NotificationContext) |
| **UI Hooks** | [`poc/dashboard/src/hooks/AGENTS.md`](poc/dashboard/src/hooks/AGENTS.md) | Custom React hooks (useOfficeEvents, usePermissions, useLocalStorage) |
| **UI i18n** | [`poc/dashboard/src/i18n/AGENTS.md`](poc/dashboard/src/i18n/AGENTS.md) | English & Hebrew translations, RTL layout handling, terminology |
| **Pixel Canvas** | [`poc/dashboard/src/canvas/AGENTS.md`](poc/dashboard/src/canvas/AGENTS.md) | Virtual office canvas rendering, desk coordinates, agent sprites |

---

## ⚡ Primary Verification Workflows

```bash
# 1. Run all Backend tests (zero mocks, real SQLite)
pytest poc/tests/ -v

# 2. Build Frontend (strict TypeScript compilation & bundle verification)
cd poc/dashboard && npm run build
```

---

## 🛡️ Core System Invariants

1. **Zero Mocks Policy**: We do not use mock database or fake execution layers in tests. All tests run against real SQLite and real FastAPI routers.
2. **Autonomous Execution**: Proactively implement and verify solutions without blocking or asking the user to manually run commands.
3. **Provider-Agnostic Runtime & Model Policy**: Orchestration, hierarchy, and API routers depend strictly on the `RuntimeAdapter` protocol and `ModelPolicyResolver` tiers—never hardcoding provider transport or concrete model names into business logic.
4. **Multi-Tier Clarification Protocol**: If an agent lacks information, it invokes `ask_supervisor`. The system auto-resolves from Project Shared Memory first, routes to the direct manager second, or escalates to the human operator third—never abruptly ending the task as `COMPLETED`.
5. **Self-Healing State & Resumption**: SQLite database connections auto-recreate parent directories and schema if missing. Agent runs capture `session_id` allowing seamless resumption without loss of context.

---

## 🔄 Mandatory `AGENTS.md` Synchronization Rule

> [!IMPORTANT]
> **CRITICAL RULE FOR ALL DEVELOPERS AND AGENTS**:
> Whenever ANY code, logic, endpoint, database schema, orchestration flow, or UI component/page/state/i18n is created, modified, or deleted, you **MUST** update the corresponding directory's `AGENTS.md` (and `CLAUDE.md` where applicable) within the **SAME task/commit**.
>
> 1. **Zero Out-of-Sync Code**: Code changes without matching `AGENTS.md` updates are strictly unacceptable.
> 2. **Surgical Accuracy**: Document exact endpoint paths, HTTP verbs, payload models, parameters, state machines, and invariants.
> 3. **Index Maintenance**: If a new submodule or directory with an `AGENTS.md` is added, register it in the root table of contents immediately.

## Modular implementation map
Current refactoring is documented in [the implementation ledger](docs/refactor-implementation.md). SQLite implementation belongs to poc/storage; public persistence methods remain available through DatabaseManager. Runtime, orchestration and workflow engines use composed collaborators and explicit ports. Backend router_registry/dependencies/runtime_wiring connect implementations; optional router/worker failures do not intentionally abort unrelated startup. Frontend api.ts is a public facade over one HTTP client and domain wrappers; views are lazy and errors are contained to features.

PLATFORM_DISABLED_CAPABILITIES selects optional capabilities at startup. GET /health is liveness; GET /health/ready is required-database readiness; authenticated GET /api/v1/capabilities is a sanitized availability report. Readiness does not establish provider connectivity. The user currently prohibits tests/build/lint/type checks/startup; do not infer authorization from historical verification commands above. No automated or live runtime verification has been performed for the combined refactor.
### Playground verification
Run `.venv/bin/python -m pytest --noconftest poc/tests/test_workflow_playground.py -q` for isolated SQLite/FastAPI contract checks without resetting the application's default database. These tests do not perform paid model inference. Playground is an internal tool-free workflow exercise; it uses the same DAG and configured models but cannot validate live tool effects.

Workflow debugging: use the per-workflow Logs page for run/step errors and stdout/stderr runtime events. Isolated regression tests now exercise actual subprocess output pipes without invoking a model. A short tool-free diagnostic workflow can test the configured provider; passing contract tests alone does not establish provider connectivity.

### Office isolation and plugin cache verification
Run `.venv/bin/python -m pytest --noconftest poc/tests/test_workflow_origin.py poc/tests/test_workflow_playground.py -q` for real SQLite/FastAPI origin and playground contracts. In `poc/dashboard`, run `node --test tests/requestCache.test.mjs` (Node with TypeScript stripping) and `npm run build`. Office scoping is presentation separation, not a new permission boundary; normal task authorization remains required.

### Workflow editing verification
Run `.venv/bin/python -m pytest --noconftest poc/tests/test_workflow_revisions.py poc/tests/test_workflow_origin.py poc/tests/test_workflow_playground.py -q`, then `npm run build` in poc/dashboard. Revision tests use real SQLite and FastAPI, including concurrent writers, migration, pagination, actor attribution, extension-field preservation and tenant isolation.

### Shared assistant authoring verification
Run `.venv/bin/python -m pytest --noconftest poc/tests/test_workflow_assistant.py -q`. The suite uses real SQLite/FastAPI and signed JWTs, plus concurrent save/update requests. It checks stale-token privilege reduction, tenant/department isolation, exact resource approval, client scopes, history, no executable workflow creation, and idempotency. The module's README documents the structured API; no provider/model calls are needed for this backend phase.

## Workflow Assistant model generation
Workflow Assistant model/chat verification: run .venv/bin/python -m pytest --noconftest poc/tests/test_workflow_assistant.py poc/tests/test_workflow_assistant_generation.py -q and npm run build inside poc/dashboard. Generation contracts use real DB/FastAPI and real subprocess lifecycle tests; they do not establish successful live-provider inference. Never run authoring through ordinary tool-enabled task execution.

## Model-only YAML authoring and internal MCP
Model-only/YAML/MCP verification: run .venv/bin/python -m pytest --noconftest poc/tests/test_workflow_assistant.py poc/tests/test_workflow_assistant_generation.py poc/tests/test_workflow_assistant_yaml.py poc/tests/test_workflow_assistant_mcp.py poc/tests/test_workflow_revisions.py poc/tests/test_workflow_origin.py poc/tests/test_workflow_playground.py -q, then npm run build inside poc/dashboard. MCP SDK is pinned >=1.28,<2 in pyproject.toml/poc/requirements.txt; pydantic>=2.11 is required. No mock adapter or destructive shared conftest is used. Native YAML exports do not authorize execution.

Master 523913e was merged into codex/platform-modular-refactor by explicit user request, including queue/revisions/assistant/playground. Source-only review and Git operations were authorized; no tests/build/lint/typecheck/application startup were performed and commit hooks were disabled. See docs/refactor-implementation.md for current contracts and unverified runtime evidence.

## Direct API runtime configuration
The platform default can use CLI backends or direct Anthropic/OpenAI/NVIDIA NIM HTTP inference. Runtime settings remain server-wide; authenticated non-admin users cannot change the default. API credentials and token prices come from the server environment; model IDs are non-secret saved settings. See [setup instructions](docs/runtime-provider-setup.md). Do not run tests, builds, lint, type checking, application startup or paid inference under the current task restriction.

## New workflow chat
Workflows → Create with AI opens a friendly chat/preview dialog powered by the configured runtime model. It is a new implementation, independent of the removed assistant. It uses current DB permissions and credential-free allowlists, offers no model tools, and creates inactive workflows only after an explicit click. See docs/workflow-chat.md for lifecycle and verification limits. No tests, builds, type checking, application startup or live inference were run.

## Governed workflow connector tools
Integration modules now implement fixed-origin GitHub activity reads and strict channel sends with current-policy checks and audited no-retry claims. All connector workflow steps run in connector-only/model-only mode, not through local shell/file tools. Supported-provider metadata is registered without creating grants; explicit tool whitelists remain authoritative. Telegram display labels such as Hermes_test are not accepted as executable chat IDs. The MCP Hub's admin-only Telegram fetch now reads real recent bot updates without sending or consuming messages. Read docs/connector-execution.md before extending tool implementations. Runtime verification remains prohibited for this task.

## Sandboxed repository workspaces
Clone only for steps that run or change code: declare params.workspace on the step. The backend clones on the host (git metadata outside the mount, token only in git's env) and runs every model tool in a no-network Docker container. This requires a Direct API provider and a digest-pinned PLATFORM_SANDBOX_IMAGE, and fails closed without Docker. Write mode opens only a new-branch draft PR; it never pushes to existing branches and never merges. See docs/repo-workspaces.md. No tests, builds, startup, Docker runs or live GitHub calls were performed.

## Security configuration (fail closed)
The server requires JWT_SECRET_KEY (>= 32 chars) unless PLATFORM_DEV_MODE=1. API keys need PLATFORM_API_KEY_ORG_ID. Approval callbacks need TELEGRAM_WEBHOOK_SECRET / SLACK_SIGNING_SECRET. CORS uses PLATFORM_CORS_ORIGINS. SSE and stats are organization-scoped, and task resume never infers permission grants from text. See docs/security-configuration.md. No tests, builds or startup were run.

## Workflow settings (model, machine size, network, secrets)
Each workflow's definition.settings selects a model (default, tier or catalog ID; it overrides the agent model for step tasks), a sandbox machine size (small/medium/large) and an HTTPS egress allowlist enforced by a per-step proxy container. Write-only secrets are stored AES-GCM encrypted (PLATFORM_SECRETS_KEY) or as allowlisted AWS Secrets Manager ARNs, injected only into repository sandboxes as env vars and redacted from tool output. Managing them requires a DB-verified org admin or department manager. See docs/workflow-settings.md. No tests, builds, Docker or AWS calls were run.

Local launch: `uv run python poc/start_api.py` loads repository-root .env through Uvicorn before application import. Configure a persistent random JWT_SECRET_KEY (>=32 chars) in ignored .env; changing it invalidates existing login tokens. Do not print or commit the key.

Provider-visible reasoning summaries are recorded per completed API response and shown in Workflow Logs events; missing summaries are explicit. Encrypted continuation stays in private session transcripts. OpenAI reasoning families use Responses; known Claude families request thinking. Exact contracts: poc/runtime/AGENTS.md. No tests/build/typecheck/startup/provider calls performed.


Workflow/session pricing uses explicit per-call usage events, recorded provenance, additive API cost_summary and private session ledgers. Unknown is not free; actual/reference estimates remain distinct; department accounting retains API_KEY cost_source. NVIDIA hosted prototyping free rates are sourced in runtime/direct_pricing.py. No tests/build/typecheck/startup/inference run.


PR workflow correction: author typed workspace + required_outcome=pull_request, require explicit department write grants and pinned sandbox configuration, and retain receipt-based publication. Governed connector finals use a completed/blocked envelope and blocked work fails rather than triggering success notifications. No tests/build/startup/PRs/message sends performed.


Repository workflow implementation includes manual step mode/connector/repository/ref/PR-title controls, department-scoped catalog loading and static sandbox readiness warnings. Source review only: user explicitly reiterated not to run tests; no tests/build/typecheck/startup or Docker commands were executed.


Workflow authoring is generic and follows the current user request: changes, deliverables, acceptance criteria, dependencies and requested notifications. No version-bump defaults, release policies or fixed notification sequence are imposed. Execution inspects real files and repository instructions, preserves unrelated work and clarifies material missing requirements. Changes sharing a checkout remain in one workspace step because separate steps use independent clones; dependencies do not transfer uncommitted files. Requested PRs use write workspaces with required PR receipts and remain drafts. Notifications report actual exposed milestones and returned URLs. Workspace repository references stay separate from connector resources. This supersedes the earlier version-bump-specific guidance. No saved workflow/grants were modified and no tests/build/typecheck/startup/model calls were performed.


Channel action configuration now requires exactly one matching step mcp_servers connector and authorized_resources destination/tool (send_message or post_chat_message), in addition to its explicit source dependency. Workflow execution preflight checks every channel action before any steps, preventing a malformed final notification from being discovered only after a PR is published. The saved Core plugin patch PR workflow notify_done scope was repaired with an immutable configuration revision; historical failed execution status/PR receipts were retained and nothing was retried. No tests/build/startup/provider calls or messages were performed. Repository workspaces still use per-step shallow clones cleaned up afterward; a shared Git-object cache is not implemented by this repair.


Repository cache implementation: integrations/repo_cache.py, default database-adjacent repo_cache, configurable path/TTL/entry count/retained entry size. Each workflow still gets a fresh independent checkout; no offline stale fallback, shared edits or cached credentials. Existing policy rechecks and audit contracts remain. User prohibits tests: only source review and diff whitespace checks were performed; no runtime/application/Docker/Git/model execution.


Notification configuration change: use existing Channel Binding cadence, not synthetic start/middle/done work stages. Engine lifecycle hooks, per-event audit claims, best-effort delivery warnings and typed chat/UI modes are implemented. Existing workflow revision migration preserves historical run failures and PR receipts. No tests/build/typecheck/startup or message sends performed.

## Organization provider credentials
Organization execution no longer consumes global provider keys/defaults or host CLI/gateway auth. Configure PLATFORM_SECRETS_KEY and re-enter keys/defaults per organization in Runtime settings; existing plaintext globals are not auto-migrated or deleted. See docs/organization-provider-credentials.md for schema, API, rollout and deferred verification. No tests/build/typecheck/startup/provider calls were performed.

Execution backend foundation: definition.settings.execution_backend defaults to direct_api; step params can override. Claude Code uses Agent SDK as the planned transport. All non-direct engines remain explicitly blocked until hosted isolation/credential-proxy/policy integration exists. See docs/execution-backends.md. No SDK install/tests/build/startup/Docker/model calls performed.

The local `uv run python poc/start_api.py` launcher passes the absolute repository-root `.env` path to Uvicorn and defers application import until environment loading. This includes JWT_SECRET_KEY; shell environment values retain precedence. Direct Uvicorn invocations must provide their own environment or --env-file. No startup or tests were performed.

Claude Agent SDK read-only workflow integration is implemented in source, disabled by default. Native Linux/local Docker and a digest-pinned SDK image are required; no Docker Desktop claim. Real Anthropic keys stay in a host broker accessed through a private Unix socket relay. No shell/writes/PR/resume support yet. See docs/claude-hosted.md. Do not enable on the strength of source review; no tests/build/SDK/Docker/startup/inference executed.

Sandbox startup failures now surface sanitized Docker category/exit/reference diagnostics; raw stderr is not echoed into workflow errors. The reported failed PR execution was not rerun or modified. Root Docker cause still requires server evidence; no Docker/tests/startup run.

Explicit diagnostic exception: Docker info/image inspection and one network-disabled sleep-0 container probe were authorized and completed successfully. No test suite, workflow, model or message was run. The broader runtime restriction remains; see docs/workflow-repairs.md.

Governed connector finals now use strict schema-backed internal completion and at most one formatting-only pass without connector tools. It is not an external-action retry; it adds accounted model usage only on a future run when needed. Rejected candidate previews are bounded/redacted and remain scoped to authorized logs. See docs/connector-completion.md. No inference/workflow/tests/build executed for this fix.

## GitHub Actions
See [.github/AGENTS.md](.github/AGENTS.md) for CI triggers, isolated backend contracts, dashboard checks, gated container publishing and PR labels. Workflow creation authorizes future GitHub CI; this task did not run local tests/builds or deploy anything. Branch protection requires repository administration after check names appear.

Initial CI diagnosis: use only contract files versioned on master; branch-local tests cannot be referenced by master workflows. Frontend type checking is mandatory and exposed existing Department/Ant Design option compatibility issues, repaired without suppressing errors. Local runtime checks remain unrun.
