# CLAUDE.md - Frontend Guidelines (Dashboard)

This document provides developer instructions, architectural invariants, and component standards for Claude Code working on the `poc/dashboard` React application.

---

## 🚀 Quick Commands

* **Install Dependencies**: `npm install`
* **Development Server**: `npm run dev` (starts on `http://localhost:5173`)
* **Production Build**: `npm run build` (runs `vite build`, verifies TypeScript types & bundles)
* **Preview Production**: `npm run preview`
* **Type Checking**: `npx tsc --noEmit` (run ONLY if explicitly requested)

---

## 🏗️ Architecture & Technology Stack

* **Framework**: React 18 with TypeScript (`strict: true`)
* **Bundler & Tooling**: Vite + Rolldown
* **UI Component Library**: Ant Design (`antd` v5) with dark algorithm theme:
  * Base Background: `#0a0d12`
  * Container Background: `#161b22`
  * Elevated Background: `#1c2128`
  * Primary Accent: Emerald `#10b981`
  * Borders: `#30363d` / `#21262d`
* **Icons**: `@ant-design/icons`
* **Routing**: `react-router-dom` v6 (`AppLayout` shell, route definitions in `src/App.tsx`)
* **Multi-Tenant Authentication & Department Context**:
  * `src/context/AuthContext.tsx`: Manages JWT tokens, authenticated `user`, current `organization`, department roster, and `activeDepartmentId`.
  * Auto-injects bearer token into Axios headers and handles 401 session expiry.
* **Internationalization (i18n)**:
  * `src/i18n/I18nContext.tsx`, `src/i18n/locales/en.ts`, `src/i18n/locales/he.ts`.
  * English default UI (`'en'`) with zero hardcoded Hebrew strings in components.
  * Instant future Hebrew RTL toggle support via typed `TranslationDictionary`.
* **Sidebar Navigation (`src/components/layout/AppSidebar.tsx`)**:
  * 4 structured navigation sections:
    1. `OPERATIONS`: Office Canvas (`/`), Live Flow (`/flow`), Agents Roster (`/agents`).
    2. `TOOLS & PLUGINS`: Plugins Hub (`/skills`), MCP Hub (`/mcp`), Tasks Queue (`/tasks`).
    3. `WORKSPACE & DATA`: Projects (`/projects`), Schedule & Calendar (`/calendar`), System Metrics (`/dashboard`).
    4. `ORGANIZATION & GOVERNANCE`: Org & Teams (`/organization`).
* **Top Bar (`src/components/layout/OfficeTopBar.tsx`)**:
  * Live status indicator with route titles.
  * Clickable organization badge (triggers `OrgHierarchyModal`).
  * Department switcher dropdown (`Select`) bound to `AuthContext`.
  * User identity & role badge (`admin`, `lead`, `member`).
  * Live digital clock.
* **Modular UI Components**:
  * Robotic UI (`src/components/robotic/`): `ModelSelector.tsx`, `DepartmentSelect.tsx`, `CollapsiblePluginCard.tsx`.
  * Organization Governance (`src/components/org/`): `DepartmentsBudgetTab.tsx`, `TeamInvitationsTab.tsx`, `OrgUsersTab.tsx`.
  * Authentication Forms (`src/components/auth/`): `SignInForm.tsx`, `RegisterOrgForm.tsx`, `AcceptInviteForm.tsx`.
  * Workflows & DAG (`src/components/workflows/`): `CreateWorkflowModal.tsx`, `WorkflowCanvasGraph.tsx`.
* **Curated LLM Model Catalog (`src/constants/models.ts`)**:
  * Tier classification (`executive`, `architect`, `developer`, `worker`, `default`).
  * Providers: Anthropic Claude (3.7 Sonnet, 3.5 Sonnet, 3.5 Haiku, 3 Opus) and NVIDIA NIM (Nemotron 3 Super 120B, Llama 3.3 70B Instruct).
  * Enriched dynamically with discovered backend models via `getAvailableModels()`.
* **Graphics & Simulation Engine**:
  * HTML5 Canvas Pixel Renderer (`src/engine/PixelRenderer.ts` & `src/components/office/PixelOfficeCanvas.tsx`).
  * High-fidelity Isometric Office Workspace (`src/components/office/AgentsOfficeV3Canvas.tsx`) with zoom/pan and live agent workstations.
* **Real-time Event Streaming**:
  * Global SSE client (`src/services/eventStream.ts`) streaming from `/api/v1/events/stream`.
  * React hook: `useOfficeEvents` (`src/hooks/useOfficeEvents.ts`) with zero polling loops.

---

## 📁 Directory Structure

```
poc/dashboard/
├── AGENTS.md                    # Master UI agents guide & architectural map
├── CLAUDE.md                    # Developer guidelines and commands
├── index.html                   # HTML entry point
├── package.json                 # Dependencies and scripts
├── src/
│   ├── App.tsx                  # Root routes and Ant Design ConfigProvider
│   ├── components/
│   │   ├── AGENTS.md            # Components documentation & catalog
│   │   ├── agents/              # CharacterSelector, HierarchyEditor, TemplateGallery
│   │   ├── approval/            # ApprovalModal (HITL decisions)
│   │   ├── auth/                # SignInForm, RegisterOrgForm, AcceptInviteForm
│   │   ├── chat/                # AgentMiniChatDrawer (interactive agent mini-chat)
│   │   ├── common/              # FolderPickerModal, OrgHierarchyModal, RuntimeSetupModal
│   │   ├── flow/                # AgentFlowDiagram (live visual pipeline)
│   │   ├── layout/              # AppLayout, AppSidebar, OfficeTopBar
│   │   ├── memory/              # ProjectSharedMemoryModal
│   │   ├── office/              # AgentsOfficeV3Canvas, PixelOfficeCanvas, OfficeRightSidebar, AgentDeskDrawer
│   │   ├── org/                 # DepartmentsBudgetTab, TeamInvitationsTab, OrgUsersTab
│   │   ├── robotic/             # ModelSelector, DepartmentSelect, CollapsiblePluginCard
│   │   ├── scheduler/           # CronBuilderModal
│   │   ├── warroom/             # WarRoomModal (multi-agent deliberation)
│   │   └── workflows/           # CreateWorkflowModal, WorkflowCanvasGraph
│   ├── constants/
│   │   └── models.ts            # Curated LLM catalog, tiers, context windows, colors
│   ├── context/
│   │   ├── AGENTS.md            # State & AuthContext documentation
│   │   └── AuthContext.tsx      # Multi-tenant auth, session, and department state
│   ├── engine/
│   │   ├── AGENTS.md            # Spatial rendering engine documentation
│   │   └── PixelRenderer.ts     # Procedural pixel art canvas engine
│   ├── hooks/
│   │   └── useOfficeEvents.ts   # SSE live hook for agents and tasks
│   ├── i18n/
│   │   ├── AGENTS.md            # i18n & localization documentation
│   │   ├── I18nContext.tsx      # Translation context & useTranslation hook
│   │   ├── index.ts             # Barrel exports
│   │   └── locales/             # en.ts (default), he.ts (RTL support)
│   ├── pages/
│   │   ├── AGENTS.md            # Pages documentation & route catalog
│   │   ├── AgentFlow.tsx        # Live delegation flow (/flow)
│   │   ├── Agents.tsx           # Fleet roster & agent management (/agents)
│   │   ├── AuthPage.tsx         # Sign-in, org register, invite accept
│   │   ├── CalendarView.tsx     # Cron routines & schedules (/calendar)
│   │   ├── Dashboard.tsx        # System metrics & node health (/dashboard)
│   │   ├── McpHub.tsx           # MCP integrations & workflows (/mcp)
│   │   ├── OfficeView.tsx       # Live interactive workstation canvas (/)
│   │   ├── OrganizationPage.tsx # Org & Teams governance (/organization)
│   │   ├── Projects.tsx         # Workspace directory projects (/projects)
│   │   ├── Skills.tsx           # Plugins Hub (/skills)
│   │   └── Tasks.tsx            # Orchestrated tasks queue (/tasks)
│   ├── services/
│   │   ├── AGENTS.md            # API client & SSE stream documentation
│   │   ├── api.ts               # Public endpoint compatibility facade
│   │   ├── httpClient.ts        # Shared Axios client and interceptors
│   │   └── eventStream.ts       # SSE event bus client
│   └── types/                   # TypeScript interfaces (agent, task, mcp, auth, etc.)
```

---

## 📚 Complete Index of UI AGENTS.md Files

* [**`poc/dashboard/AGENTS.md`**](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/AGENTS.md): Master Frontend architecture and coordination guide.
* [**`src/pages/AGENTS.md`**](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/pages/AGENTS.md): Full documentation of all 11 application pages and route views.
* [**`src/components/AGENTS.md`**](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/components/AGENTS.md): Component library catalog across layout, robotic, org, auth, workflows, office, and modals.
* [**`src/context/AGENTS.md`**](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/context/AGENTS.md): AuthContext, multi-tenant session isolation, and department switching.
* [**`src/i18n/AGENTS.md`**](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/i18n/AGENTS.md): Translation engine, English-default UI rules, and locale dictionary contracts.
* [**`src/services/AGENTS.md`**](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/services/AGENTS.md): Axios client methods, request/response interceptors, and real-time SSE stream.
* [**`src/engine/AGENTS.md`**](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/engine/AGENTS.md): Spatial canvas engines (`PixelRenderer.ts` and `AgentsOfficeV3Canvas.tsx`).

---

## 🔄 Mandatory UI `AGENTS.md` Synchronization Rule

> [!IMPORTANT]
> **Every time any UI page, component, modal, hook, context state, API client method, or i18n dictionary is added, modified, or refactored, the developer/agent MUST update the corresponding `AGENTS.md` file in `poc/dashboard/` as part of the same task.**
>
> 1. When modifying a page in `src/pages/`, update [`src/pages/AGENTS.md`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/pages/AGENTS.md).
> 2. When creating or altering a component in `src/components/`, update [`src/components/AGENTS.md`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/components/AGENTS.md).
> 3. When altering authentication, tenancy, or context state in `src/context/`, update [`src/context/AGENTS.md`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/context/AGENTS.md).
> 4. When adding translation strings or modifying i18n mechanics in `src/i18n/`, update [`src/i18n/AGENTS.md`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/i18n/AGENTS.md).
> 5. When adding or updating API endpoints or SSE streaming in `src/services/`, update [`src/services/AGENTS.md`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/services/AGENTS.md).
> 6. When modifying canvas rendering or simulation logic in `src/engine/` or office canvas components, update [`src/engine/AGENTS.md`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/engine/AGENTS.md).
> 7. If routing, top-level layout, or high-level architecture changes, update [`poc/dashboard/AGENTS.md`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/AGENTS.md) and [`poc/dashboard/CLAUDE.md`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/CLAUDE.md).

---

## 📐 Coding Conventions & Guidelines

1. **TypeScript Strictness**:
   * Always define typed DTOs and interfaces in `src/types/`. Do NOT use `any` unless absolutely necessary for third-party interop.
   * Verify every change compiles cleanly using `npm run build` or `npx tsc --noEmit` if instructed.
2. **Component Structure**:
   * Functional components with explicit `React.FC<Props>` typing.
   * Destructure props and provide sensible defaults.
   * Clean up event listeners, timers, and SSE streams in `useEffect` cleanup functions.
3. **API Integration**:
   * UI consumers use the public `src/services/api.ts` facade. Endpoint implementations belong to domain `src/services/*Api.ts` modules and import the shared Axios instance from `httpClient.ts`; never import the facade inside a domain client. Only `httpClient.ts` registers HTTP interceptors. Place reusable DTOs in `src/types/` and re-export legacy public types through the facade.
   * Standard Axios response pattern: `const res = await apiMethod(); setState(res.data)`.
   * Handle errors gracefully with Ant Design's `message.error(...)`.
4. **Ant Design & Dark Theme Conventions**:
   * Use theme tokens and Ant Design primitives (`Button`, `Modal`, `Drawer`, `Card`, `Tag`, `Typography`, `Table`, `Tabs`, `Segmented`).
   * When wrapping multiple adjacent elements in table column `render` functions, always wrap them in a `<div style={{ display: 'flex', gap: '8px' }}>` container to prevent JSX syntax errors.
5. **Real-Time Responsiveness**:
   * Avoid polling loops where possible. Rely on `useOfficeEvents` SSE push for live updates.
6. **Localization Hygiene**:
   * All user-facing copy in components must be in English. Never hardcode Hebrew strings in JSX.
   * Use `const { t } = useTranslation();` for internationalized copy.

## Optional feature conventions
Keep route imports lazy and errors within FeatureErrorBoundary; shell navigation must remain usable. Gate only the exact unavailable capability, not a composite page's independent resources. Use shared resourceLoading/mcpResources rather than repeated fallback state or fabricated connector/channel defaults. ResourceWarning displays scoped failures/retry while independent content remains. Runtime setup can be deferred; backend execution gates remain authoritative. Current user restriction prohibits execution verification.

### Playground UI verification
The Workflows launch modal supports a tool-free Playground mode with JSON-object validation, fresh runs and clear model cost/tool availability text. Verify with `npm run build`; execution inspection uses scoped detail responses rather than list summaries for per-step output.

Workflow logs live at `/workflows/:workflowId/logs`, with an optional execution query parameter. Validate empty history, early failures, live steps, navigation cleanup and authorized JSON export when changing this view. `npm run build` validates the production bundle.

### Navigation, plugins and office scope
Use bounded client request caching for plugin discovery (60s) and source config (30s); do not persist catalog content or credentials in browser storage. Manual scans must bypass both client results and the Git scan cache. Keep Office/Live Flow office-scoped without hiding workflow executions from Tasks. The outer app shell must stay viewport constrained while Content/sidebar navigation own scrolling. Verify the cache with `node --test tests/requestCache.test.mjs`, then build with `npm run build`.

### Workflow editor compatibility
Editing must retain workflow identity and unknown YAML/JSON extension fields. Do not apply connector catalog defaults over saved edit state. Save expected_revision and retain the draft on 409. Configuration history belongs in History; execution diagnostics remain in Logs. Validate the bundle with npm run build and backend revision tests with isolated SQLite/FastAPI.

## Workflow Assistant model generation
Workflow Assistant route /workflow-assistant uses existing auth and typed API wrappers, no browser-stored conversation/permission cache. Poll private generation IDs with cleanup, handle provider errors visibly, require explicit save or save-blocked, and preserve captured draft versions. Never dispatch planning as an Office task. Verify with npm run build in poc/dashboard.

## Model-only YAML authoring and internal MCP
Workflow Assistant selection must use context.authoring_models; never derive planning choices from catalog.agents. Agents in the proposal are execution assignments. Use server-provided definition_yaml for preview/download and validateAssistantYaml for native validation. Show draft-only behavior and server errors; do not silently replace an unsupported provider/model or activate downloaded YAML.
