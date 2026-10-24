# AGENTS.md - Pages & Application Routes

## 1. Overview & Directory Mission
The `src/pages/` directory contains top-level page components mounted by React Router in [`src/App.tsx`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/App.tsx). Each page coordinates state, calls typed endpoints from [`src/services/api.ts`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/services/api.ts), subscribes to real-time events via [`useOfficeEvents`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/hooks/useOfficeEvents.ts), and renders modular components from [`src/components/`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/components/).

---

## 2. Page Catalog & Route Reference

### 2.1 `OfficeView.tsx` (`/`)
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

### 2.5 `Workflows.tsx` (`/workflows`)
* **Purpose**: Dedicated Workflows & Automations Hub for multi-agent DAG pipelines, manual execution, transparent background queue dispatching, and automated run deduplication.
* **Key Components**:
  * [`CreateWorkflowModal`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/components/workflows/CreateWorkflowModal.tsx): Visual and YAML workflow builder with skills and MCP channel bindings.
  * [`WorkflowCanvasGraph`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/components/workflows/WorkflowCanvasGraph.tsx): Interactive DAG canvas graph visualization of workflow step dependencies with direct step deletion (`handleDeleteStepFromCanvas`) that persists updated JSON/YAML definitions via `updateWorkflow`.
  * Execution History Table & Live Queue Inspector: Displays status (`QUEUED`, `RUNNING`, `COMPLETED`, `FAILED`), token consumption, costs, and `⚡ DEDUPLICATED / CACHED` badges.
  * Execution Launch Modal: Supports custom JSON trigger payloads and force re-run deduplication bypass (background queue dispatching operates transparently behind the scenes).
  * Execution Inspection Drawer: Inspects sandbox paths, token accounting, error messages, and input payloads.

### 2.6 `McpHub.tsx` (`/mcp`)
* **Purpose**: Model Context Protocol (MCP) integrations and workflow trigger channels hub.
* **Key Components**:
  * [`CreateWorkflowModal`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/components/workflows/CreateWorkflowModal.tsx): Multi-step workflow builder with channel bindings.
  * [`WorkflowCanvasGraph`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/components/workflows/WorkflowCanvasGraph.tsx): DAG visualization of configured workflow steps.
* **State & Features**:
  * **Live Repository Discovery**: Fetches public and private GitHub and GitLab repositories using MCP connector tokens.
  * **Multi-Channel Array Configuration**: Configures `allowed_channels` array for Slack channels and Telegram chats.
  * **Department MCP Access Permissions**: Grants or revokes MCP connector tools on a per-department or per-agent basis.
  * **Workflow Channel Binding Table & Modals**: Displays active workflows with bound channel provider (Slack/Telegram), trigger event, and target repository.
  * Connector installation modal supporting standard providers (`github`, `gitlab`, `slack`, `telegram`, `postgres`, `filesystem`, `brave-search`) and custom stdio/SSE commands.
  * Connector connection tester with real-time tool discovery verification.

### 2.7 `OrganizationPage.tsx` (`/organization`)
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

### 2.8 `AuthPage.tsx` (`/auth` or unauthenticated root)
* **Purpose**: Multi-tenant authentication and user onboarding portal.
* **Key Components**:
  * [`SignInForm`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/components/auth/SignInForm.tsx): Email and password sign-in.
  * [`RegisterOrgForm`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/components/auth/RegisterOrgForm.tsx): New organization registration with admin credentials, organization name, and subdomain slug.
  * [`AcceptInviteForm`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/components/auth/AcceptInviteForm.tsx): Invitation token redemption and account password activation.
* **State & Features**:
  * Auto-detects `?token=...` or `?invite=...` in URL query parameters to default to the Accept Invitation tab.
  * Clear error alerts for invalid credentials or expired invitation tokens.

### 2.9 `Tasks.tsx` (`/tasks`)
* **Purpose**: Queue of all tasks across the platform with hierarchical execution trees and RabbitMQ distributed worker status.
* **Key Components**:
  * RabbitMQ Status Banner: Live broker connection, queue depths (Urgent, Standard, Background, Workflows), active worker count, and DLQ badge.
  * Task Roster Table: Columns for Title, Agent, Status tag, Priority, Duration, and Action buttons.
  * Dead-Letter Queue (DLQ) Inspector Drawer: Lists isolated failed messages (>3 attempts) with root causes and one-click `Retry Task 🔁` requeuing.
  * Task Tree Modal: Displays the hierarchical delegation breakdown (`TaskTreeNode`) showing parent and subtask dependencies.
  * Task Logs Modal: Real-time event log viewer for task execution trace.
  * Delegation Modal: Allows humans to delegate an existing task to another agent.
* **State & Features**:
  * Live status tags (`pending`, `running`, `completed`, `failed`, `waiting_input`, `pending_approval`).
  * Task creation with RabbitMQ Topic Queue dispatch option and Priority slider (1: Low to 10: Urgent Incident).

### 2.10 `Projects.tsx` (`/projects`)
* **Purpose**: Enterprise workspace and repository project definitions.
* **Key Components**:
  * Project List Table: Path, Git repository, description, and created timestamp.
  * [`FolderPickerModal`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/components/common/FolderPickerModal.tsx): Native directory browser for selecting local codebase repositories.
* **State & Features**:
  * Links physical disk directories to autonomous agents.
  * Project creation and update modals with path validation.

### 2.11 `CalendarView.tsx` (`/calendar`)
* **Purpose**: Automated cron schedule management and recurring routines.
* **Key Components**:
  * Ant Design `Calendar` view with event indicators on scheduled days.
  * Scheduled Jobs Table with toggle switch, last run status, and trigger now button.
  * [`CronBuilderModal`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/components/scheduler/CronBuilderModal.tsx): Interactive cron expression generator and validator.
  * [`ApprovalModal`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/components/approval/ApprovalModal.tsx): Human-in-the-loop pending approval resolver.
* **State & Features**:
  * One-click trigger of scheduled routines (`triggerScheduleNow`).
  * Pending approvals badge showing actionable decisions requiring human intervention.

### 2.12 `Dashboard.tsx` (`/dashboard`)
* **Purpose**: High-level platform health, system metrics, and runtime statistics.
* **Key Components**:
  * System Health Alert banner (`Healthy`, `Degraded`, `Critical`).
  * 4 Statistic Cards: Total Agents, Active Tasks, Connected MCPs, and Total Projects.
  * Quick Launch Action shortcuts linking to Office Canvas, Agents, and MCP Hub.
* **State & Features**:
  * Fetches `getSystemStats()` and `getSystemHealth()` with error fallbacks.

---

## 3. 🔄 Mandatory UI `AGENTS.md` Synchronization Rule

> [!IMPORTANT]
> **Every time any page in `src/pages/` is added, modified, or refactored, the developer/agent MUST update this file (`src/pages/AGENTS.md`) as part of the same task.**
>
> Checklist on page changes:
> 1. Document new route paths or query parameters.
> 2. Detail any new modals, drawers, or subcomponents mounted by the page.
> 3. Document state flow changes (new React Context consumption, SSE listeners, or Axios calls).
> 4. Ensure master index in [`poc/dashboard/AGENTS.md`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/AGENTS.md) is updated if page routes or responsibilities are altered.

## Workflows Playground
`/workflows` provides a Playground button per workflow. The shared launch modal switches to tool-free mode, accepts only JSON objects, explains model costs and disabled tools/notifications/approvals, and hides production cache controls. It calls executeWorkflowPlayground, opens the execution inspector and execution tab, and shows PLAYGROUND badges. The inspector refreshes authorized execution details every three seconds while open, cancels updates on close/ID changes, and displays persisted per-step input, output, status and cost alongside aggregate metrics. This mode does not emulate tool responses or train model weights.

## Per-workflow logs page
`WorkflowLogs.tsx` mounts at `/workflows/:workflowId/logs`; optional `?execution=<id>` selects a permanent run link. The Workflows table exposes Logs and its inspector links to Full logs. The page loads authorized workflow metadata, latest 200 executions filtered by workflow_id, and selected execution details. It refreshes every five seconds with cleanup on navigation, supports playground/live filters, searches step data, shows run/step errors and timestamps, input/output, costs and up to 500 persisted runtime events per step. Empty logs explain failures before step launch or legacy records. JSON export downloads only the selected authorized execution detail. Errors are displayed inline with Refresh available.

## Office versus workflow activity
OfficeView and AgentFlow call useOfficeEvents('office'); Tasks retains the default all scope. Live Flow requests office-scoped historical recent activity. Shared specialist definitions can be reused by workflows, but those runs and descendants do not affect the Office canvas, office task counters or Live Flow feed. SkillsPage uses the session-memory plugin API cache; manual Scan and Save & Sync force a rescan, while configuration fetch failures stop initial scanning instead of falling back to an unintended source.

## Workflow Edit and History actions
Each workflow row exposes Edit and History. Edit mounts a fresh shared builder instance with the selected workflow, updating the same record rather than creating another. Close/success clears edit context; new-workflow actions explicitly select create mode. History opens WorkflowHistoryDrawer, separate from the execution Logs view. Canvas deletions pass expected_revision and a change summary and reconcile flow edges, so they are also audited configuration revisions. Existing execution IDs/logs remain intact.
