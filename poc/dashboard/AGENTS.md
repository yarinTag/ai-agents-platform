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
* **Networking**: Central Axios client (`src/services/api.ts`) with request/response interceptors
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
     * MCP Hub (`/mcp`): Model Context Protocol connectors, multi-channel arrays, and workflow triggers.
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

### Internal workflow playground
The Workflows page now launches fresh tool-free exercises through `POST /api/v1/workflows/{workflow_id}/playground`. Execution inspection shows persisted step input/output/status/cost and refreshes while open. WorkflowExecution in `src/types/mcp.ts` includes optional step_runs. See pages/services guides for lifecycle and request details.

### Workflow logs route
`/workflows/:workflowId/logs?execution=<executionId>` renders WorkflowLogsPage for run history and detailed step/runtime diagnostics, with mode filters, search and JSON export. It is linked from each workflow row and execution inspector. Existing authenticated routing and scoped APIs apply.

### Office origin filtering, plugin cache and shell layout
useOfficeEvents accepts an optional execution scope: all by default, office for OfficeView/AgentFlow. Workflow origin is tracked per run/lineage rather than inferred from shared agent identity. Task DTOs include optional workflow_execution_id/workflow_id. Plugin API response caching is bounded, in memory and invalidated on auth/source changes, with explicit manual refresh. The app shell is viewport constrained and navigation/content scroll independently. `tests/requestCache.test.mjs` verifies request sharing, expiry, failure eviction and invalidation races using Node's test runner.

### Workflow edit/history
The Workflows hub now exposes Edit and History. The shared builder supports editing an existing PlatformWorkflow and optional change notes, with revision checks that prevent stale saves. WorkflowHistoryDrawer shows saved configuration snapshots and before/after differences with pagination. This history is distinct from per-run Logs. WorkflowRevision and PlatformWorkflow.revision define typed frontend contracts.
