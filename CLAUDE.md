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

### Playground verification
Run `.venv/bin/python -m pytest --noconftest poc/tests/test_workflow_playground.py -q` for isolated SQLite/FastAPI contract checks without resetting the application's default database. These tests do not perform paid model inference. Playground is an internal tool-free workflow exercise; it uses the same DAG and configured models but cannot validate live tool effects.

Workflow debugging: use the per-workflow Logs page for run/step errors and stdout/stderr runtime events. Isolated regression tests now exercise actual subprocess output pipes without invoking a model. A short tool-free diagnostic workflow can test the configured provider; passing contract tests alone does not establish provider connectivity.

### Office isolation and plugin cache verification
Run `.venv/bin/python -m pytest --noconftest poc/tests/test_workflow_origin.py poc/tests/test_workflow_playground.py -q` for real SQLite/FastAPI origin and playground contracts. In `poc/dashboard`, run `node --test tests/requestCache.test.mjs` (Node with TypeScript stripping) and `npm run build`. Office scoping is presentation separation, not a new permission boundary; normal task authorization remains required.
