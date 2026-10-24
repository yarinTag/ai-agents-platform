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

> [!IMPORTANT]
> **Every time any component in `src/components/` is added, modified, or refactored, the developer/agent MUST update this file (`src/components/AGENTS.md`) as part of the same task.**
>
> Checklist on component changes:
> 1. Document any added or changed TypeScript props interfaces.
> 2. Detail any new subcomponents or exported utilities.
> 3. Verify dark theme token adherence (`#0a0d12`, `#161b22`, `#10b981`).
> 4. Ensure no hardcoded Hebrew strings are present (use i18n keys).

## Viewport shell scrolling
AppLayout constrains the outer shell to 100dvh with overflow hidden. The 52px top bar cannot shrink; the remaining body flexes with minHeight=0. Sidebar and Content fill that body. Navigation and right-hand content scroll independently, so long pages cannot scroll the menu off screen. Content uses minWidth=0/minHeight=0 to prevent flex overflow; office content keeps its existing hidden-overflow canvas behavior. Sidebar parent routes remain highlighted for nested routes such as workflow logs.

## Workflow editing and history components
CreateWorkflowModal accepts optional `workflow?: PlatformWorkflow | null`. Edit mode hydrates existing name/description/schedule/webhook settings, steps, skills, MCP grants and channel binding, opens the builder tab, and submits updateWorkflow with expected_revision and an optional change note. It preserves unknown root/step fields and metadata when roundtripping YAML, uses stable IDs and excludes connector-discovery defaults from overwriting edit state. Flow dependencies are reflected in visual steps and removed edges are reconciled. Conversion requests are sequenced to prevent older responses replacing newer edits; saving is disabled during conversion or invalid visual definitions. Dirty raw YAML must be applied before switching tabs. Missing/legacy step aliases are normalized for the builder. Creation remains supported by the same component.
WorkflowHistoryDrawer displays newest-first saved revisions, actor/time/summary, changed-field tags, per-field before/after values and full snapshots. It loads 50 revisions per page with an older-revisions action and handles scoped errors/retries. Legacy baselines explicitly indicate that earlier changes were not tracked. It provides inspection, not one-click restore.
