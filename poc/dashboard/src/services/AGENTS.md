# AGENTS.md - Networking & Real-Time Event Services

## 1. Overview & Directory Mission
The `src/services/` directory is the single source of truth for all network communication between the React frontend and the FastAPI backend. It contains the central Axios HTTP client with multi-tenant interceptors ([`api.ts`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/services/api.ts)) and the real-time Server-Sent Events client ([`eventStream.ts`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/src/services/eventStream.ts)).

---

## 2. Central HTTP Client (`src/services/api.ts`)

### 2.1 Configuration & Interceptors
* **Base URL**: `http://localhost:8000` (timeout: 10,000ms).
* **Request Interceptor**:
  * Reads `localStorage.getItem('agents_platform_auth_token')`.
  * If present, injects `config.headers.Authorization = 'Bearer ' + token`.
* **Response Interceptor (401 Handling)**:
  * Catches HTTP 401 Unauthorized responses.
  * Exempts public auth endpoints (`/auth/login`, `/auth/org-register`, `/invitations/accept`).
  * For all protected endpoints, purges cached tokens from `localStorage` and emits `window.dispatchEvent(new CustomEvent('auth:unauthorized'))`.

### 2.2 Typed API Method Directory

#### Authentication & Profiles
* `loginOrganizationUser(data: LoginDto)`: POST `/api/v1/auth/login`
* `registerOrganization(data: RegisterOrgDto)`: POST `/api/v1/auth/org-register`
* `acceptOrgInvitation(data: AcceptInviteDto)`: POST `/api/v1/invitations/accept`
* `getCurrentUserProfile()`: GET `/api/v1/auth/me`

#### Organizations & Departments
* `getDepartments(organization_id?: string)`: GET `/api/v1/departments`
* `createDepartment(data: CreateDepartmentDto)`: POST `/api/v1/departments`
* `getDepartmentMembers(deptId: string)`: GET `/api/v1/departments/{deptId}/members`
* `bulkInviteDepartmentMembers(deptId: string, data: BulkInviteDto)`: POST `/api/v1/departments/{deptId}/members/bulk-invite`
* `removeDepartmentMember(deptId: string, userId: string)`: DELETE `/api/v1/departments/{deptId}/members/{userId}`
* `getOrganizationUsers(orgId: string)`: GET `/api/v1/organizations/{orgId}/users`

#### Autonomous Agents & Roster
* `getAgents()`: GET `/api/v1/agents/`
* `getAgent(id: string)`: GET `/api/v1/agents/{id}/`
* `createAgent(data: AgentCreateDto)`: POST `/api/v1/agents/`
* `updateAgent(id: string, data: AgentUpdateDto)`: PUT `/api/v1/agents/{id}/`
* `deleteAgent(id: string, cascade?: boolean)`: DELETE `/api/v1/agents/{id}/`
* `getAgentChildren(id: string)`: GET `/api/v1/agents/{id}/children/`
* `getAgentHierarchy(id: string)`: GET `/api/v1/agents/{id}/hierarchy/`
* `getEntireHierarchyTree()`: GET `/api/v1/agents/hierarchy/tree`
* `getTemplates(category?: string)`: GET `/api/v1/templates/`
* `instantiateTemplate(templateId: string, data: TemplateInstantiateDto)`: POST `/api/v1/templates/{templateId}/instantiate/`

#### Orchestrated Tasks & Tree
* `getTasks(params?: { agent_id?: string; project_id?: string; status?: string; limit?: number })`: GET `/api/v1/tasks/`
* `getTask(id: string)`: GET `/api/v1/tasks/{id}`
* `createTask(data: TaskCreateDto)`: POST `/api/v1/tasks/`
* `updateTask(id: string, data: Partial<TaskCreateDto>)`: PUT `/api/v1/tasks/{id}`
* `deleteTask(id: string)`: DELETE `/api/v1/tasks/{id}`
* `cancelTask(id: string)`: POST `/api/v1/tasks/{id}/cancel`
* `delegateTask(taskId: string, data: TaskDelegateDto)`: POST `/api/v1/tasks/{taskId}/delegate`
* `getSubtasks(taskId: string)`: GET `/api/v1/tasks/{taskId}/subtasks`
* `getTaskTree(taskId: string)`: GET `/api/v1/tasks/{taskId}/tree`
* `getTaskLogs(id: string)`: GET `/api/v1/tasks/{id}/logs`

#### Skills & Plugins Hub
* `getSkills()`: GET `/api/v1/skills/`
* `getSkill(id: string)`: GET `/api/v1/skills/{id}`
* `createSkill(data: Partial<Skill>)`: POST `/api/v1/skills/`
* `updateSkill(id: string, data: Partial<Skill>)`: PUT `/api/v1/skills/{id}`
* `deleteSkill(id: string)`: DELETE `/api/v1/skills/{id}`
* `scanPlugins(params?: { source_mode?: 'local' | 'git'; git_repo?: string; local_path?: string })`: GET `/api/v1/skills/plugins/scan`
* `getPluginsConfig()`: GET `/api/v1/skills/plugins/config`
* `updatePluginsConfig(data: { source_mode: 'local' | 'git'; git_repo?: string; local_path?: string })`: PUT `/api/v1/skills/plugins/config`
* `getPluginGitRepos(token?: string)`: GET `/api/v1/skills/plugins/git-repos`
* `getPluginSkillContent(path: string)`: GET `/api/v1/skills/plugins/content`

#### Model Context Protocol (MCP) Connectors & Resources
* `getMCPCatalog()`: GET `/api/v1/mcp/catalog`
* `getMCPConnectors()`: GET `/api/v1/mcp/connectors`
* `getMCPConnector(id: string)`: GET `/api/v1/mcp/connectors/{id}`
* `installMCPConnector(data)`: POST `/api/v1/mcp/connectors`
* `updateMCPConnector(id: string, data)`: PUT `/api/v1/mcp/connectors/{id}`
* `deleteMCPConnector(id: string)`: DELETE `/api/v1/mcp/connectors/{id}`
* `testMCPConnector(id: string)`: POST `/api/v1/mcp/connectors/{id}/test`
* `getMCPTools(connectorId: string)`: GET `/api/v1/mcp/connectors/{connectorId}/tools`
* `getMCPPermissions(agentId?: string)`: GET `/api/v1/mcp/permissions`
* `grantMCPPermission(data)`: POST `/api/v1/mcp/permissions/grant`
* `revokeMCPPermission(data)`: POST `/api/v1/mcp/permissions/revoke`
* `discoverMCPResources(provider: string, token?: string, configuration?: any)`: POST `/api/v1/mcp/discover-resources`
* `testChannelMessage(data: { provider: string; channel_id: string; message: string })`: POST `/api/v1/mcp/test-channel-message`

#### Workflows & Channel Bindings
* `getWorkflows()`: GET `/api/v1/workflows/`
* `getWorkflow(id: string)`: GET `/api/v1/workflows/{id}`
* `createWorkflow(data)`: POST `/api/v1/workflows/`
* `updateWorkflow(id: string, data)`: PUT `/api/v1/workflows/{id}`
* `deleteWorkflow(workflowId: string)`: DELETE `/api/v1/workflows/{workflowId}`
* `executeWorkflow(workflowId: string, payload?: Record<string, any>)`: POST `/api/v1/workflows/{workflowId}/execute`
* `bindWorkflowChannel(workflowId: string, data: WorkflowChannelBinding)`: POST `/api/v1/workflows/{workflowId}/channel-binding`
* `unbindWorkflowChannel(workflowId: string)`: DELETE `/api/v1/workflows/{workflowId}/channel-binding`
* `generateWorkflowDefinition(params)`: POST `/api/v1/workflows/generate`
* `convertWorkflowFormat(data)`: POST `/api/v1/workflows/convert-format`

#### Schedules & Approvals
* `getSchedules(params?)`: GET `/api/v1/schedules/`
* `createSchedule(data)`: POST `/api/v1/schedules/`
* `updateSchedule(id: string, data)`: PUT `/api/v1/schedules/{id}`
* `deleteSchedule(id: string)`: DELETE `/api/v1/schedules/{id}`
* `toggleSchedule(id: string, enabled: boolean)`: POST `/api/v1/schedules/{id}/toggle`
* `triggerScheduleNow(id: string)`: POST `/api/v1/schedules/{id}/trigger`
* `validateCronExpression(cron_expression: string)`: POST `/api/v1/schedules/validate`
* `getPendingApprovals(params?)`: GET `/api/v1/approvals/pending`
* `respondToApproval(data: ApprovalResponseDto)`: POST `/api/v1/approvals/respond`

#### Real-Time Chat & Collab
* `getAgentSessions(agentId: string)`: GET `/api/v1/chat/{agentId}/sessions`
* `createAgentSession(agentId: string, data?)`: POST `/api/v1/chat/{agentId}/sessions`
* `activateAgentSession(agentId: string, conversationId: string)`: POST `/api/v1/chat/{agentId}/sessions/{conversationId}/activate`
* `getChatHistory(agentId: string, conversationId?, limit?)`: GET `/api/v1/chat/{agentId}/messages`
* `sendChatMessage(agentId: string, content: string, projectId?, conversationId?)`: POST `/api/v1/chat/{agentId}/messages`
* `clearChatHistory(agentId: string)`: POST `/api/v1/chat/{agentId}/clear`
* `getWarRoomSessions(projectId?)`: GET `/api/v1/war-room/`
* `createWarRoomSession(data: WarRoomCreateDto)`: POST `/api/v1/war-room/`
* `sendWarRoomMessage(sessionId: string, data: WarRoomMessageCreateDto)`: POST `/api/v1/war-room/{sessionId}/messages`
* `synthesizeWarRoomPlan(sessionId: string, synthesized_plan: string)`: POST `/api/v1/war-room/{sessionId}/synthesize`

---

## 3. Real-Time Event Stream (`src/services/eventStream.ts`)

### 3.1 Architecture & SSE Invariants
* Connects directly to `/api/v1/events/stream` via the browser's native `EventSource`.
* **Zero Mocking**: Consumes raw platform events emitted by the backend event bus.
* **Sequence Tracking**: Maintains `lastSequence` state and transmits `?after_sequence={N}` upon reconnection to ensure zero dropped messages.
* **Auto-Reconnection**: Reconnects with exponential backoff if the SSE pipe drops.

### 3.2 Event Subscriber Pattern
Components or hooks register typed listeners:
```typescript
import { eventStream, PlatformEventPayload } from '../services/eventStream';

// Subscribe to specific event types
const unsubscribe = eventStream.subscribe('task:completed', (payload: PlatformEventPayload) => {
  console.log('Task completed:', payload.task_id);
});

// Or wildcard subscription
eventStream.subscribe('*', (payload) => { ... });
```

---

## 4. 🔄 Mandatory UI `AGENTS.md` Synchronization Rule

> [!IMPORTANT]
> **Every time an API endpoint or SSE event handling logic in `src/services/` is added, modified, or refactored, the developer/agent MUST update this file (`src/services/AGENTS.md`) as part of the same task.**
>
> Checklist on service changes:
> 1. Document new exported API functions and their corresponding HTTP route & method.
> 2. Detail any alterations to request or response interceptors.
> 3. Document any new SSE events or changes to `PlatformEventPayload`.
> 4. Ensure [`poc/dashboard/AGENTS.md`](file:///Users/yarintag/Desktop/Projects/ai-agents-platform/poc/dashboard/AGENTS.md) is updated if external integration capabilities change.
