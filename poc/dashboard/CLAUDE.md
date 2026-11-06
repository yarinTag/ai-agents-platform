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
  * Brand title and active platform status indicator.
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
│   │   ├── McpHub.tsx           # MCP integrations hub (/mcp)
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

## Runtime execution method UX
Runtime settings is accessible from OfficeTopBar after first use or deferral. Provider availability is configuration-only, not a live authentication/model test. Direct API requires server credentials/prices and an explicit tool-capable model ID; frontend sends model_id alongside provider_id. Existing active job selection and conversation state must not be replaced when the default changes; current model context refreshes through platform:runtime-changed. Shared English/Hebrew setup copy lives in i18n/runtimeSetup.ts. No frontend build/type checking was run.

## New workflow chat UI
Use the Workflows → Create with AI modal, not the removed standalone Workflow Assistant. Keep the chat small: no YAML editor or provider setup form in the conversation. Exact allowed resource IDs are available under a collapsible list. API jobs are polled with cleanup; private-read denial clears preview/conversation and stops polling. Client retry reuses request IDs; creation retries rely on the server's stored preview/stable workflow ID. Creation is inactive and the workflow list refreshes after success. Localized domain text lives in workflowChat.ts with typed English/Hebrew parity. Current verification restriction still applies.

Chat recovery uses the private workflowChat URL query parameter; successful polling clears transient network errors. A successful saved reply is not a provider failure simply because a later context read failed during development reload.

Execution mode must be explicit. Local-server runs use background dispatch to avoid the shared HTTP timeout; queued mode retains broker errors and never silently retries locally. Neither dispatch mode supplies missing integrations. workflowRun.ts owns EN/HE explanatory copy.

Do not auto-select invented Telegram/Slack destinations. Resource discovery provides candidates, never permissions. Telegram fetch uses the exact edited connector ID and a bounded20s client timeout; administrators explicitly select/save the intended ID. Workflow chat shows backend execution_supported status and receives per-agent connector_tools without secrets. No UI/build/type verification was run.

Connector resource selection uses real discovered IDs and explicit selection/save. Telegram **Find chat IDs** performs read-only discovery; channel aliases are rejected on save and no default destinations are invented.

Installed integration destination tests send exactly one explicit message via connector_id. Keep connection checks separate from message delivery; discovered names persist in channel_labels while allowlists retain canonical IDs.

Connector channel-label persistence reads discoveredResources through the hook state contract; preserve this dependency when changing save logic. Missing state previously threw before the save request. No runtime checks were performed.

Workflow chat step payloads may include send_output_of; preserve it through preview and confirmed creation so explicit channel actions remain deterministic.

Keep channel display names distinct from delivery identities: option label uses channel_labels, value uses channel ID; workflow metadata.channel_name is presentation only. No runtime verification was performed.

AI workflow previews show selected plugin skills; saved proposal payloads retain canonical skill IDs, distinct from display names. Source review only, no build/typecheck executed.

Use one Workflow Skills selection; never require assigning it to each step. Promote legacy assignments on load/import and strip per-step fields on visual export. Tests/build/typecheck remain unrun under current instructions.

Planned workflow runners are labeled as created on confirmation, not existing agents. Unknown agent IDs stay invalid; previews must retain backend validation errors. Runtime verification remains unauthorized.

Never populate workflow agent selectors from static/demo roles. Use authorized live records with department/current-workflow filtering and distinguish planned provisioning from existing agents. No runtime checks performed.

Reasoning logs: preserve reasoning_summary available/not_returned status and full text expansion separately from final answers. Opaque continuation stays private. Events arrive per completed response. No build/test/typecheck performed under current restriction.


Keep reasoning summaries discoverable outside the collapsed Runtime Events section: WorkflowLogs exposes a per-step count badge and dedicated panel above output. No tests/build/startup performed.

WorkflowLogs displays reasoning_summary events only in the dedicated reasoning panel; Runtime Events filters them out and counts only remaining events. Persisted event records and JSON export retain the complete trace. This supersedes the earlier duplicate chronological display. Source review only; no runtime checks performed.

WorkflowLogs reasoning presentation follows the user preference: reasoning_summary appears once in the chronological Runtime Events timeline alongside tools/results. The separate reasoning panel is removed; Runtime Events defaults open when reasoning events exist (or the step failed). The Reasoning (N) header badge remains for discoverability. This supersedes the earlier panel/filter notes. Persistence and JSON export are unchanged. Source review only; no runtime checks performed.


Workflow costs must use formatCost(cost_summary, legacy_cost), not truthy zero hiding or a fabricated zero fallback. Preserve free/unavailable/estimated/reported distinction and separate reference price; usage timeline and inspection expose session totals. No runtime checks performed.


AI creation must preserve workspace and required_outcome DTO fields and distinguish granted workspace operations from read-only connector tools in preview. No build/typecheck executed.


When editing repository steps preserve unknown params, workspace and required_outcome. Use only department catalog repository/operation options, separate workspace mode from connector tools, and display static setup warnings. No tests/build/typecheck/startup performed.


Use Channel Binding for workflow lifecycle update cadence; preserve legacy modes while generating canonical notification configuration. No progress-only DAG stages or model inference for engine notifications. No runtime checks performed.


Keep the Channel Binding notification dropdown at four canonical choices; older persisted modes must not add visible legacy options. Friendly labels live in workflowChat.ts. No tests/build/typecheck performed.

Runtime setup automatic prompts wait for authenticated organization/user context and are shown at most once per user/organization per browser tab session (sessionStorage contains only the shown marker). Explicit Configure runtime still opens the modal. Missing organization keys remain execution-blocking; dismissal grants no credentials. No runtime verification performed.

Completion-validation events now render a bounded redacted candidate preview in StepEventTimeline. Existing scoped logs/export are reused; raw provider envelopes are not displayed. No build/typecheck/render verification was performed for this change.

## CI environment
Dashboard CI and Docker builds target Node22. CI explicitly runs type checking because npm run build only invokes Vite; it also runs lint and request-cache tests. Local runtime verification remains unperformed.

Thread transport controls must remain Anthropic-only, organization-scoped and opt-in, with the temporary-retention notice. RuntimeSettingsPanel now scopes reload to authenticated user/org and disables non-admin edits. Thread events are transport metadata, not TTFT or token savings. No build/typecheck/test execution performed.

## Logic regression command
npm test runs all tests/*.test.mjs with Node22 native TypeScript stripping and locked npm dependencies. The same glob is used by master CI. See tests/AGENTS.md for scope, deterministic race fixtures and limitations; no API keys or external requests are required. No local execution was performed under the current runtime restriction.

## Connection canvas views
Organization workflow and Skills & Plugins canvases share common/ConnectionCanvas. Keep domain graph projection in org/orgWorkflowsCanvasModel.ts and skills/pluginsFlowModel.ts, preserve IDs and configured resource boundaries, and use the existing organization-scoped APIs. Organization canvas copy is paired EN/HE in i18n/orgWorkflowsCanvas.ts. Runtime validation is performed through GitHub CI; no local application startup was performed.


Plugin canvas skill edges represent server-extracted SKILL.md references, not a prescribed
execution sequence. Preserve click focus, cross-package incoming/outgoing traversal and the
separate instruction inspector in skills/PluginSkillFlowGraph.tsx. Do not restore fabricated
Core lifecycle links or infer them from frontend previews. Organization canvases continue to
use the shared ConnectionCanvas renderer. No local runtime verification performed.


Skill-flow follow-up: use skill_connections kinds/evidence for flow, with optional
ordinary references, and preserve declared conditions/source text. Do not convert the
legacy connected_skills list into execution arrows. Package switches must clear focus
and pending reveal work; focused neighbours never override the package filter.
No local tests/build/typecheck/application/browser verification performed.


The Workflows hub must explicitly forward AuthContext.activeDepartmentId to workflow and
execution-list calls and reload on department changes. Clear old scoped rows/selections
and discard late responses before presenting another department. All Departments omits
the filter and remains subject to backend authorization. No local runtime verification.


Use usePermissions/effectivePermissions for presentation: account/membership ranks intersect;
organization admin rights never imply cross-tenant access. Every API request forwards the same
in-memory selected department; API routes independently authorize it. Scope changes remount page
instances, and async profile/401 results must not overwrite a newer login. Do not restore token
secrets in URL/cache keys or host-wide queue/native picker controls. No local tests/build/lint/
typecheck/startup were performed. See docs/access-control-audit.md for exact backend constraints.


WorkflowApprovalPanel is a presentation of backend approval authority: never resolve from local state or URL parameters, expose bearer tokens in Telegram links, or bypass existing department-scoped HTTP transport. Matched EN/HE copy lives in workflowApproval.ts.


For governance UI implementation, follow docs/design/governance-ux.md (AI-14). Keep supported/configured/authorized/provider-verified facts separate, clear stale department data, and distinguish draft/active/execution/approval/action receipt states. Static wireframes are design artifacts, not proof of shipped features or browser behavior.

AI-17: do not mount the admin OrganizationPage for nonadmins. CapabilityGovernancePanel derives current account/membership presentation rights, reads only permitted endpoints and uses selected header department. No All Departments mutation. Preserve review-before-save, expected_revision/409 recovery, role/scope reset and AbortSignal/generation guards. No raw server exception bodies or configuration/credentials are rendered or cached. Full UI contract: docs/design/capability-policy-editor.md. Frontend verification is GitHub CI only; no local UI/runtime startup.

AI-18: preserve current DB-authorized role journeys, scope reset and explicit review/CAS recovery; do not infer rights from a JWT role, group membership or cached catalog. Agent instructions must not weaken a requested approval or offer a runnable unsupported action. See docs/governance-policy-guide.md for the English/Hebrew usage guide and unverified rollout boundaries, and docs/architecture/p01-governance-api.md for exact source DTOs. This documentation task changes no UI/runtime behavior.


## AI-1 workflow table labels (2026-11-06)
WorkflowsPage passes AuthContext departments and an explicit ORG_ADMIN account-role check to createWorkflowColumns. The Department column, including its header, exists only for organization admins. Department names come from the current roster; missing names fall back to IDs and absent departments remain Global. Channel labels come from already-loaded MCP configuration.channel_labels keyed by channel_id, matching provider and connector_id. Legacy bindings without connector_id resolve only with exactly one provider connector. Missing/blank/ambiguous labels fall back to canonical IDs. Department/channel IDs remain in tooltips. Names are presentation metadata, never delivery destinations or grants. No new API requests or backend authorization changes. Static source/diff review only; no local tests/build/typecheck/browser/startup performed.


## AI-2 compact table actions (2026-11-06)
`pages/RowActionMenu.tsx` provides a click-triggered Ant Design Dropdown with a compact ellipsis button, row-specific accessible label/title and typed MenuProps items. Workflows keeps Run visible; Playground, Edit, History, Settings, Logs (router link), Canvas and YAML/JSON Definition move into its menu. Agents keeps Chat with Edit/Delete in its menu; Projects uses Edit/Delete menu; Tasks keeps Logs with manager-only Delegate, Execution tree, running-only Cancel and Delete in its menu. Workflow Executions already has a single Inspect primary action and retains it. Actions columns have compact widths (150px with primary/menu, 90px for menu-only or Inspect). Existing role disables and conditional availability remain intact; Settings remains readable. Destructive items are danger-styled below a divider and require Modal.confirm before calling existing handlers. Workflow deletion retains its existing warning. Names/IDs, backend requests and department scopes are unchanged. AI-1 friendly labels and admin-only Department column remain intact. Source/diff review only; no local tests/build/lint/typecheck/browser/server execution performed under current restrictions.


## AI-4 calendar execution navigation (2026-11-06)
Calendar task cells link to /tasks?taskId=<encoded task ID>; useTasksPage reads that parameter through the authorized getTask API and opens the existing output/error/event console. Closing removes only taskId; stale/unmounted detail responses are ignored and failures show an error. CalendarRun renders status, actual start/end and completed duration, task console links and workflow logs links using canonical workflow/execution IDs. Workflow trigger_type is displayed, with CRON labeled Scheduled (cron); task trigger provenance is unavailable unless matched to a loaded workflow run, never inferred as manual. useCalendarViewPage independently loads up to 200 recent authorized workflow executions with the active department filter, existing polling/request-generation guards and a separate resource error. Cells and date inspection include workflow runs, including runs without tasks; the date modal discloses the 200-run history bound. Activity groups by started_at with created_at fallback; missing actual start/end remains unavailable. No backend/schema/grant changes. Static review only; local tests/build/typecheck/browser/startup remain unauthorized.
