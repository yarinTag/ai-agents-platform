# AGENTS.md - Frontend Architecture & UI Agents Guide

## 1. System Identity & Mission
The **AI Agents Platform Dashboard** (`poc/dashboard/`) is an enterprise-grade, multi-tenant web application providing an interactive mission-control interface for orchestrating autonomous AI agent fleets. It combines real-time spatial simulation (isometric and pixel-art office workstations), directed acyclic graph (DAG) execution tracking, multi-channel workflow automation (Slack, Telegram, GitHub, GitLab), plugin/skill management, and multi-tenant organizational governance.

---

## 2. Technology Stack & Design System

* **Core Framework**: React 18 with TypeScript (`strict: true`)
* **Build Tooling**: Vite with Rolldown bundler
* **Component Library**: Ant Design (`antd` v5) with dark algorithm theme:
  * Base Background: `#0a0d12` (Deep Obsidian)
  * Container Background: `#161b22` (Graphite Navy)
  * Elevated Background: `#1c2128` (Card & Surface Layer)
  * Primary Accent: `#10b981` (Emerald Tech Green)
  * Secondary Borders: `#30363d` / `#21262d`
* **Icons**: `@ant-design/icons`
* **Routing**: `react-router-dom` v6 with layout wrapper pattern (`AppLayout` in `src/App.tsx`)
* **State Management**: React Context (`AuthContext`, `I18nContext`), custom hooks (`useOfficeEvents`), and local component state
* **Networking**: Public compatibility facade (`src/services/api.ts`), domain endpoint clients (`src/services/*Api.ts`), and one Axios transport/interceptor owner (`src/services/httpClient.ts`). Domain clients depend on transport and types, not on one another. Existing consumers retain facade imports.
* **Real-Time Layer**: Global Server-Sent Events (SSE) bus (`src/services/eventStream.ts`) streaming from `/api/v1/events/stream`

---

## 3. Core Architecture Pillars

### 3.1 Multi-Tenant Authentication & Department Context
* **Location**: [`src/context/AuthContext.tsx`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/context/AuthContext.tsx)
* **Tenancy Isolation**: Isolates all users, departments, agents, skills, and tasks by organization.
* **Session Storage**: Synchronizes JWT tokens in `localStorage` under `agents_platform_auth_token` and session profile under `agents_platform_auth_session`.
* **Dynamic Department Selection**: Maintains `activeDepartmentId` globally to allow seamless switching between company units (e.g., Engineering, Marketing, Operations, Executive).
* **Interceptor Binding**: Bearer tokens are automatically attached to all outgoing requests; 401 errors trigger session invalidation and broadcast `auth:unauthorized`.

### 3.2 Internationalization Engine (i18n)
* **Location**: [`src/i18n/I18nContext.tsx`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/i18n/I18nContext.tsx)
* **Dictionaries**: [`src/i18n/locales/en.ts`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/i18n/locales/en.ts) and [`src/i18n/locales/he.ts`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/i18n/locales/he.ts)
* **English Default**: UI is strictly rendered in English by default (`locale: 'en'`).
* **Zero Hardcoded Hebrew**: Hardcoding Hebrew text in JSX is prohibited. All keys are defined in the typed `TranslationDictionary` across both locales, ensuring instant Hebrew RTL toggle capability.
* **Safe Translation Hook**: `useTranslation()` provides `t(key, paramsOrFallback?, fallback?)` with safe dot-notated path resolution and parameter interpolation (e.g., `{count}`).

### 3.3 Navigation Architecture (4 Structured Sections)
* **Location**: [`src/components/layout/AppSidebar.tsx`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/components/layout/AppSidebar.tsx)
* The collapsible navigation sidebar partitions application features into 4 functional domains:
  1. **`OPERATIONS`**:
     * Office Canvas (`/`): Spatial 2D/3D workstation office floor with live status.
     * Workflows (`/workflows`): Dedicated Workflows & Automations Hub for multi-agent DAG pipelines, manual execution, RabbitMQ distributed queue dispatching, and automated run deduplication.
     * Live Flow (`/flow`): Visual task delegation pipeline and live SSE activity feed.
     * Agents Roster (`/agents`): Agent fleet roster, templates, hierarchy, and mini-chats.
  2. **`TOOLS & PLUGINS`**:
     * Plugins Hub (`/skills`): Local directory vs Git repository scanner with collapsible plugin cards.
     * MCP Hub (`/mcp`): Model Context Protocol connectors, multi-channel arrays, and tool permissions.
     * Tasks Queue (`/tasks`): Hierarchical task trees, real-time logs, and human delegation.
  3. **`WORKSPACE & DATA`**:
     * Projects (`/projects`): Workspace directories linked via native folder picker.
     * Schedule & Calendar (`/calendar`): Automated cron routines and HITL approvals.
     * System Metrics (`/dashboard`): System health, node statistics, and platform status.
  4. **`ORGANIZATION & GOVERNANCE`**:
     * Org & Teams (`/organization`): Enterprise departments, budgets, invitations, and user access.

### 3.4 Top Bar Command Center
* **Location**: [`src/components/layout/OfficeTopBar.tsx`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/components/layout/OfficeTopBar.tsx)
* **Interactive Elements**:
  * Sidebar collapse/expand toggle button.
  * Active route indicator with icon, title, and subtitle.
  * Organization Badge: Displays current organization name and opens the `OrgHierarchyModal` on click.
  * Department Switcher Dropdown: `<Select />` dropdown bound to `activeDepartmentId` for instant tenant filtering.
  * User Role Badge: Displays current user avatar, email/name, and role tag (`admin`, `lead`, `member`).
  * Live Clock: Real-time digital clock formatted as `hh:mm:ss a`.

### 3.5 Modular & Robotic UI Components
* **Robotic Design System (`src/components/robotic/`)**:
  * `ModelSelector.tsx`: Dropdown combining static curated models with dynamically discovered backend models. Shows tier color badges, context window sizes, and provider grouping.
  * `DepartmentSelect.tsx`: Standardized dropdown for selecting departments within an organization.
  * `CollapsiblePluginCard.tsx`: Collapsible robotic card displaying plugin details, description, source path/repo, and nested skills list.
* **Organization Governance (`src/components/org/`)**:
  * `DepartmentsBudgetTab.tsx`: Department cards, budget allocation, and department creation.
  * `TeamInvitationsTab.tsx`: Member roster per department and bulk email invitation modal.
  * `OrgUsersTab.tsx`: Organization-wide member list, roles, and status tags.
* **Authentication Forms (`src/components/auth/`)**:
  * `SignInForm.tsx`: Standard credentials login.
  * `RegisterOrgForm.tsx`: Organization creation with admin user and subdomain slug.
  * `AcceptInviteForm.tsx`: Invitation token acceptance and user activation.
* **Workflow Automation & DAG (`src/components/workflows/`)**:
  * `CreateWorkflowModal.tsx`: 4-tab workflow builder (Basics, Multi-channel & MCP scope, Step DAG builder, Live YAML sync).
  * `WorkflowCanvasGraph.tsx`: Interactive SVG canvas showing workflow execution graph.

### 3.6 Curated LLM Model Catalog
* **Location**: [`src/constants/models.ts`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/constants/models.ts)
* **Tiers**:
  * `executive` (Gold `#eab308`): Claude 3.7 Sonnet, Nemotron 3 Super 120B
  * `architect` (Purple `#a855f7`): Claude 3 Opus
  * `developer` (Blue `#3b82f6`): Claude 3.5 Sonnet
  * `worker` (Emerald `#10b981`): Claude 3.5 Haiku, Llama 3.3 70B Instruct
  * `default` (Cyan `#0ea5e9`): System CLI default model
* Formatted context windows (`200K`, `128K`, `1M`) and dynamic provider normalization.

---

## 4. Subsystem Index & AGENTS.md Directory Map

| Path | Documentation File | Description |
|---|---|---|
| `poc/dashboard/` | [**`AGENTS.md`**](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/AGENTS.md) | Master frontend architecture and coordination rules |
| `poc/dashboard/src/pages/` | [**`src/pages/AGENTS.md`**](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/pages/AGENTS.md) | Documentation of all 11 application pages and view state flows |
| `poc/dashboard/src/components/` | [**`src/components/AGENTS.md`**](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/components/AGENTS.md) | Component library across layout, robotic, org, auth, workflows, office, and modals |
| `poc/dashboard/src/context/` | [**`src/context/AGENTS.md`**](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/context/AGENTS.md) | Authentication context, JWT tokens, tenant isolation, and department switching |
| `poc/dashboard/src/i18n/` | [**`src/i18n/AGENTS.md`**](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/i18n/AGENTS.md) | Internationalization system, translation dictionary contract, and English default rule |
| `poc/dashboard/src/services/` | [**`src/services/AGENTS.md`**](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/services/AGENTS.md) | Central Axios client, interceptors, typed API methods, and SSE event streaming |
| `poc/dashboard/src/engine/` | [**`src/engine/AGENTS.md`**](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/engine/AGENTS.md) | Spatial canvas simulation engines (PixelRenderer and AgentsOfficeV3Canvas) |

---

## 5. 🔄 Mandatory UI `AGENTS.md` Synchronization Rule

> [!IMPORTANT]
> **Every time any UI page, component, modal, hook, context state, API client method, or i18n dictionary is added, modified, or refactored, the developer/agent MUST update the corresponding `AGENTS.md` file in `poc/dashboard/` as part of the same task.**
>
> * **Adding or editing a Page**: Update [`src/pages/AGENTS.md`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/pages/AGENTS.md) with new routes, state parameters, or interactions.
> * **Adding or editing a Component or Modal**: Update [`src/components/AGENTS.md`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/components/AGENTS.md) with props, subcomponents, and styling rules.
> * **Modifying Auth, Session, or Context**: Update [`src/context/AGENTS.md`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/context/AGENTS.md) with new context properties or storage behaviors.
> * **Adding Translation Keys or Changing Locales**: Update [`src/i18n/AGENTS.md`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/i18n/AGENTS.md) to reflect dictionary additions.
> * **Adding or Modifying API Endpoints or SSE Handlers**: Update [`src/services/AGENTS.md`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/services/AGENTS.md) with new API signatures and stream behavior.
> * **Modifying Canvas Engine or Rendering Logic**: Update [`src/engine/AGENTS.md`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/engine/AGENTS.md) with new sprites, department layouts, or tick calculations.
> * **High-Level Layout, Architecture, or Navigation Changes**: Update [`poc/dashboard/AGENTS.md`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/AGENTS.md) and [`poc/dashboard/CLAUDE.md`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/CLAUDE.md).

## Feature composition and failure containment
App loads optional route views lazily through LazyFeatureRoute/FeatureErrorBoundary. AppLayout sidebar/topbar remain outside feature boundaries. Exact-router capability gates read authenticated /api/v1/capabilities; composite MCP/Calendar/Agents views use scoped resource states so unrelated sections remain usable. A failed report is a warning, not a global app outage. Runtime setup is separately lazy and deferrable.

The merged `/workflow-assistant`, `/workflows`, and `/workflows/:workflowId/logs` routes use this same lazy/error-contained loading. Workflow log parameter/search navigation resets the route boundary independently. `AppLayout` retains incoming `100dvh`, `minWidth: 0` and `minHeight: 0` scrolling constraints. Existing sidebar parent-route highlighting and Office-scoped snapshots are preserved.

Large pages use page-local hooks and typed panels; workflow/chat/office/war-room components use focused hooks/panels; PixelRenderer composes scene state, lifecycle and painters while retaining its public API. services/resourceLoading distinguishes failed reads from empty results; services/mcpResources owns configured-resource projection. No fake fallback channels/connectors are supplied after failed reads. EN/HE feature-availability keys and RTL infrastructure remain available. No build/type check/browser rendering was performed.

### Internal workflow playground
The Workflows page now launches fresh tool-free exercises through `POST /api/v1/workflows/{workflow_id}/playground`. Execution inspection shows persisted step input/output/status/cost and refreshes while open. WorkflowExecution in `src/types/mcp.ts` includes optional step_runs. See pages/services guides for lifecycle and request details.

### Workflow logs route
`/workflows/:workflowId/logs?execution=<executionId>` renders WorkflowLogsPage for run history and detailed step/runtime diagnostics, with mode filters, search and JSON export. It is linked from each workflow row and execution inspector. Existing authenticated routing and scoped APIs apply.

### Office origin filtering, plugin cache and shell layout
useOfficeEvents accepts an optional execution scope: all by default, office for OfficeView/AgentFlow. Workflow origin is tracked per run/lineage rather than inferred from shared agent identity. Task DTOs include optional workflow_execution_id/workflow_id. Plugin API response caching is bounded, in memory and invalidated on auth/source changes, with explicit manual refresh. The app shell is viewport constrained and navigation/content scroll independently. `tests/requestCache.test.mjs` verifies request sharing, expiry, failure eviction and invalidation races using Node's test runner.

### Workflow edit/history
The Workflows hub now exposes Edit and History. The shared builder supports editing an existing PlatformWorkflow and optional change notes, with revision checks that prevent stale saves. WorkflowHistoryDrawer shows saved configuration snapshots and before/after differences with pagination. This history is distinct from per-run Logs. WorkflowRevision and PlatformWorkflow.revision define typed frontend contracts.

## Workflow Assistant model generation
WorkflowAssistant.tsx mounts at /workflow-assistant and appears under Operations. It uses typed assistant DTOs and uncached authenticated API calls for workspace/catalog/drafts, asynchronous model jobs, validation and explicit save. Query generation restores a private job. EN/HE strings use assistant.*; responsive chat/proposal columns respect RTL. Draft revision capture prevents stale refinements/saves.

## Model-only YAML authoring and internal MCP
WorkflowAssistant now selects an authoring model/provider from authenticated context rather than department agents. The model's execution agents remain per-step proposal data. The page loads the native YAML schema, displays/downloads canonical inactive YAML, validates it through /validate-yaml, shows actual MCP tool names and preserves source revision/history behavior. No local conversation or permission cache is added.

## Direct API provider setup & provider-dependent models (2026-10-31)
`RuntimeSetupModal` configures Direct HTTP API providers (`direct_nvidia`, `direct_anthropic`, `direct_openai`, `direct_openrouter`), optional API keys, enabled providers, and per-provider default models from each provider's model catalog. `OfficeTopBar` Runtime settings reopens it; successful saves emit `platform:runtime-changed` so `ModelSelector` and `useAgentsPage` reload the provider-filtered model list from `/api/v1/models/`.

## Workflow Assistant UI route removal (2026-10-31)
`/workflow-assistant` has been removed from `src/App.tsx`, `AppSidebar.tsx`, and `OfficeTopBar.tsx`. Workflow authoring and AI generation remain consolidated in `/workflows`.

## Friendly workflow chat window
Workflows has a Create with AI action opening WorkflowChatModal: a simple conversation, configured-model label, department selector, step preview and explicit Create workflow. An expandable resource list shows exact authorized repository/channel/tool IDs. useWorkflowChat owns typed context reads, job polling/cancellation, request ID reuse on retries and explicit creation. No removed Workflow Assistant route is restored. New English/Hebrew copy lives in i18n/workflowChat.ts. Runtime/settings changes refresh context; existing jobs keep their captured model. Nothing executes automatically. No build or runtime verification was run.

The AI creation window can recover the authorized stored chat from ?workflowChat=<request-id>. Connection/timeout/HTTP details and transient-error clearing distinguish dev-server reloads from model failures.

Manual Workflow Run now provides an explicit local-server/background option (UI default) and a separate message-queue option. Local mode removes only the broker requirement; it changes neither agent tools nor runtime/governance checks. Errors name unavailable capabilities.

Governed connector resources now distinguish executable availability from a descriptive/connected catalog entry. The chat resource panel shows Available/Unavailable from the server. Telegram Fetch resources requests actual bot chat IDs, has no suggested phantom targets and requires explicit selection/save. Slack lists real-format configured IDs only. This task did not build/run the dashboard.

ChatWorkflow step types preserve optional send_output_of for explicit server-executed channel delivery proposals. No automatic sending occurs from the authoring UI.

Workflow chat catalog types include optional channel_labels (exact-ID-to-display-name map). Destination selectors/chat previews/diagrams display labels while API requests retain canonical IDs.

ChatWorkflow step types carry optional skills:string[]; context catalog includes optional plugin skill metadata. Old stored drafts lacking skills remain compatible.

ChatWorkflow types now support root skills:string[]; optional step skills are legacy compatibility. The workflow builder owns one shared skill selection and all AI steps inherit it.

Workflow chat agent catalog types support provision_on_create. No-agent warnings count the explicit provisioning option as available authoring capacity, while previews distinguish it from an existing execution agent.

The manual workflow agent dropdown now reflects authorized persisted agents, not static role names. A planned dedicated runner is an explicit option only for new workflows; other workflow runners are excluded.



## Reasoning logs (2026-11-01)
Workflow Logs displays persisted reasoning_summary events through StepEventTimeline, separately from results, with expansion and explicit missing-summary status. Existing polling, scoped reads and JSON export apply. Events arrive per completed model response, not live token streaming. No route/API changes or runtime verification.


Workflow Logs reasoning discoverability: collapsed step headers show Reasoning (N) when provider-visible summaries exist; expanded steps show a dedicated summary panel above output, independently of the closed Runtime Events section. Existing records were inspected read-only; no runtime checks or model calls performed.

WorkflowLogs displays reasoning_summary events only in the dedicated reasoning panel; Runtime Events filters them out and counts only remaining events. Persisted event records and JSON export retain the complete trace. This supersedes the earlier duplicate chronological display. Source review only; no runtime checks performed.

WorkflowLogs reasoning presentation follows the user preference: reasoning_summary appears once in the chronological Runtime Events timeline alongside tools/results. The separate reasoning panel is removed; Runtime Events defaults open when reasoning events exist (or the step failed). The Reasoning (N) header badge remains for discoverability. This supersedes the earlier panel/filter notes. Persistence and JSON export are unchanged. Source review only; no runtime checks performed.


Workflow price visibility uses additive CostSummary DTOs plus workflowCosts formatting across execution tables, Logs and inspection. Explicit free zero, estimates and unavailable prices differ; per-call usage and cumulative session prices appear in existing logs/detail. Reference estimates are separate from actual/configured costs. See service/page/component guides. No build or runtime verification.


AI creation preview now exposes repository workspace mode and its currently granted operations separately from read-only MCP tools. ChatStep DTO preserves workspace and required_outcome; catalog DTOs include workspace_operations for connectors/agents. EN/HE copy updated. No build/runtime checks.


Manual Create/Edit now supports typed repository read/write workspace configuration through WorkflowRepositoryFields, using a single department catalog load shared across steps. AI preview and manual fields expose static readiness warnings; neither grants permissions nor executes. Workspace params and required PR outcome survive serialization. No runtime checks performed.


Workflow progress cadence is configured in the existing Channel Binding selector, with canonical completion-only/start-completion/each-step options. AI preview presents channel plus cadence; manual new binding defaults to COMPLETION_ONLY. Historical message stages are not automatically removed from unrelated workflows. No tests/build/typecheck performed.


Channel Binding offers exactly four notification choices with friendly EN/HE names. Legacy final modes remain backend-compatible and render under Finish only rather than adding extra options. No runtime checks performed.
