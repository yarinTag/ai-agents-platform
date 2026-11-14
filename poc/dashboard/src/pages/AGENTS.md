# AGENTS.md - Pages & Application Routes

## 1. Overview & Directory Mission
The `src/pages/` directory contains top-level page components mounted by React Router in [`src/App.tsx`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/App.tsx). Each page coordinates state, calls typed endpoints from [`src/services/api.ts`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/services/api.ts), subscribes to real-time events via [`useOfficeEvents`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/hooks/useOfficeEvents.ts), and renders modular components from [`src/components/`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/components/).

---

## 2. Page Catalog & Route Reference

### 2.1 `OfficeView.tsx` (`/office`)
* **Purpose**: Primary mission-control command floor rendering the physical simulation of the AI office.
* **Key Components**:
  * [`AgentsOfficeV3Canvas`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/components/office/AgentsOfficeV3Canvas.tsx): High-fidelity 2.5D/isometric office floor with zoom, pan, department clusters, and agent avatars.
  * [`PixelOfficeCanvas`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/components/office/PixelOfficeCanvas.tsx): Retro HTML5 canvas pixel-art view.
  * [`OfficeRightSidebar`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/components/office/OfficeRightSidebar.tsx): Department quick filter, active agents list, live platform activity stream, and quick task dispatch. Note: Legacy Shared Memory panel has been removed from this sidebar.
  * [`AgentDeskDrawer`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/components/office/AgentDeskDrawer.tsx): Agent workstation drawer displaying status, assigned tasks, and dispatch actions.
  * [`AgentMiniChatDrawer`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/components/chat/AgentMiniChatDrawer.tsx): Direct live conversation drawer with selected agent.
  * [`WarRoomModal`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/components/warroom/WarRoomModal.tsx): Multi-agent deliberation session modal.
* **State & Features**:
  * View mode switcher (`Segmented`): Pixel Art vs Isometric 3D.
  * Filters out `WORKFLOW_AUTOMATION` agents so only physical office agents occupy workstation desks.
  * Live SSE connection badge (`LIVE SSE` vs `RECONNECTING`) and active running task count indicator (`⚡ N ACTIVE`).

### 2.2 `AgentFlow.tsx` (`/flow`)
* **Purpose**: Visual hierarchy and real-time task delegation pipeline.
* **Key Components**:
  * [`AgentFlowDiagram`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/components/flow/AgentFlowDiagram.tsx): SVG DAG visualization of agent reporting relationships and active task delegations.
  * [`AgentDeskDrawer`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/components/office/AgentDeskDrawer.tsx): Workstation details when an agent node is clicked.
* **State & Features**:
  * Consumes `useOfficeEvents` for live state sync.
  * Live SSE activity feed: Ingests `lastEvent` directly into the activity log without polling.
  * Displays event types (`task:created`, `task:completed`, `agent:status`) with color-coded tags and timestamps.

### 2.3 `Agents.tsx` (`/agents`)
* **Purpose**: Full autonomous agent fleet roster, lifecycle management, and prompt configuration.
* **Key Components**:
  * [`ModelSelector`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/components/robotic/ModelSelector.tsx): Curated and discovered model selector with provider grouping and tier badges.
  * [`CharacterSelector`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/components/agents/CharacterSelector.tsx): Visual sprite avatar picker.
  * [`TemplateGallery`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/components/agents/TemplateGallery.tsx): One-click template instantiation for standard roles (Software Architect, Frontend Dev, Security Engineer).
  * [`HierarchyEditor`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/components/agents/HierarchyEditor.tsx): Drag-and-drop or selectable manager-subordinate tree structure.
  * [`FolderPickerModal`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/components/common/FolderPickerModal.tsx): Local computer filesystem directory selector for agent working directory.
  * [`AgentMiniChatDrawer`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/components/chat/AgentMiniChatDrawer.tsx): Quick chat with any agent from the table.
* **State & Features**:
  * Agent CRUD operations with department assignments.
  * Model tier assignment (`executive`, `architect`, `developer`, `worker`).
  * Direct skill assignments via multi-select dropdown.

### 2.4 `Skills.tsx` (`/skills`)
* **Purpose**: Plugins Hub for scanning, discovering, and configuring agent skills and capability packages.
* **Key Components**:
  * [`CollapsiblePluginCard`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/components/robotic/CollapsiblePluginCard.tsx): Robotic card component showing plugin metadata, source path, git repository, and list of included skills.
  * [`FolderPickerModal`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/components/common/FolderPickerModal.tsx): Native directory picker for local plugins directory.
* **State & Features**:
  * Strict `Segmented` toggle between **Local Directory** and **Git Repository** source modes.
  * **Git Repository Selector**: Discovers accessible GitHub/GitLab repositories using configured MCP credentials or manual personal access token.
  * **Zero-Clone In-Memory Scanning**: Backend parses remote repo markdown skills via GitHub tree API without disk cloning.
  * **Clear Path / Clear Repo Support**: Users can clear the local directory or git repository to configure an empty path with 0 skills.
  * Collapsible plugin cards with expand/collapse all controls.
  * Modal for viewing skill implementation code or markdown prompt instructions.

### 2.5 `McpHub.tsx` (`/mcp`)
* **Purpose**: Model Context Protocol (MCP) integrations hub.
* **State & Features**:
  * **Live Repository Discovery**: Fetches public and private GitHub and GitLab repositories using MCP connector tokens.
  * **Multi-Channel Array Configuration**: Configures `allowed_channels` array for Slack channels and Telegram chats.
  * **Department MCP Access Permissions**: Grants or revokes MCP connector tools on a per-department or per-agent basis.
  * Connector installation modal supporting standard providers (`github`, `gitlab`, `slack`, `telegram`, `postgres`, `filesystem`, `brave-search`) and custom stdio/SSE commands.
  * Connector connection tester with real-time tool discovery verification.
  * Note: The legacy Workflow Channels tab has been removed from MCP Hub as workflows and channel bindings are managed in the dedicated `/workflows` hub.

### 2.6 `OrganizationPage.tsx` (`/organization`)
* **Purpose**: Enterprise multi-tenant governance, department hierarchy, budgets, and user access.
* **Key Components**:
  * Top Hero Banner: Organization identity, slug, and hierarchical structure overview.
  * 4 KPI Metric Cards: Total Departments, Team Members, Active Users, and Organization ID.
  * [`DepartmentsBudgetTab`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/components/org/DepartmentsBudgetTab.tsx): Department cards with allocated monthly budgets, lead assignments, and department creation modal.
  * [`TeamInvitationsTab`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/components/org/TeamInvitationsTab.tsx): Department member roster and bulk email invitation modal with role selection.
  * [`OrgUsersTab`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/components/org/OrgUsersTab.tsx): Organization-wide directory of users, roles (`admin`, `lead`, `member`), and department memberships.
* **State & Features**:
  * Scoped to the authenticated user's organization (`AuthContext`).
  * Real-time refresh of organization profile and departments.

### 2.7 `AuthPage.tsx` (`/auth` or unauthenticated root)
* **Purpose**: Multi-tenant authentication and user onboarding portal.
* **Key Components**:
  * [`SignInForm`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/components/auth/SignInForm.tsx): Email and password sign-in.
  * [`RegisterOrgForm`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/components/auth/RegisterOrgForm.tsx): New organization registration with admin credentials, organization name, and subdomain slug.
  * [`AcceptInviteForm`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/components/auth/AcceptInviteForm.tsx): Invitation token redemption and account password activation.
* **State & Features**:
  * Auto-detects `?token=...` or `?invite=...` in URL query parameters to default to the Accept Invitation tab.
  * Clear error alerts for invalid credentials or expired invitation tokens.

### 2.8 `Tasks.tsx` (`/tasks`)
* **Purpose**: Queue of all tasks across the platform with hierarchical execution trees.
* **Key Components**:
  * Task Roster Table: Columns for Title, Agent, Status tag, Priority, Duration, and Action buttons.
  * Task Tree Modal: Displays the hierarchical delegation breakdown (`TaskTreeNode`) showing parent and subtask dependencies.
  * Task Logs Modal: Real-time event log viewer for task execution trace.
  * Delegation Modal: Allows humans to delegate an existing task to another agent.
* **State & Features**:
  * Live status tags (`pending`, `running`, `completed`, `failed`, `waiting_input`, `pending_approval`).
  * Task creation with priority, max steps, and timeout.

### 2.9 `Projects.tsx` (`/projects`)
* **Purpose**: Enterprise workspace and repository project definitions.
* **Key Components**:
  * Project List Table: Path, Git repository, description, and created timestamp.
  * [`FolderPickerModal`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/components/common/FolderPickerModal.tsx): Native directory browser for selecting local codebase repositories.
* **State & Features**:
  * Links physical disk directories to autonomous agents.
  * Project creation and update modals with path validation.

### 2.10 `CalendarView.tsx` (`/calendar`)
* **Purpose**: Automated cron schedule management and recurring routines.
* **Key Components**:
  * Ant Design `Calendar` view with event indicators on scheduled days.
  * Scheduled Jobs Table with toggle switch, last run status, and trigger now button.
  * [`CronBuilderModal`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/components/scheduler/CronBuilderModal.tsx): Interactive cron expression generator and validator.
  * [`ApprovalModal`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/components/approval/ApprovalModal.tsx): Human-in-the-loop pending approval resolver.
* **State & Features**:
  * One-click trigger of scheduled routines (`triggerScheduleNow`).
  * Pending approvals badge showing actionable decisions requiring human intervention.

### 2.11 `Dashboard.tsx` (`/dashboard`)
* **Purpose**: High-level platform health, system metrics, and runtime statistics.
* **Key Components**:
  * System Health Alert banner (`Healthy`, `Degraded`, `Critical`).
  * 4 Statistic Cards: Total Agents, Active Tasks, Connected MCPs, and Total Projects.
  * Quick Launch Action shortcuts linking to Workflows, Agents, and MCP Hub.
* **State & Features**:
  * Fetches `getSystemStats()` and `getSystemHealth()` with error fallbacks.

---

## 3. 🔄 Mandatory UI `AGENTS.md` Synchronization Rule

### Page feature ownership after modular extraction

Routes, endpoint signatures and existing API facade imports are unchanged. The five page shells below own composition and delegate state/effects to page-specific hooks. Presentation helpers receive explicit typed subsets of hook results, rather than creating additional data subscriptions or independent copies of the same state. New helper files are page-local and are not additional router destinations.

| Page | State and application actions | Presentation ownership |
|---|---|---|
| Agents.tsx | useAgentsPage.tsx: auth-derived department choices, agent/skill/model loading, editor state, CRUD and agent groups | agentColumns.tsx creates roster columns; AgentEditor.tsx owns the existing create/edit form and folder picker; shell retains tabs and chat composition |
| Skills.tsx | useSkillsPage.tsx: source configuration, scans, repository discovery, skill CRUD, content loading and collapse state | PluginSourceConfiguration.tsx renders local/Git source selection and token discovery; SkillsCatalogTabs.tsx renders plugin browsing/custom skill registry; shell retains skill/content/folder modals |
| Tasks.tsx | useTasksPage.tsx: one useOfficeEvents subscription, task CRUD, delegation, tree loading, row actions and tree projection | Tasks.tsx retains table and action/detail dialogs; no new polling or streaming client |
| CalendarView.tsx | useCalendarViewPage.tsx: schedule/task/approval loading, existing 10-second refresh and cleanup, schedule actions, date-cell rendering and schedule columns | Shell retains calendar/tabs/date inspection and cron/approval modal composition; calendarDates.ts owns the shared Dayjs relative-time configuration |
| McpHub.tsx | useMcpState.tsx owns auth context, form instances, shared UI state and initial fetch; useMcpConnectorActions.tsx owns connector discovery/configuration/tools/permissions; useMcpWorkflowActions.tsx owns channel bindings and workflow actions; useMcpPage.tsx composes these and derives channels/catalog filtering | McpHubTabs renders Integrations Marketplace (McpMarketplace) and Installed Connectors (McpInstalledConnectors). McpConnectorModal composes McpRepositorySelection, McpSlackSelection and McpTelegramSelection within the same Form. McpCustomConnectorModal, McpToolsDrawer and McpPermissionsModal own existing connector dialogs. mcpProviderIcon.tsx owns provider icon mapping. |

Selected-resource updates, inline editing, notifications, form validation and modal close handlers are preserved by relocation. `resourceLoading.ts` supplies `readResource`, which records read failure independently from successful empty results. `ResourceSection.tsx` renders scoped unavailable/retry states. MCP catalog/connectors/workflows load independently; unavailable permissions disable Access mutations and render an explicit warning. Connector and binding save handlers also guard dialogs left open during a failed refresh. Channel suggestions come only from configured connector arrays, without invented fallback channel names. Calendar schedule/history/approval reads remain independent, with unavailable sections and disabled dependent schedule actions rather than false empty-success states. Skills initial source configuration failure stops scanning and exposes retry; neither manual rescan nor source overrides bypass a missing initial configuration. The custom skills tab remains separate from plugin source/scan availability. Workflow quick-add channel mutation is owned once by `useMcpWorkflowActions.handleQuickAddBindingChannel` and reused by Enter and Add.

Capability readiness and backend service fault isolation are not established by this frontend extraction. No tests, build, lint, type checking or application startup were run for this change under the user's current restriction; source review is the available validation boundary.

> [!IMPORTANT]
> **Every time any page in `src/pages/` is added, modified, or refactored, the developer/agent MUST update this file (`src/pages/AGENTS.md`) as part of the same task.**
>
> Checklist on page changes:
> 1. Document new route paths or query parameters.
> 2. Detail any new modals, drawers, or subcomponents mounted by the page.
> 3. Document state flow changes (new React Context consumption, SSE listeners, or Axios calls).
> 4. Ensure master index in [`poc/dashboard/AGENTS.md`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/AGENTS.md) is updated if page routes or responsibilities are altered.

## Final review shared ownership
MCP channel/repository projections reuse services/mcpResources rather than duplicate provider-specific loops. Scoped ResourceSection errors/retry preserve independent tabs when optional backends are unavailable. Existing routes and component exports remain compatible.


## Workflows Playground
`/workflows` provides a Playground button per workflow. The shared launch modal switches to tool-free mode, accepts only JSON objects, explains model costs and disabled tools/notifications/approvals, and hides production cache controls. It calls executeWorkflowPlayground, opens the execution inspector and execution tab, and shows PLAYGROUND badges. The inspector refreshes authorized execution details every three seconds while open, cancels updates on close/ID changes, and displays persisted per-step input, output, status and cost alongside aggregate metrics. This mode does not emulate tool responses or train model weights.

## Per-workflow logs page
`WorkflowLogs.tsx` mounts at `/workflows/:workflowId/logs`; optional `?execution=<id>` selects a permanent run link. The Workflows table exposes Logs and its inspector links to Full logs. The page loads authorized workflow metadata, latest 200 executions filtered by workflow_id, and selected execution details. It refreshes every five seconds with cleanup on navigation, supports playground/live filters, searches step data, shows run/step errors and timestamps, input/output, costs and up to 500 persisted runtime events per step. Empty logs explain failures before step launch or legacy records. JSON export downloads only the selected authorized execution detail. Errors are displayed inline with Refresh available.

## Office versus workflow activity
OfficeView and AgentFlow call useOfficeEvents('office'); Tasks retains the default all scope. Live Flow requests office-scoped historical recent activity. Shared specialist definitions can be reused by workflows, but those runs and descendants do not affect the Office canvas, office task counters or Live Flow feed. SkillsPage uses the session-memory plugin API cache; manual Scan and Save & Sync force a rescan, while configuration fetch failures stop initial scanning instead of falling back to an unintended source.

## Workflow Edit and History actions
Each workflow row exposes Edit and History. Edit mounts a fresh shared builder instance with the selected workflow, updating the same record rather than creating another. Close/success clears edit context; new-workflow actions explicitly select create mode. History opens WorkflowHistoryDrawer, separate from the execution Logs view. Canvas deletions pass expected_revision and a change summary and reconcile flow edges, so they are also audited configuration revisions. Existing execution IDs/logs remain intact.

## Workflow Assistant model generation
WorkflowAssistant.tsx (/workflow-assistant, optional ?generation=id) loads current departments/catalog/drafts, selects a planning profile/model, submits bounded user/assistant conversations, polls active jobs every 1.5 seconds (5-second retry on transient reads), and allows cancellation. It renders clarification questions, per-step declared resources/dependencies, current validation and JSON. Saving calls the generation save-draft endpoint with explicit save_blocked on invalid proposals. Source revisions come from the loaded draft or saved generation snapshot, never silently from a newer list entry; stale drafts require reload. Permissions/resources are refreshed on terminal jobs/save. Conversation state stays in memory; known job links recover from the server.

Draft history is loaded through getAssistantDraftHistory (GET /drafts/{id}/revisions) and displayed as read-only revision snapshots in the proposal panel.

## Model-only YAML authoring and internal MCP
WorkflowAssistant.tsx now sends model_id/provider_id, shows configured-runtime model options independent of department agents, loads /workflow-schema, previews/downloads workflow-draft.yaml and calls /validate-yaml for current checks. MCP call audit badges come from authenticated job data. New history snapshots prefer definition_yaml with legacy JSON fallback. Legacy chats with provider_id=legacy remain viewable without selecting a former planning agent; a current model must be selected for new generation.


## Incoming master integration ownership

`Workflows.tsx` mounts at `/workflows` and now delegates loading, polling, execution, optimistic revision writes and modal state to `useWorkflowsPage.tsx`. `workflowColumns.tsx` owns saved-workflow actions (Edit/History/Run/Playground/Logs/Canvas/Definition/Delete); `workflowExecutionColumns.tsx` owns execution summaries; `WorkflowExecutionDrawer.tsx` owns authorized selected-run/step inspection. Existing 10-second list and 3-second detail refresh/cleanup are preserved. Workflow Logs and Workflow Assistant remain separate routes, retaining model-only generation, permission-aware drafts and non-executable YAML semantics.

`services/workflowDefinitions.ts:removeWorkflowStep` owns DAG-stage removal/dependency rewiring and flow-edge reconciliation for both workflow and MCP canvases. Both update the current workflow using expected_revision and change_summary; optimistic conflicts retain displayed state and show the error. The MCP canvas no longer calls format conversion with an unsupported positional signature.

Tasks uses `useTaskQueue.ts` and `TaskQueuePanel.tsx` for broker metrics, independent 5-second refresh, DLQ inspection/retry and explicit unavailable states. Task dispatch preserves upstream use_queue=true and priority (1–10) while all-scope task history remains separate from broker availability. Agents Fleet retains office-agent filtering; workflow agents are managed through Workflows rather than a duplicate fleet tab. Plugin manual Scan/Save & Sync pass forceRefresh=true through the cached API, and source-config read failure still prevents a scan.

No tests, build, lint, type checking, import execution or application startup were run during merge resolution. Source/API contract review does not establish live integration correctness.

## MCP page render correction (2026-10-30)
McpHubPage reads resourceErrors from useMcpPage before using connectors availability to disable Add Custom MCP. The resource state remains owned by useMcpState; the page must not reference an undeclared local. This fixes the reported resourceErrors ReferenceError. No tests/build were run.

## MCP Hub workflow tab removal and GitHub token discovery (2026-10-31)
McpHubTabs removes the duplicate Workflow Channels tab (`McpWorkflowChannels`) and McpHubPage removes the workflow binding/canvas/builder modals, as workflow management lives under `/workflows`. In `useMcpConnectorActions.handleFetchResources`, manual token repository fetches (`isManual=true`) replace `discoveredResources` strictly with the repositories returned for the token and update `selectedResources` to valid repositories from that token instead of merging stale or default repository names.

## Workflow Assistant removal (2026-10-31)
The `/workflow-assistant` route has been removed from `src/App.tsx` and the sidebar navigation. Workflow creation and AI playbook generation are consolidated under `/workflows` (`Workflows.tsx` and `CreateWorkflowModal.tsx`).

## New friendly AI creation window
Workflows.tsx owns a chatOpen flag and mounts WorkflowChatModal from Create with AI. Successful inactive creation reloads the existing workflow list; manual creation, editing, logs and history remain separate existing actions. This new window replaces no removed route and restores none of the deleted assistant files.

Workflows initializes the AI modal from ?workflowChat=<private-request-id> to recover an existing conversation after reload. Explicit close removes only this query parameter; other route query parameters are preserved.

The workflow Run modal exposes Run location: Run on this server (manual UI default) or Send to message queue. The former sends use_queue=false&background=true and returns promptly without the broker; the latter sends use_queue=true. Playground retains its separate tool-free path. Structured CAPABILITY_UNAVAILABLE errors now render a useful queue-specific or capability-specific message instead of passing an object to message.error. No automatic fallback/retry occurs.

MCP connector actions now pass editingConnector.id to resource discovery. Telegram displays actual recent bot chats or valid configured IDs and removes phantom defaults/implicit selection; empty discovery explains real numeric IDs/@usernames and webhook limitations. Slack displays only returned configured channel IDs without inserting #general/#dev-team defaults. Selection/save remains explicit. Existing invalid aliases are not silently mapped to other recipients.

WorkflowExecutionDrawer and WorkflowLogs render notification_error as a separate warning from run failure. This distinguishes a completed GitHub summary from a blocked optional Telegram/Slack delivery.

Telegram connector selection exposes **Find chat IDs**, showing discovered titles beside exact IDs without automatically selecting or granting destinations. Telegram/Slack destination saving rejects display-name aliases; no suggested channel defaults are fabricated.

Installed connectors expose Send test message beside each saved Telegram/Slack destination; Check connection remains separate. Tests pass connector_id and display safe backend errors. Telegram Find chats lists observed names and keeps selection values as exact IDs; save persists configuration.channel_labels (ID-to-name display metadata) alongside allowed_channels. Labels never authorize or resolve delivery. Configured tags retain names after reload and show IDs on hover.

Connector save correction: useMcpConnectorActions explicitly includes/destructures discoveredResources from useMcpState before deriving configuration.channel_labels. Omitting this caused a ReferenceError before Telegram/Slack save HTTP requests. Static source review only; runtime verification remains unauthorized.

Telegram discovered-chat selection displays names with canonical IDs available on hover; checkbox values remain the discovered IDs. Installed connector tags use persisted channel_labels. No arbitrary name-to-destination guessing is introduced.

## Workflow settings action
`useWorkflowsPage` owns `settingsWorkflow`/`setSettingsWorkflow` and exposes `settingsText` (`useWorkflowSettingsText`). `workflowColumns.tsx` adds a **Settings** button next to History on each saved workflow row. `Workflows.tsx` mounts `WorkflowSettingsDrawer` keyed by workflow ID while `settingsWorkflow` is set and calls `loadData()` after a settings save, because saving bumps the workflow revision that Edit and canvas step deletion send as `expected_revision`. Secret writes do not change the revision and do not reload the list. No runtime verification was run.

WorkflowLogs readability: steps render collapsed except FAILED or active ones (defaults reapply per selected execution; polling does not reset manual expansion). Step headers show duration and cost; run/step times use locale formatting with run durations, and run-list errors clamp to two lines with theme danger color. Output precedes the collapsed input. Runtime events render through components/workflows/StepEventTimeline as one summarized line per event, with More (full text) and JSON (raw event) toggles; the events section opens by default only for failed steps. Source review only; no build/typecheck was run.

## WorkflowLogs runs card list & dark-theme polish (2026-11-01)
`WorkflowLogs.tsx` replaces the multi-line Ant Design `<Button block type="primary">` run list items (which caused horizontal flex squishing and full-card green fill) with vertical dark-themed clickable run cards (`role="button"`, keyboard accessible, emerald accent border `#10b981` when selected), a `Segmented` mode filter (`All Runs`, `Live`, `Playground`), status/trigger/deduplication tags with icons, duration/cost/token metadata, and a 4-column execution summary grid with terminal-styled `#0d1117` output/input blocks.

## Settings page & runtime configuration (2026-11-01)
`OrganizationPage.tsx` (`/organization?tab=runtime`) owns the `Runtime settings` tab rendering `RuntimeSettingsPanel` for configuring AI API providers, API keys, enabled providers, and default models. The redundant `SettingsPage.tsx` and sidebar entry have been removed; `/settings` redirects to this tab.


WorkflowLogs now renders a dedicated Model reasoning summaries panel above Step Output inside each expanded step. Available summaries are counted in a geekblue Reasoning (N) badge visible even on collapsed step headers. Existing Runtime Events retains the full chronological trace. Missing-summary events remain visible in the dedicated panel. No route/API changes. Read-only inspection of existing SQLite run records confirmed persisted NVIDIA summaries; no new inference/tests/build/startup performed.

WorkflowLogs displays reasoning_summary events only in the dedicated reasoning panel; Runtime Events filters them out and counts only remaining events. Persisted event records and JSON export retain the complete trace. This supersedes the earlier duplicate chronological display. Source review only; no runtime checks performed.

WorkflowLogs reasoning presentation follows the user preference: reasoning_summary appears once in the chronological Runtime Events timeline alongside tools/results. The separate reasoning panel is removed; Runtime Events defaults open when reasoning events exist (or the step failed). The Reasoning (N) header badge remains for discoverability. This supersedes the earlier panel/filter notes. Persistence and JSON export are unchanged. Source review only; no runtime checks performed.


WorkflowLogs, WorkflowExecutionDrawer and workflowExecutionColumns use services/workflowCosts.formatCost for all workflow/run/step prices, including free and unavailable values. Logs and inspection show cumulative session cost from step.session_cost_summary; usage events show per-call pricing. All run list cost rows are visible even at zero; historical missing pricing is unavailable rather than free. No routes, new requests or schema changes. No build/typecheck performed.

## Telegram selectable-tag tooltip
McpTelegramSelection renders each discovered chat in a keyed native span with title=canonical chat ID, containing the controlled Ant Design CheckableTag. The tag keeps selection handlers and styles; unsupported title props are not passed to it.

## Organization & Department Workflows Canvas & Skills Canvas Diagrams (2026-11-03)
`OrganizationPage.tsx` (`/organization`) loads organization workflows via `getWorkflows()` alongside `getDepartments()` and `getOrganizationUsers()` and mounts `OrgWorkflowsCanvasTab` under the **Workflows Canvas** (`key: 'workflows'`) tab, powered by the generic `ConnectionCanvasDiagram` (`src/components/common/ConnectionCanvas/`). `SkillsCatalogTabs.tsx` (`/skills`) mounts `PluginsConnectionCanvas` exclusively under the top-level **Skills & Plugins Canvas** (`key: 'canvas'`) tab (with no duplicate canvas toggle inside `Skills Repository Hub`), rendering multi-stage skill flows and inter-skill connections.


## Workflow hub department selection (2026-11-05)
`useWorkflowsPage` reads AuthContext.activeDepartmentId and scopes workflow-list and
execution-history requests with department_id. Null (All Departments) omits the filter;
server tenant/role authorization continues to apply. Organization/user/department changes
immediately hide old rows, clear detail/editor/history/settings/run selections and reload
both lists. A scope key plus request version rejects late previous-scope responses and
superseded polls; unmount invalidates pending list commits. Detail polling and successful
run/canvas updates also ignore previous-scope responses. Open UI is reset on scope changes;
this does not cancel already submitted executions. Counts derive from scoped rows.
No local tests/build/typecheck/browser or server execution performed.


## Permission-aware pages (2026-11-05)
Agent/workflow create/edit/delete, hierarchy/template and schedule configuration require management;
Tasks/workflow runs, triggers, delegation/cancel and chat mutations require operation rights.
Projects/custom skill/template/connector/source configuration and direct integration tests require
organization administration. Inspection/history/logs remain readable in authorized scope. A mixed
manager in a MEMBER department sees read-only controls via usePermissions. Plugin read-only scans
omit source-changing query parameters; non-admins cannot load private repository discovery or edit
source config. QueuePanel explains why broker-wide metrics/DLQ actions are unavailable rather than
polling global endpoints. App supplies a read-only department access view to non-admin Org & Teams
and routes legacy Settings navigation through that same protected organization view. Each feature remounts on scope/role changes. No runtime
checks were performed; exact exceptions/limitations are in docs/access-control-audit.md.

Workflow create and Create with AI entry points and recovery modal are enabled for canRead. Existing editing/deletion/settings and execution controls retain their respective roles. No local runtime verification performed.


WorkflowLogs mounts WorkflowApprovalPanel keyed by execution ID; Telegram links open /workflows/{workflow_id}/logs?execution={execution_id}. Gate reads/polling and role controls remain backend-authorized. WAITING_APPROVAL retains persisted step/run state without blocking a worker.


AI-14 defines proposed page composition and role journeys in docs/design/governance-ux.md; existing /organization non-admin DepartmentAccessPage must not be replaced by an admin-requesting component just to display permissions. Empty context with an authorized header department is a load mismatch, not an instruction to join the department. No page behavior changed in P00.

## AI-17 organization capabilities
OrganizationPage adds capabilities to its tab state and mounts CapabilityGovernancePanel on the existing /organization route. Non-admins retain the router-provided DepartmentAccessPage, which embeds the same panel without org-user/runtime/admin data requests. Header selection controls one explicit department. See docs/design/capability-policy-editor.md; no new route/sidebar.


## AI-1 workflow table labels (2026-11-06)
WorkflowsPage passes AuthContext departments and an explicit ORG_ADMIN account-role check to createWorkflowColumns. The Department column, including its header, exists only for organization admins. Department names come from the current roster; missing names fall back to IDs and absent departments remain Global. Channel labels come from already-loaded MCP configuration.channel_labels keyed by channel_id, matching provider and connector_id. Legacy bindings without connector_id resolve only with exactly one provider connector. Missing/blank/ambiguous labels fall back to canonical IDs. Department/channel IDs remain in tooltips. Names are presentation metadata, never delivery destinations or grants. No new API requests or backend authorization changes. Static source/diff review only; no local tests/build/typecheck/browser/startup performed.


## AI-2 compact table actions (2026-11-06)
`pages/RowActionMenu.tsx` provides a click-triggered Ant Design Dropdown with a compact ellipsis button, row-specific accessible label/title and typed MenuProps items. Workflows keeps Run visible; Playground, Edit, History, Settings, Logs (router link), Canvas and YAML/JSON Definition move into its menu. Agents keeps Chat with Edit/Delete in its menu; Projects uses Edit/Delete menu; Tasks keeps Logs with manager-only Delegate, Execution tree, running-only Cancel and Delete in its menu. Workflow Executions already has a single Inspect primary action and retains it. Actions columns have compact widths (150px with primary/menu, 90px for menu-only or Inspect). Existing role disables and conditional availability remain intact; Settings remains readable. Destructive items are danger-styled below a divider and require Modal.confirm before calling existing handlers. Workflow deletion retains its existing warning. Names/IDs, backend requests and department scopes are unchanged. AI-1 friendly labels and admin-only Department column remain intact. Source/diff review only; no local tests/build/lint/typecheck/browser/server execution performed under current restrictions.


## AI-4 calendar execution navigation (2026-11-06)
Calendar task cells link to /tasks?taskId=<encoded task ID>; useTasksPage reads that parameter through the authorized getTask API and opens the existing output/error/event console. Closing removes only taskId; stale/unmounted detail responses are ignored and failures show an error. CalendarRun renders status, actual start/end and completed duration, task console links and workflow logs links using canonical workflow/execution IDs. Workflow trigger_type is displayed, with CRON labeled Scheduled (cron); task trigger provenance is unavailable unless matched to a loaded workflow run, never inferred as manual. useCalendarViewPage independently loads up to 200 recent authorized workflow executions with the active department filter, existing polling/request-generation guards and a separate resource error. Cells and date inspection include workflow runs, including runs without tasks; the date modal discloses the 200-run history bound. Activity groups by started_at with created_at fallback; missing actual start/end remains unavailable. No backend/schema/grant changes. Static review only; local tests/build/typecheck/browser/startup remain unauthorized.


## AI-5 consolidated runtime settings navigation (2026-11-07)
The authenticated `/settings` route uses React Router Navigate with replace to `/organization?tab=runtime`, removing the legacy history entry. SettingsPage and its lazy import/sidebar item are removed. OrganizationPage validates `tab` against departments/workflows/team/users/runtime/capabilities, defaults missing/unknown values to departments, and updates only tab while preserving other query parameters. Browser back/forward and direct links select the corresponding tab. RuntimeSettingsPanel remains in the organization runtime tab; the existing non-admin DepartmentAccessPage route and capability/read guards remain authoritative, so redirects grant no admin access. No backend/provider behavior changes. Static source/diff review only; no local tests/build/typecheck/browser/startup under current runtime restrictions.


## Organization department directory scope (2026-11-07)
getDepartments(organization_id?) explicitly disables X-Department-ID using Axios's false header sentinel. httpClient respects that sentinel instead of injecting the active department; all other requests retain existing header selection. GET /api/v1/departments still applies current backend organization and membership authorization: admins see their full organization directory, non-admins only authorized memberships. Org & Teams Departments & Budgets counts/table and team selectors therefore no longer collapse to the selected header department. No global request-scope mutation, backend permission bypass or cross-tenant access. Static review/diff check only; runtime verification remains unauthorized.


## Explicit department member request scope (2026-11-07)
getDepartmentMembers, bulkInviteDepartmentMembers and removeDepartmentMember send X-Department-ID equal to their target deptId and encode path IDs. httpClient supplies the global selection only when the request has no explicit X-Department-ID header, preserving both a target scope and the false directory sentinel. Current server membership/tenant/admin checks remain unchanged. OrganizationPage clears old members before loading and ignores superseded/unmounted member responses/errors/loading updates. This prevents global header selection from rejecting Org & Teams operations on another authorized department. Static diff review only; no runtime verification performed.


Manage Team navigation uses selectTab('team') with the selected department, matching the URL-owned tab state introduced by AI-5. The removed setActiveTab state setter has no remaining OrganizationPage references. Static reference/diff checks only; no runtime verification performed.

## AI-20 PR scopes and evidence
AI-20: WorkflowLogs and WorkflowExecutionDrawer render step.pr_evidence from authorized execution details, independently of model output and the 500-event timeline bound. Inspection also mounts existing WorkflowApprovalPanel keyed by execution ID, preserving current backend authority. No new route, action endpoint or resource grant. Missing historical receipts remain absent; confirmation is never inferred from workflow completion.

OrganizationPage supports `/organization?tab=channels` and mounts ChannelBindingsPanel for the channel registry.

AI-29 adds the organization-admin Webhook diagnostics tab in MCP Hub. It is scoped to a selected Slack/Telegram connector and unmounts when the operator leaves the tab.

AI-26 OrganizationPage exposes Linked accounts at /organization?tab=identities. Non-admin users reach the same personal/management panel from the existing DepartmentAccessPage shell.

The Workflows header opens the department-scoped Approvals inbox. Execution-derived waiting step keys are passed to the canvas only when the inspected execution belongs to that workflow.

The dashboard welcome and default connector test notification use ConduitCross branding.
Workflow lists and logs load on entry, relevant selection changes, and explicit refresh. Workflow mutations can refresh affected data. Lists, execution details, and logs have no periodic refresh timers.

The Workflows run modal starts with the Advanced execution parameters accordion collapsed for manual runs and expanded for Playground. The JSON field stays registered with the existing run form when collapsed.

The MCP Hub uses McpDepartmentTools for non-admins. It loads the effective catalog for the selected department and displays the connector, capability description, exact resource and separate authoring/execution decisions. Entering a new department clears the prior results. Marketplace, administration dialogs and connection tests mount only in the admin Hub.

The Skills Hub displays the active department’s effective plugin source and inheritance origin. Organization administrators can save a GitHub override or restore inheritance. Dashboard WorkflowMetricsView displays the reliability trend, failure diagnostics and latest failure logs. Workflows accepts ?edit=<id> for an authorized visible workflow and consumes it when opening the existing builder.

Skills Hub allows organization admins to switch between organization defaults and the selected department’s override. Scope changes remount the catalog and editor. Reliability trends display UTC.

Workflow Logs opens approval details from the Run approvals button. Both inboxes use the same pending/history tables, scoped to the execution when opened from logs.
