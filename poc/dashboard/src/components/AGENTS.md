# AGENTS.md - UI Component Library & Design System

## 1. Overview & Directory Mission
The `src/components/` directory provides modular, reusable, and typed React components implementing the platform's robotic dark aesthetic. All components adhere to Ant Design v5 dark tokens, strict TypeScript interfaces, and consistent color palettes (Emerald `#10b981`, Deep Obsidian `#0a0d12`, Slate borders `#30363d`).

---

## 2. Component Subsystems & Directory Catalog

### 2.1 `layout/` - Application Shell & Headers
* **[`AppLayout.tsx`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/components/layout/AppLayout.tsx)**:
  * Master application shell wrapper with collapsible sidebar state (`collapsed`).
  * Integrates `OfficeTopBar` at the top and `AppSidebar` on the left.
  * Provides flex layout with fluid height (`calc(100vh - 52px)`).
* **[`AppSidebar.tsx`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/components/layout/AppSidebar.tsx)**:
  * 4 structured navigation sections:
    1. **`OPERATIONS`**: Office Canvas (`/`), Live Flow (`/flow`), Agents Roster (`/agents`).
    2. **`TOOLS & PLUGINS`**: Plugins Hub (`/skills`), MCP Hub (`/mcp`), Tasks Queue (`/tasks`).
    3. **`WORKSPACE & DATA`**: Projects (`/projects`), Schedule & Calendar (`/calendar`), System Metrics (`/dashboard`).
    4. **`ORGANIZATION & GOVERNANCE`**: Org & Teams (`/organization`).
  * Responsive collapse/expand transition (68px ↔ 230px).
  * Color-coded status badges (`LIVE` in green, `MCP` in cyan, `ORG` in purple).
* **[`OfficeTopBar.tsx`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/components/layout/OfficeTopBar.tsx)**:
  * Top header bar with real-time digital clock (`hh:mm:ss a`).
  * Clickable organization badge with building icon, triggering `OrgHierarchyModal`.
  * Multi-department switcher dropdown (`Select`) bound to `activeDepartmentId` in `AuthContext`.
  * User profile chip with role tag (`admin`, `lead`, `member`) and popconfirm logout button.

### 2.2 `robotic/` - Specialized Platform Design System
* **[`ModelSelector.tsx`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/components/robotic/ModelSelector.tsx)**:
  * AI model dropdown component combining static catalog (`src/constants/models.ts`) and live backend models (`getAvailableModels()`).
  * Groups models by provider: *System Default*, *Anthropic Claude*, *NVIDIA NIM*.
  * Displays tier badges (`Executive`, `Architect`, `Coding`, `Fast Worker`), context window size (`200K`, `128K`), and descriptions.
* **[`DepartmentSelect.tsx`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/components/robotic/DepartmentSelect.tsx)**:
  * Dropdown for assigning departments to agents or tasks.
  * Automatically pulls departments from `AuthContext` and supports custom department entry if needed.
* **[`CollapsiblePluginCard.tsx`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/components/robotic/CollapsiblePluginCard.tsx)**:
  * Robotic card component representing a skill/plugin package.
  * Expand/collapse toggle with smooth animated accordion header.
  * Shows source path, git repository URL, and nested skills list with action buttons to inspect or test.

### 2.3 `org/` - Organization & Governance Tabs
* **[`DepartmentsBudgetTab.tsx`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/components/org/DepartmentsBudgetTab.tsx)**:
  * Displays department grid with monthly budget limits, active spend, and assigned department lead.
  * Includes modal for creating new departments with initial budget and description.
* **[`TeamInvitationsTab.tsx`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/components/org/TeamInvitationsTab.tsx)**:
  * Manages department membership roster.
  * Multi-email bulk invitation modal with role assignment (`admin`, `lead`, `member`).
  * Displays pending invitation status and direct invitation link copying.
* **[`OrgUsersTab.tsx`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/components/org/OrgUsersTab.tsx)**:
  * Comprehensive roster of all organization users, roles, email addresses, and associated departments.

### 2.4 `auth/` - Multi-Tenant Authentication Forms
* **[`SignInForm.tsx`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/components/auth/SignInForm.tsx)**:
  * Clean credentials form (email & password) with loading indicator.
* **[`RegisterOrgForm.tsx`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/components/auth/RegisterOrgForm.tsx)**:
  * Full onboarding form for new organizations: Organization Name, Subdomain Slug (auto-slugified), Admin Name, Admin Email, and Admin Password.
* **[`AcceptInviteForm.tsx`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/components/auth/AcceptInviteForm.tsx)**:
  * User onboarding form for accepting email invites: Invitation Token, Full Name, and Password setup.

### 2.5 `workflows/` - Workflow Builder & DAG Canvas
* **[`CreateWorkflowModal.tsx`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/components/workflows/CreateWorkflowModal.tsx)**:
  * 4-tab workflow builder modal:
    1. **Basics**: Name, description, department scope, and optional cron expression.
    2. **MCP Scope & Channel Bindings**:
       * Selectable MCP connectors and tools.
       * Searchable multi-channel `<Select />` filtering across configured `allowed_channels` arrays (Slack channels, Telegram chats).
       * Searchable GitHub/GitLab repository `<Select />` populated both from connector configuration (`allowed_repos`, `default_repo`) and live repository discovery (`discoverMCPResources`).
    3. **Visual DAG Builder**: Step builder with agent assignment, skill execution, and dependency linking. Deleting a step (`handleDeleteStepByKey`) automatically cleans up and bridges `depends_on` references in downstream steps.
    4. **Live YAML Playbook**: Bidirectional synchronization between visual DAG state and raw YAML definition (`definition_yaml`).
* **[`WorkflowCanvasGraph.tsx`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/components/workflows/WorkflowCanvasGraph.tsx)**:
  * Interactive DAG workflow diagram showing execution nodes, triggers, channel connectors, and directed dependency edges.
  * Supports `onDeleteStep?: (stepKey: string) => void` allowing users to delete a step directly from its node card on the canvas or from the Step Details inspector modal.

### 2.6 `office/` - Spatial Simulation & Workstations
* **[`AgentsOfficeV3Canvas.tsx`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/components/office/AgentsOfficeV3Canvas.tsx)**:
  * High-fidelity 2.5D isometric office workspace with zoom/pan controls.
  * Features central AI brain core surrounded by department hubs (Engineering, Operations, Marketing, Executive).
  * Animated agent workstations with live glowing status dots indicating idle, working, or waiting states.
* **[`PixelOfficeCanvas.tsx`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/components/office/PixelOfficeCanvas.tsx)**:
  * Procedural HTML5 canvas pixel art renderer powered by `PixelRenderer.ts`.
  * Animated characters, desk furniture, computer monitors, and status thought bubbles.
* **[`OfficeRightSidebar.tsx`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/components/office/OfficeRightSidebar.tsx)**:
  * Department quick filter bar.
  * Active running agent roster with progress indicators.
  * Real-time activity feed streaming platform events.
  * Task creation and direct dispatch input.
  * *Note: Legacy Shared Memory panel has been completely removed.*
* **[`AgentDeskDrawer.tsx`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/components/office/AgentDeskDrawer.tsx)**:
  * Slide-over drawer showing detailed workstation status when an agent's desk is clicked on the canvas.

### 2.7 Other Component Subsystems
* **`agents/`**:
  * [`CharacterSelector.tsx`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/components/agents/CharacterSelector.tsx): Sprite avatar picker.
  * [`HierarchyEditor.tsx`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/components/agents/HierarchyEditor.tsx): Tree representation of agent manager-subordinate relationships.
  * [`TemplateGallery.tsx`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/components/agents/TemplateGallery.tsx): Ready-to-use agent role templates.
* **`approval/`**:
  * [`ApprovalModal.tsx`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/components/approval/ApprovalModal.tsx): Human-in-the-loop (HITL) prompt dialog for approving sensitive actions.
* **`chat/`**:
  * [`AgentMiniChatDrawer.tsx`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/components/chat/AgentMiniChatDrawer.tsx): Embedded live conversation drawer with session history and prompt dispatch.
* **`common/`**:
  * [`FolderPickerModal.tsx`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/components/common/FolderPickerModal.tsx): Host filesystem directory browser for selecting local workspaces.
  * [`OrgHierarchyModal.tsx`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/components/common/OrgHierarchyModal.tsx): Standalone modal wrapper for organization and team management.
  * [`RuntimeSetupModal.tsx`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/components/common/RuntimeSetupModal.tsx): First-run runtime provider configuration.
* **`memory/`**:
  * [`ProjectSharedMemoryModal.tsx`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/components/memory/ProjectSharedMemoryModal.tsx): Project-level knowledge base and ADR viewer.
* **`scheduler/`**:
  * [`CronBuilderModal.tsx`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/components/scheduler/CronBuilderModal.tsx): Visual cron expression generator and validator.
* **`warroom/`**:
  * [`WarRoomModal.tsx`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/components/warroom/WarRoomModal.tsx): Multi-agent deliberation session modal.

---

## 3. 🔄 Mandatory UI `AGENTS.md` Synchronization Rule

### Component composition and state ownership (2026-10-29 refactor)

`App.tsx` lazy-loads optional route views through `LazyFeatureRoute`. `FeatureErrorBoundary` contains lazy-import and render errors to a feature subtree; `FeatureUnavailable` provides localized retry/navigation guidance. Explicit retry creates a new lazy component and boundary instance. It cannot guarantee recovery from permanent module errors or browser-cached failed modules; sidebar navigation remains outside this boundary. Event-handler and arbitrary asynchronous request failures still require handling inside their owning feature.

`FeatureCapabilityGate` reads the authenticated capability report only for routes with a declared router key. DISABLED/UNAVAILABLE blocks that route; DEGRADED warns; an unavailable report warns and lets the route try its own API calls. Mixed-resource hubs (Office, Live Flow, Agents/templates, Calendar/approvals and MCP/workflows) have no outer router gate so one missing capability cannot hide independent sections. Their resource owners handle scoped read errors. Runtime service state never blocks task-list/configuration pages. STARTING/STOPPING are informational and the actual endpoint remains authoritative. Requests cancel on route/tenant/department change. The report grants no permission and raw reasons/exceptions are not displayed.

`OptionalRuntimeSetup` loads first-run setup under its own error boundary. Setup can now be deferred using close/Escape/Configure runtime later, preserving access to unrelated routes even with no runnable provider. Execution is still governed by backend runtime availability. `AppLayout` uses a viewport-constrained outer shell and independently scrollable route content/sidebar so failure panels do not remove navigation.

Large components are composed from domain state hooks and presentation panels. Public component names and existing props remain compatible; shared prop contracts live in sibling `*Types.ts` modules. Views import hook symbols as types when they only need `ReturnType<typeof hook>`, avoiding a runtime dependency back into their state owner.

* Workflow builder: `CreateWorkflowModal` composes `useWorkflowBuilder` with `WorkflowGeneratorPanel`, `WorkflowDiagramPanel`, `WorkflowStepsPanel` and `WorkflowYamlPanel`. The hook owns loading, all draft state, YAML conversion, skill creation and save actions. `workflowBuilderTypes.ts` owns `WorkflowStep`, `AttachedSkill` and modal props; the legacy modal continues to re-export its two public types. Agent choices now load from the authorized agents API; the former workflowBuilderDefaults.ts static choices were removed. The initial extraction preserves endpoint contracts; the incoming native edit/revision contract is integrated below.
* Workflow graph: `WorkflowCanvasGraph` retains zoom, DAG depth calculation and selected-node state. `WorkflowStepInspector` displays selected-step details and calls the parent's visibility setter. Graph props/step/skill types live in `workflowGraphTypes.ts`; legacy graph exports of step/skill types remain available.
* Agent mini-chat: `useAgentChat` owns session/history loading, polling cleanup, message/task state and approval/send/session actions. `AgentChatContent` renders conversation/task content, while `AgentMiniChatDrawer` renders navigation, session selection and composer. The null-agent guard remains in the public drawer; derived supervisor state tolerates a null agent inside the hook. Prompt presets remain owned by the drawer. Props live in `agentChatTypes.ts`.
* Desk/sidebar: `useAgentDesk` owns forms, resource loading and dispatch/configuration actions; it always returns a model, derives no agent tasks when selection is null, and guards dispatch/save actions without an agent. `AgentDeskDrawer` owns tab presentation and the null-agent rendering guard. `useOfficeSidebar` owns department choices, task filtering and dispatch/deletion actions; `OfficeRightSidebar` renders their controls. Contracts live in `agentDeskTypes.ts` and `officeSidebarTypes.ts` respectively.
* Isometric office: `useOfficeCanvas` owns department/desk projection, agent/task lookup, live mission dispatch and viewport handlers. `OfficeDepartmentPlatforms` renders platform/desk/avatar/HUD content; `OfficeConnectionBeams` renders SVG walkways and particles. `AgentsOfficeV3Canvas` retains viewport containment, central dispatch hub and controls. Shared contracts are in `officeCanvasTypes.ts`. Position formulas, transform order, zoom limits and click callbacks are preserved by relocation.
* War room: `useWarRoom` owns session and detail requests, creation, messages and synthesis state/actions. `WarRoomModal` renders the same session sidebar/forms/detail content; `warRoomTypes.ts` owns its props. Existing endpoint calls and response handling remain unchanged.

These changes were reviewed through source reading only. No tests, build, lint, type checking, startup or live requests were run, so compilation and rendered behavior are not established by this refactor record.

> [!IMPORTANT]
> **Every time any component in `src/components/` is added, modified, or refactored, the developer/agent MUST update this file (`src/components/AGENTS.md`) as part of the same task.**
>
> Checklist on component changes:
> 1. Document any added or changed TypeScript props interfaces.
> 2. Detail any new subcomponents or exported utilities.
> 3. Verify dark theme token adherence (`#0a0d12`, `#161b22`, `#10b981`).
> 4. Ensure no hardcoded Hebrew strings are present (use i18n keys).

## Final review resource behavior
ResourceWarning shows scoped failed reads with a retry action. Workflow builder resources are loaded by useWorkflowResources, with empty configured-resource defaults and shared configuredResourceValues projection. Required unavailable resources block dependent save/generation and remain visible in a warning. Chat history/session/approval/task reads distinguish failures, ignore obsolete completions and use current selected-session refs during polling; history/session failure blocks sending to an uncertain conversation. These changes were reviewed from source only.

## Viewport shell scrolling
AppLayout constrains the outer shell to 100dvh with overflow hidden. The 52px top bar cannot shrink; the remaining body flexes with minHeight=0. Sidebar and Content fill that body. Navigation and right-hand content scroll independently, so long pages cannot scroll the menu off screen. Content uses minWidth=0/minHeight=0 to prevent flex overflow; office content keeps its existing hidden-overflow canvas behavior. Sidebar parent routes remain highlighted for nested routes such as workflow logs.

## Workflow editing and history components
CreateWorkflowModal accepts optional `workflow?: PlatformWorkflow | null`. Edit mode hydrates existing name/description/schedule/webhook settings, steps, skills, MCP grants and channel binding, opens the builder tab, and submits updateWorkflow with expected_revision and an optional change note. It preserves unknown root/step fields and metadata when roundtripping YAML, uses stable IDs and excludes connector-discovery defaults from overwriting edit state. Flow dependencies are reflected in visual steps and removed edges are reconciled. Conversion requests are sequenced to prevent older responses replacing newer edits; saving is disabled during conversion or invalid visual definitions. Dirty raw YAML must be applied before switching tabs. Missing/legacy step aliases are normalized for the builder. Creation remains supported by the same component.
WorkflowHistoryDrawer displays newest-first saved revisions, actor/time/summary, changed-field tags, per-field before/after values and full snapshots. It loads 50 revisions per page with an older-revisions action and handles scoped errors/retries. Legacy baselines explicitly indicate that earlier changes were not tracked. It provides inspection, not one-click restore.

The merged edit contract is implemented inside the extracted `useWorkflowBuilder` rather than restoring the monolithic component. `WorkflowDiagramPanel` supplies `handleDeleteStepByKey` to the graph; node/inspector deletion callbacks accept `(stepKey: string) => void | Promise<void>`. `workflowBuilderTypes.ts` owns the optional workflow prop. Resource discovery skips MCP/channel/repository defaults in edit mode and preserves configured GitHub/GitLab/local Git sources plus live discovery. Raw YAML editing invalidates older visual conversion responses. New drafts start with empty configured-resource defaults; their YAML refreshes after resource loading. History reads use request generations so an older workflow response cannot replace another workflow's history.

## Workflow Assistant removal (2026-10-31)
AppSidebar Operations no longer links to `/workflow-assistant` and OfficeTopBar no longer registers that route. Workflow creation and AI generation remain inside the dedicated `/workflows` hub (`CreateWorkflowModal`).

## Direct API provider & model selection controls (2026-10-31)
`RuntimeSetupModal` presents Direct HTTP API providers (`NVIDIA NIM`, `Anthropic`, `OpenAI`, `OpenRouter`) without the legacy CLI toggle. Operators can select the primary API provider, toggle additional enabled providers (`enabled_providers`), enter or override provider API keys (`Input.Password`), and choose the default model per provider from a searchable `<Select>` populated with that provider's catalog (`provider.config.models`). Saving dispatches `platform:runtime-changed`, and `ModelSelector` listens for `platform:runtime-changed` to reload `/api/v1/models/` so model dropdowns across the platform always reflect the configured provider(s).

## New WorkflowChatModal and hook
WorkflowChatModal({onClose,onCreated}) is mounted by Workflows while open. It offers example prompts, a plain chat textarea (Ctrl/Cmd+Enter sends), configured-model label, current department selector, a simple vertical step preview and explicit creation. Resource details are collapsed by default and show exact allowed repo/channel/tool IDs. No fabricated defaults are inserted. The preview's ready/errors and authoritative draft job ID come from the server. It saves inactive and shows a success message; onCreated refreshes Workflows.
useWorkflowChat owns context reload/cancellation, private job polling (1.5s; transient failures retry after4s), create/stop, stable request IDs on retried submissions, and listener cleanup. The department is fixed during a conversation; Start over clears in-memory chat before switching. Runtime settings changes refresh metadata, not the submitted job selection. Closing an active chat requests cancellation; failed cancellation keeps the window open. Conversation/resource data is not browser-persisted. New typed DTOs are in types/workflowChat.ts; requests use the shared services facade.

Chat reconnect correction: useWorkflowChat separates transient connection errors from action/model errors, clears connection errors after successful reads, and reports network/timeout/HTTP/422 details instead of a generic banner. workflowChat URL query IDs recover authorized stored messages/result after refresh. Sending is blocked while an unresolved recovery is pending; Retry reconnects, and Close remains available. The model label uses the submitted job model when a job exists.

WorkflowChatModal's resource list adds Available/Unavailable status from connectors[].execution_supported. A connected integration without a supported granted execution tool is shown unavailable; this does not alter credentials or grants.

Workflow destination selectors now use channel_labels for option labels and retain exact IDs as option values. useWorkflowResources exposes getChannelLabel(provider,id); builder persists channel_name independently of channel_id. Diagram nodes and final publish caption prefer channel_name. Workflow chat previews/resource lists resolve labels by connector_id+channel_id from the authorized catalog. Unknown labels fall back to IDs. Delivery payloads and governance scopes never resolve labels as identifiers.

WorkflowChatModal previews equipped skill names per step and lists organization plugin skills in the resource panel. It preserves exact skills IDs through proposal/confirmed creation.

WorkflowStepsPanel replaces Connected Skills/Step Skills with one Workflow Skills
section, describing inheritance and direct-action exclusion. No per-step selector
remains. workflowSkillSelection.collectWorkflowSkills deduplicates root+legacy
step selections for saved definitions, generation and YAML import. Builder saves
root AttachedSkill objects and strips per-step skills on visual export, allowing
removal from the shared selection to take effect. Plugin attachments prefer their
canonical path IDs. AI chat previews show one shared skill list, including old
step assignments. Existing raw YAML remains readable without automatic DB edits.

WorkflowChatModal renders planned agent entries using the localized dedicated-runner-on-confirmation label. It preserves the reserved ID in authoring payloads; backend creation replaces it with the real runner ID.

Workflow manual agent selection uses getAgents() rather than a static role list.
useWorkflowResources filters to the selected department or org-wide agents and
excludes other workflows' runners; an existing workflow may select its own runner.
A new workflow exposes the explicitly planned __workflow_runner__ option. Default
new steps select that option, not invented role IDs. Refresh clears stale options;
loading failure blocks saving via the existing resource error path, with no fake
agent fallback. Changing department/workflow reloads the source. No live checks.

## Workflow settings drawer
`workflows/WorkflowSettingsDrawer.tsx` (opened from the Workflows row **Settings** action) loads GET `/api/v1/workflows/{id}/settings` and edits three settings: **Model** (`WorkflowModelSelect.tsx`: Platform default, tiers from `getModelTiers()`, catalog models from `getAvailableModels()`; "default"/null both mean platform default and save as `model: null`; a saved value absent from the catalog stays selectable as "Saved value"), **Machine size** (Segmented small/medium/large with server `machine_sizes` cpus/memory/pids; applies only to repository-sandbox steps) and **Network access** (tags Select of exact hostnames, normalized like the server, max `max_allowed_hosts`; empty = no network). Save sends `expected_revision` from the last load. 409 keeps the edited values, disables Save and offers **Reload latest**; 400/422/403 show the server detail. A `settings_error` renders a warning and allows saving the shown defaults to repair. `can_manage=false` renders everything read-only with the org-admin/department-manager explanation.

`workflows/WorkflowSecretsSection.tsx` lists secret metadata (name, Encrypted/External tag, ARN or `••••••`, updated_at) with Replace (re-PUT same name) and Delete (Popconfirm), plus an add form (name, Encrypted value via `Input.Password` or External AWS Secrets Manager ARN). Values are write-only: held only in the antd form store while typing, cleared on every submit (success or failure), never put in React state, logs or browser storage, and the input carries new-password/password-manager ignore hints. `workflowSettingsRules.ts` mirrors server rules (secret name regex, reserved names, `PLATFORM_*`, 32768-byte value limit, ARN pattern, hostname regex) for early feedback only; the server stays authoritative. Its `describeApiFailure` shows only `msg` text from FastAPI 422 bodies because their `input` field can echo a submitted secret. Copy comes from `i18n/workflowSettings.ts`. No build/type check/runtime verification was run.

### StepEventTimeline (`workflows/StepEventTimeline.tsx`)
Renders persisted runtime events (`Array<Record<string, unknown>>`) as compact rows: local time, kind tag and a one-line summary from `describeEvent`. Kinds are the exported string enum `EventKind`, and `describeEvent` switches over it exhaustively (a `never` check), so a new kind fails type checking until it has a branch. Unrecognized runtime types map to `EventKind.Unknown` but keep their original label. That function covers stderr/raw content, error.message, result text plus reported cost, direct tool_use/tool_result, CLI assistant/user message parts (text, tool_use, tool_result), system session IDs and end_of_output. Unknown shapes fall back to clipped JSON. Each row toggles full text (More) or the raw event (JSON). Event content is rendered as React text, never HTML. Used by `pages/WorkflowLogs.tsx`.

## Reasoning runtime events (2026-11-01)
StepEventTimeline recognizes reasoning_summary with a separate geekblue Reasoning summary label, preview, full text expansion and JSON control. status=not_returned explains missing provider-visible reasoning. Existing authorized Workflow Logs data and export apply; no component API/route changed. Events arrive per completed response, not token-by-token. No build/typecheck/runtime checks executed.


StepEventTimeline recognizes usage events as Usage & cost: per-call tokens, price/source, run total and cumulative session total with full-text expansion. Result rows use cost_summary when present. Unknown price remains explicit, and known zero remains visible. Existing reasoning/tool chronological ordering is retained. No runtime checks performed.

## OfficeTopBar route indicator & runtime/org header items removal (2026-11-01)
`layout/OfficeTopBar.tsx` removes the `routeTitles` dictionary and center "Current View Indicator" badge (`LIVE FLOW`, `AGENTS ROSTER`, etc.), as well as the header `Runtime settings` button and the organization badge right after it. Left section retains the menu collapse toggle, brand link, and `ACTIVE PLATFORM` badge; right section retains the department selector, user chip, logout button, and digital clock.
`common/RuntimeSettingsPanel.tsx` provides an inline card component for configuring Direct HTTP API providers, API keys, enabled providers, and default models, mounted on `pages/SettingsPage.tsx` (`/settings`, added to `layout/AppSidebar.tsx` under `ORGANIZATION & GOVERNANCE`) and in the `Runtime settings` tab of `pages/OrganizationPage.tsx`.
`layout/OfficeTopBar.tsx` and `robotic/DepartmentSelect.tsx` resolve `d.id || d.department_id` for option values while displaying `d.name` as the option label, ensuring the initial `activeDepartmentId` matches its dropdown option.


WorkflowChatModal previews each typed workspace as repository plus read-files or code-changes/draft-PR badge. Resource catalog shows workspace_operations separately from connector tools; workspace-only capability contributes to availability. EN/HE labels live in workflowChat.ts. No permissions are changed by preview. No build/typecheck performed.


## Visual repository workspace authoring (2026-11-01)
WorkflowRepositoryFields is mounted once per step by WorkflowStepsPanel. It selects connector tools, read workspace, or write workspace with required draft-PR outcome; repository choices come only from the current department-authorized AI context catalog. It edits connector_id, repository, ref and pr_title inside existing step.params, clearing conflicting tool/channel scopes only on an explicit mode change. Workspace steps disable the connector-tools selector. Write mode requires catalog clone_repository and open_pull_request grants. This UI never changes grants or executes anything. WorkflowStep.params is now typed while retaining unknown extension fields. useWorkflowBuilder includes workspace connector IDs in root mcp_servers and preserves native params through visual/YAML round trips. useWorkflowResources loads one department context shared by all step fields, with stale-response disposal and independent catalog errors; there are no per-step network requests. Existing permission checks remain authoritative at runtime.
Both visual fields and AI preview show workspace_readiness errors as configuration warnings. Draft creation remains separate from execution. New labels are EN/HE in workflowChat.ts. No tests/build/typecheck/startup performed.


The existing Channel Binding → Notification Mode selector now offers Start/each step/completion, Start/completion, Completion only (success/failure), and None, retaining readable legacy modes. WorkflowChatModal previews the configured cadence alongside its channel instead of rendering progress updates as steps. No new settings page or notification stages. No build/typecheck performed.


Notification Mode now shows exactly four friendly options: Every step, Start and finish, Finish only, Off. Legacy final-only values display as Finish only without changing persisted semantics merely by viewing the form; selecting a mode uses its canonical value. Legacy entries are no longer offered in the dropdown. No tests/build/typecheck performed.

## Organization runtime setup
common/RuntimeSetupModal uses organization-specific runtime responses, reloads on organization change and offers explicit confirmation to revoke a stored provider key. Save/revoke/input controls are disabled for non-admins; backend authorization remains authoritative. Typed keys clear after submit (success/failure), cancel/close and organization change. No keys are returned or persisted in browser storage. EN/HE copy explains organization ownership and no server-global fallback. No build/typecheck/UI execution performed.

## Workflow execution engine selection
WorkflowBackendSelect.tsx is a focused settings control using server execution_backends descriptors. Pending engines are disabled; saved pending values remain visible with a blocking warning and explicit Direct API repair choice. WorkflowSettingsDrawer includes execution_backend in baseline/dirty comparison/save (legacy absent -> direct_api), preserving expected_revision behavior. Step-specific overrides are currently YAML params only. StepEventTimeline adds execution_backend / Execution engine rows with backend+transport. No CLI execution is advertised or enabled. No build/typecheck/render verification.

WorkflowBackendSelect now distinguishes implemented source support from configured deployment status. SDK options require configured!=false; saved unsupported/unconfigured selections remain visible with a warning. UI describes Claude as read-only repository support, not generic CLI/shell/PR execution. No build/typecheck/render verification.

Runtime setup automatic prompts wait for authenticated organization/user context and are shown at most once per user/organization per browser tab session (sessionStorage contains only the shown marker). Explicit Configure runtime still opens the modal. Missing organization keys remain execution-blocking; dismissal grants no credentials. No runtime verification performed.

StepEventTimeline recognizes completion_validation with a warning label, validation code, attempt, message and expandable redacted preview. Full diagnostic metadata remains accessible through the existing JSON toggle; no new request or log authorization boundary. No build/typecheck/render verification.

## Model filter type narrowing
WorkflowModelSelect filterOption checks for a value property before reading it because provider groups carry only label/options. Both group labels and leaf labels/IDs remain searchable. No any cast or disabled type check.
