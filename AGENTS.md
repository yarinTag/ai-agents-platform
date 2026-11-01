# AGENTS.md - Root AI Agents Platform Architecture & Directory Index

## 1. Platform Identity & Architectural Mission
The **AI Agents Platform** is an enterprise multi-tenant autonomous agent orchestration and governance platform. It blends agent hierarchy management, visual DAG workflow execution, real-time collaboration war rooms, scheduled background cron execution, and a virtual pixel office with enterprise multi-tenancy, per-department monthly spending limits, and tool-level Model Context Protocol (MCP) governance.

---

## 2. Platform Architecture Overview

```
                                  [ Enterprise Organization ]
                                               │
               ┌───────────────────────────────┴───────────────────────────────┐
               ▼                                                               ▼
    [ Department A (Budget Cap) ]                                   [ Department B (Budget Cap) ]
               │                                                               │
    ┌──────────┴──────────┐                                         ┌──────────┴──────────┐
    ▼                     ▼                                         ▼                     ▼
[ Members / Roles ] [ Autonomous Agents ]                       [ Members / Roles ] [ Autonomous Agents ]
(ORG_ADMIN,          (Hierarchies,                               (ORG_ADMIN,          (Hierarchies,
 MANAGER,             Dedicated `wf-agent-{id}`)                  MANAGER,             Dedicated `wf-agent-{id}`)
 OPERATOR, MEMBER)                                                OPERATOR, MEMBER)
    │                     │                                         │                     │
    └──────────┬──────────┘                                         └──────────┬──────────┘
               │                                                               │
               ▼                                                               ▼
    [ Department MCP Access ] ──── (Tool-Level Whitelisting) ──── [ MCP Hub & Servers ]
```

### Core Architecture Pillars
1. **Multi-Tenant Enterprise Hierarchy**:
   * **Organizations**: Root tenant domain with separate administrative control, plugin configuration (`plugins_source_mode`, `plugins_local_path`, `plugins_git_repo`), and member directories.
   * **Departments**: Logical operational units with monthly budget limits (`monthly_budget_usd`), alert thresholds (`alert_threshold_pct`), and `HARD_STOP` policy enforcement.
   * **Members & Roles**: Enterprise RBAC hierarchy (`ORG_ADMIN` ➔ `MANAGER` ➔ `OPERATOR` ➔ `MEMBER`) governing system administration, task approval, and workflow execution.
   * **Autonomous Agents**: Org- and department-scoped AI workers organized into reporting chains (`parent_id`, `allowed_child_ids`) with specialized skills and tool access.
2. **Model Context Protocol (MCP) Hub**:
   * Pre-configured connector catalog (`CATALOG_MCP_SERVERS`: GitHub, Trello, Telegram, Slack, PostgreSQL, Brave Search, Filesystem).
   * Live remote repository discovery (`/api/v1/mcp/discover-resources`) via GitHub/GitLab personal access tokens across public and private repositories without disk cloning.
   * Multi-channel destination arrays (`allowed_channels`) for Telegram chats and Slack channels with live verification dispatch (`/api/v1/mcp/test-channel-message`).
   * Department MCP governance (`department_mcp_access`) enforcing granular tool whitelisting and blocking unapproved tool invocations.
3. **Plugins & Skills Hub**:
   * Strict separation between **Local Directory Mode** and **Git Repository Mode**.
   * Optional empty paths support ("Clear Path" / "Clear Repo") that safely return 0 plugins without falling back to unintended system folders.
   * 100% in-memory zero-clone GitHub REST API scanner (`_scan_git_repo_via_api`) that parses remote repository trees and blobs into plugin skill definitions.
4. **Workflows Execution Engine**:
   * Declarative YAML/JSON playbooks with bidirectional format conversion (`/api/v1/workflows/convert-format`).
   * AI-powered natural language playbook generator (`/api/v1/workflows/generate`).
   * Dedicated **Workflows Hub** (`/workflows` under `OPERATIONS` in `AppSidebar`).
   * Automated provisioning of dedicated execution runner agents (`wf-agent-{id}`).
   * RabbitMQ distributed queue dispatching (`platform.workflows.execution`) with SHA-256 payload deduplication, smart caching, and Concurrency group serialization.
   * Topological DAG execution, parallel multi-agent stages, conditional triggers, maker-checker human evaluations, and multi-channel notification bindings.
5. **Modern Dashboard & UI Toolkit**:
   * `OrganizationPage` (`/organization` under `ORGANIZATION & GOVERNANCE` in `AppSidebar`).
   * Reusable `Robotic` component kit (`RoboticHeader`, `RoboticCard`, `RoboticButton`, `RoboticBadge`, etc.).
   * Curated unified `MODEL_CATALOG` across Anthropic, OpenAI, Google Gemini, and Local Ollama.
   * Complete English (`en.ts`) and Hebrew (`he.ts`) internationalization with RTL support.

---

## 3. Master Index of Directory Documentation

### Backend & Service Guides
* [**Root Guide**](CLAUDE.md): Platform overview, verification commands, and operational rules.
* [**Root Architecture**](AGENTS.md): Monorepo architectural map, system invariants, and master documentation index.
* [**Backend Core**](poc/backend/AGENTS.md): FastAPI service architecture, lifespan startup, and dependency injection.
* [**Backend Guidelines**](poc/backend/CLAUDE.md): Backend development standards, test requirements, and conventions.
* [**REST API Routers**](poc/backend/api/AGENTS.md): Complete guide to all backend REST API routes, models, and endpoints.
* [**Security & Hardening**](poc/backend/security/AGENTS.md): HS256 JWT, PBKDF2 hashing, RateLimiterMiddleware (2000 req/min), tenant scoping.
* [**Workflows Engine**](poc/workflows/AGENTS.md): WorkflowEngine, WorkflowParser, SandboxManager, DAG execution, and budgets.
* [**Runtime Abstraction**](poc/runtime/AGENTS.md): RuntimeAdapter protocol, model tiers, and curated `MODEL_CATALOG`.
* [**Orchestration & Hierarchy**](poc/orchestration/AGENTS.md): Multi-agent task trees, supervisor chain resolution, and department MCP checks.
* [**Agent-to-Agent Messaging**](poc/backend/messages/AGENTS.md): Peer communication, structured message types, and thread tracking.
* [**Multi-Agent Teams**](poc/backend/teams/AGENTS.md): Dynamic agent squads, missions, and deliverable synthesis.
* [**Project Shared Memory**](poc/backend/memory/AGENTS.md): ADRs, conventions, insights, lessons, and dynamic prompt injection.
* [**Interactive Chat**](poc/backend/chat/AGENTS.md): Agent mini-chat drawer, blocker resolution, and streaming output.
* [**Scheduler & Cron**](poc/backend/scheduler/AGENTS.md): Background cron polling loop, croniter forecasting, and scheduled tasks.
* [**Events & Streaming Bus**](poc/backend/events/AGENTS.md): In-memory EventBus pub/sub, SQLite event store, and persistent SSE stream.
* [**Approvals & HITL**](poc/backend/approvals/AGENTS.md): Human-in-the-loop permission requests, supervisor escalation, and dual-channel Telegram/Slack ChatOps callbacks.
* [**Distributed Queues**](poc/backend/queue/AGENTS.md): RabbitMQ AMQP message broker, priority task queues (1-10), durable queues, and dead-letter exchanges (DLX).
* [**Database & Postgres RLS**](poc/backend/db/AGENTS.md): Enterprise PostgreSQL schema with kernel-level Row-Level Security (RLS) tenant isolation.
* [**War Room Deliberation**](poc/backend/war_room/AGENTS.md): Multi-agent deliberation councils, debate rounds, consensus synthesis.

### Frontend & UI Guides
* [**Frontend Core**](poc/dashboard/AGENTS.md): React 18, Vite, Ant Design, TypeScript, pixel canvas integration.
* [**Frontend Guidelines**](poc/dashboard/CLAUDE.md): Build verification, component standards, strict TypeScript typing.
* [**UI Component Library**](poc/dashboard/src/components/AGENTS.md): Standardized `Robotic` UI component kit and layouts.
* [**UI Pages & Routes**](poc/dashboard/src/pages/AGENTS.md): Application route pages (Organization, Workflows, MCP, War Room, Office).
* [**UI Context & State**](poc/dashboard/src/context/AGENTS.md): React context providers (AuthContext, OfficeContext, NotificationContext).
* [**UI Custom Hooks**](poc/dashboard/src/hooks/AGENTS.md): Custom hooks (useOfficeEvents, usePermissions, useLocalStorage).
* [**UI Internationalization**](poc/dashboard/src/i18n/AGENTS.md): English (`en.ts`) and Hebrew (`he.ts`) translations, RTL handling.
* [**Pixel Canvas Engine**](poc/dashboard/src/canvas/AGENTS.md): Virtual pixel office canvas, agent sprites, desk coordinates.

---

## 4. Platform Invariant Rules & Guardrails

1. **Zero Mocks Invariant**: All automated integration tests run against real SQLite databases and real FastAPI instances.
2. **Provider-Agnostic Intelligence**: Orchestration and APIs depend on the `RuntimeAdapter` protocol and `ModelPolicyResolver` tiers rather than vendor-specific model strings.
3. **Resumable Execution**: Every agent run captures `session_id` allowing seamless continuation via `resume_task` without loss of execution history.
4. **Self-Healing Persistence**: Database connections automatically recreate directories and schema if the database file is removed at runtime (`poc/persistence.py`).
5. **Multi-Tier Clarification**: Ambiguous tasks invoke `ask_supervisor` (Tier 1: Shared Memory ➔ Tier 2: Manager ➔ Tier 3: Human Operator) and never falsely conclude as `COMPLETED`.

---

## 🔄 Mandatory `AGENTS.md` Synchronization Rule

> [!IMPORTANT]
> **MANDATORY POLICY FOR ALL DEVELOPERS AND AGENTS**:
> Whenever ANY code, logic, endpoint, database schema, orchestration flow, or UI component/page/state/i18n is created, modified, or deleted, you **MUST** update the corresponding directory's `AGENTS.md` (and `CLAUDE.md` where applicable) within the **SAME task/commit**.
>
> * **No Out-of-Sync Code**: Submitting code modifications without corresponding updates to the relevant `AGENTS.md` files is strictly prohibited.
> * **Precise Technical Contracts**: Document exact routes, request/response models, database columns, enum values, and state transition rules.
> * **Master Directory Registration**: If a new submodule or directory is created with an `AGENTS.md`, immediately register its link in this root table of contents.

## Modular refactor source policy
Owned source files must remain at most 500 physical lines, including comments and blank lines. Split by responsibility and preserve public contracts. Third-party dependencies and generated build outputs are excluded. See [refactor roadmap](docs/refactor-roadmap.md) and [SQLite storage components](poc/storage/AGENTS.md), which owns composed repositories, records, connections and the legacy persistence facade. Runtime verification is not authorized in the current task.

## Refactor implementation index
* [Plugin discovery](poc/plugins/AGENTS.md): HTTP-independent metadata, local and Git adapters.
* [External channel adapters](poc/integrations/AGENTS.md): acknowledged Telegram/Slack delivery, no simulated success.
* [Test source organization](poc/tests/AGENTS.md): existing cases/fixtures split by responsibility; not executed.
* [Implementation and code review ledger](docs/refactor-implementation.md): ownership, source evidence, intentional corrections and unverified runtime requirements.

Demo registration is implemented once in poc/demo_data.py and imported by both explicit demo/setup entry points. No demo registration was executed during this refactor.
## Internal Workflow Playground (2026-10-24)
`POST /api/v1/workflows/{workflow_id}/playground` runs the existing DAG with fresh tool-free model inference. Runs use `PLAYGROUND`, `pg_exec_` execution IDs, `pg_task_` task IDs, and a separate deduplication hash namespace. No channel notifications, automatic reviewer tasks, supervisor escalation, or production completion callbacks run. This is a prompt/data exercise, not a full container security boundary or live integration test. See workflows and runtime guides. Contract tests: `poc/tests/test_workflow_playground.py` use real SQLite and FastAPI; run with `--noconftest` to avoid the shared default-database reset fixture.

`DatabaseManager.update_workflow_execution` accepts `sandbox_path` so pre-created QUEUED execution records capture their workspace when execution starts.

Per-workflow run diagnostics are available at `/workflows/:workflowId/logs?execution=<executionId>`, using scoped execution details and persisted runtime events. The Workflows table exposes a Logs link per workflow.

## Workflow/office execution visibility and catalog caching
Workflow task origin is resolved through workflow_step_runs and task parent/root lineage, without changing shared agent definitions or adding schema columns. Office and Live Flow request office-scoped task/activity snapshots and ignore workflow-tagged SSE events; the global Tasks view still shows all runs. See backend API/events and dashboard guides. Plugins use a bounded session-memory client cache with explicit invalidation and manual refresh; the application shell uses independent navigation/content scrolling.

## Workflow editing and revision history
Existing workflows can be edited in the shared visual/YAML builder and inspected through History. SQLite workflows.revision starts at 1; workflow_revisions stores full configuration snapshots and actor/change metadata. Each effective update appends a revision in the same BEGIN IMMEDIATE transaction; expected_revision provides optimistic concurrency. Existing records receive one Legacy baseline; earlier edits cannot be reconstructed. See backend API and workflow guides. Execution deduplication includes the saved revision so edits cannot reuse outputs from an older definition.

## Shared workflow authoring foundation
The protected `/api/v1/workflow-assistant` service reads current database user/membership/role policy, returns a sanitized organization/department resource catalog, validates strict proposals and stores non-executable drafts separately from workflows. Invalid proposals return structured errors; explicitly opted-in blocked proposals remain authoring records, never active workflows. Draft revisions/idempotency and current-policy revalidation are transactional. Chat generation and internal MCP authoring are implemented; external OAuth/MCP installation, publication and activation remain future work. Details and schema are in the module guide.

## Workflow Assistant model generation
Workflow Assistant phase two adds /workflow-assistant chat and isolated asynchronous model generation; its backend contract is documented in poc/backend/workflow_assistant/AGENTS.md. Configured runtime model/provider routing is reused without agent tasks or Office events; the internal MCP tool inventory is limited to catalog/schema/YAML validation. Draft save remains explicit and versioned; External MCP login/transport and workflow activation remain future work.

## Model-only YAML authoring and internal MCP
The Workflow Assistant now selects model_id/provider_id directly, uses an internal process-bound MCP server (catalog/schema/YAML validation only), and emits inactive native workflow YAML. Canonical governed schema: [Workflow authoring schema](poc/workflows/workflow-authoring.schema.yaml), generated from workflows.authoring_schema.WorkflowDocument. Execution agents remain per-step assignments; no planning agent is selected or persisted. The external installable OAuth MCP server remains future work.

The model returns a generation-scoped validation_id for a server-stored YAML candidate instead of regenerating the document after validation; current permissions and candidate integrity are rechecked before presenting/saving.

## Master merge composition (2026-10-29)
The refactor now includes master 523913e. Workflow revision/history, assistant/internal MCP, playground, queue, Office task-origin scoping and plugin cache remain available through extracted modules. backend/queue_lifecycle owns independent broker/worker startup; backend/workflow_wiring injects policy/output and optional human-approval delivery into workflow execution. No tests/build/application were executed during integration.

## Direct HTTP API providers and provider-scoped models (2026-10-31)
Runtime execution now uses Direct HTTP API calls (`runtime.direct_worker` across `direct_nvidia`, `direct_anthropic`, `direct_openai`, and `direct_openrouter`) instead of spawning the `claude` CLI binary. `RuntimeSetupModal` allows configuring API providers, API keys, and per-provider default models, and `GET /api/v1/models` dynamically returns only the models belonging to the configured/enabled provider(s).

## Workflow Assistant full removal (2026-10-31)
All Workflow Assistant modules, routes, and schemas (`poc/backend/workflow_assistant/`, `poc/runtime/authoring.py`, `poc/workflows/authoring_schema.py`, `poc/workflows/workflow-authoring.schema.yaml`, `poc/dashboard/src/pages/WorkflowAssistant.tsx`, `poc/dashboard/src/services/assistantApi.ts`, `poc/dashboard/src/types/assistant.ts`, `assistant.*` i18n keys, `workflow_assistant_*` SQLite tables, and `poc/tests/test_workflow_assistant*.py`) have been completely removed so all workflow creation and AI generation are consolidated in `/workflows`.

## Friendly workflow creation chat (2026-10-31)
The new workflow chat lives inside the Workflows hub (Create with AI), independently of the removed Workflow Assistant. Backend contracts, policy and strict reply models live in backend/api/workflow_chat*.py; model-only transport lives in runtime/workflow_chat.py. The configured model receives only current department-authorized resource IDs (repositories/channels/tools/agents). Human-confirmed creation revalidates the stored preview and provisions an inactive workflow through shared creation logic. See the [REST API guide](poc/backend/api/AGENTS.md) and [chat implementation notes](docs/workflow-chat.md). The removed assistant, internal MCP transport and schema are not restored. Runtime verification remains unauthorized.

Workflow chat recovery uses a private workflowChat query ID to restore stored conversation/results after refresh. Polling HTTP success is distinct from job completion; transient reconnect errors clear on success. See docs/workflow-chat.md.

Manual workflow execution now offers explicit local-server background dispatch alongside RabbitMQ dispatch. The /execute API adds background=false; use_queue=false&background=true creates a real queued record and invokes the same governed workflow engine without a broker. It is process-local, not durable, and supplies no additional MCP tools.

## Governed connector execution (2026-10-31)
Production workflow steps now use server-owned tool scopes for GitHub.com read operations and exact-ID Telegram/Slack sends through Direct API workers. Each actual call intersects its frozen step resources with current tenant/department/agent permissions, user status, budget and run lifetime. Connector-backed workflows (including analysis steps and reviews) have no shell/file/delegation tools; Playground and workflow chat receive no live connectors. Successful audited receipts are required for completion. The known exact legacy preview sentence is removed from production step input without rewriting saved workflow revisions. See [connector execution](docs/connector-execution.md) and integrations/runtime/workflow guides. No tests, live connector/model calls or message sends were executed.

Optional completion delivery is separate from required workflow work: invalid Telegram/Slack targets are blocked and surfaced as notification_error warnings, while authorized data steps can continue. Explicit channel-send steps remain required and fail closed.

Explicit workflow channel delivery uses params.channel_action (send_channel_message, connector_id, channel_id, source_step) and the governed tool executor rather than model-selected calls. Chat proposals expose send_output_of. See workflow/API guides; Playground performs no sends.

AI workflow chat now catalogs current organization plugin skills, validates and preserves ChatStep.skills, and shows selected skills in preview. Workflow execution resolves full skill instructions within the organization source, without global skill-cache fallback. See plugin/API/workflow guides.

Workflow Skills is now a single shared selection inherited by every AI step. Legacy step skills are promoted/deduplicated; deterministic delivery actions do not load skills. AI chat and the visual builder save shared root skills. See workflow/API/dashboard component guides.

Workflow AI chat exposes an explicit planned dedicated-runner option, materialized only during confirmed creation. It does not require an Office agent or reuse other workflow runners. Current department/resource grants still govern all steps; unknown IDs are rejected.
