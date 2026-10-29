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
   * Automated provisioning of dedicated execution runner agents (`wf-agent-{id}`).
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
* [**Approvals & HITL**](poc/backend/approvals/AGENTS.md): Human-in-the-loop permission requests and supervisor escalation.
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
