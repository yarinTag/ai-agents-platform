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
* [**Workflow Assistant Authoring**](poc/backend/workflow_assistant/AGENTS.md): Shared permission-aware catalog, proposal validation, non-executable drafts and revision history for future chat/MCP clients.
* [**Runtime Abstraction**](poc/runtime/AGENTS.md): RuntimeAdapter protocol, model tiers, and curated `MODEL_CATALOG`.
* [**Orchestration & Hierarchy**](poc/orchestration/AGENTS.md): Multi-agent task trees, supervisor chain resolution, and department MCP checks.
* [**Agent-to-Agent Messaging**](poc/backend/messages/AGENTS.md): Peer communication, structured message types, and thread tracking.
* [**Multi-Agent Teams**](poc/backend/teams/AGENTS.md): Dynamic agent squads, missions, and deliverable synthesis.
* [**Project Shared Memory**](poc/backend/memory/AGENTS.md): ADRs, conventions, insights, lessons, and dynamic prompt injection.
* [**Interactive Chat**](poc/backend/chat/AGENTS.md): Agent mini-chat drawer, blocker resolution, and streaming output.
* [**Scheduler & Cron**](poc/backend/scheduler/AGENTS.md): Background cron polling loop, croniter forecasting, and scheduled tasks.
* [**Events & Streaming Bus**](poc/backend/events/AGENTS.md): In-memory EventBus pub/sub, SQLite event store, and persistent SSE stream.
* [**Approvals & HITL**](poc/backend/approvals/AGENTS.md): Human-in-the-loop permission requests, supervisor escalation, and dual-channel Telegram/Slack ChatOps callbacks.
* [**Distributed Queues**](poc/backend/queue/AGENTS.md): RabbitMQ AMQP message broker, priority task queues (1-10), quorum queues, and dead-letter exchanges (DLX).
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
