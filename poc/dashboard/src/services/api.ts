import axios from 'axios';
import { cachedRequest, invalidateRequestCache } from './requestCache';
import { Agent, AgentCreateDto, AgentUpdateDto, AgentTemplate, TemplateInstantiateDto } from '../types/agent';
import { Task, TaskCreateDto, TaskDelegateDto, TaskTreeNode } from '../types/task';
import { Skill, PluginPackage, PluginsConfig } from '../types/skill';
import { Project } from '../types/project';
import { ActivityEvent } from '../types/flow';
import { RuntimeSetupState, RuntimeSelectionDto } from '../types/runtime';
import {
  AuthResponse,
  CurrentUserProfileResponse,
  Department,
  DepartmentMember,
  BulkInviteResponse,
  OrganizationUser,
  LoginDto,
  RegisterOrgDto,
  AcceptInviteDto,
  CreateDepartmentDto,
  BulkInviteDto
} from '../types/auth';

export const AUTH_TOKEN_KEY = 'agents_platform_auth_token';
export const AUTH_SESSION_KEY = 'agents_platform_auth_session';

const API_BASE_URL = 'http://localhost:8000';

export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
});

// Axios Request Interceptor: Attach Bearer token from localStorage
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem(AUTH_TOKEN_KEY);
    if (token) {
      if (config.headers) {
        config.headers.Authorization = `Bearer ${token}`;
      }
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Axios Response Interceptor: Catch 401 and broadcast auth:unauthorized
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      const url = error.config?.url || '';
      const isAuthExempt =
        url.includes('/auth/login') ||
        url.includes('/auth/org-register') ||
        url.includes('/invitations/accept');

      if (!isAuthExempt) {
        invalidateRequestCache('plugins:');
        localStorage.removeItem(AUTH_TOKEN_KEY);
        localStorage.removeItem(AUTH_SESSION_KEY);
        window.dispatchEvent(new CustomEvent('auth:unauthorized'));
      }
    }
    return Promise.reject(error);
  }
);

// Runtime providers (first-run setup)
export const getRuntimeSetupState = () => api.get<RuntimeSetupState>('/api/v1/runtimes/');
export const redetectRuntimeProviders = () => api.post<RuntimeSetupState>('/api/v1/runtimes/detect');
export const selectRuntimeProvider = (data: RuntimeSelectionDto) =>
  api.put<RuntimeSetupState>('/api/v1/runtimes/selection', data);

// Agents & Hierarchy
export const getAgents = () => api.get<Agent[]>('/api/v1/agents/');
export const getAgent = (id: string) => api.get<Agent>(`/api/v1/agents/${id}/`);
export const createAgent = (data: AgentCreateDto) => api.post<Agent>('/api/v1/agents/', data);
export const updateAgent = (id: string, data: AgentUpdateDto) => api.put<Agent>(`/api/v1/agents/${id}/`, data);
export const deleteAgent = (id: string, cascade: boolean = true) =>
  api.delete(`/api/v1/agents/${id}/`, { params: { cascade } });
export const getAgentChildren = (id: string) => api.get<Agent[]>(`/api/v1/agents/${id}/children/`);
export const getAgentHierarchy = (id: string) => api.get<any[]>(`/api/v1/agents/${id}/hierarchy/`);
export const getEntireHierarchyTree = () => api.get<any[]>('/api/v1/agents/hierarchy/tree');

// Templates
export const getTemplates = (category?: string) =>
  api.get<AgentTemplate[]>('/api/v1/templates/', { params: category ? { category } : {} });
export const getTemplate = (id: string) => api.get<AgentTemplate>(`/api/v1/templates/${id}/`);
export const createTemplate = (data: Partial<AgentTemplate>) => api.post<AgentTemplate>('/api/v1/templates/', data);
export const deleteTemplate = (id: string) => api.delete(`/api/v1/templates/${id}/`);
export const instantiateTemplate = (templateId: string, data: TemplateInstantiateDto) =>
  api.post<Agent>(`/api/v1/templates/${templateId}/instantiate/`, data);

// Projects
export const getProjects = () => api.get<Project[]>('/api/v1/projects/');
export const getProject = (id: string) => api.get<Project>(`/api/v1/projects/${id}`);
export const createProject = (data: Partial<Project>) => api.post<Project>('/api/v1/projects/', data);
export const updateProject = (id: string, data: Partial<Project>) => api.put<Project>(`/api/v1/projects/${id}`, data);
export const deleteProject = (id: string) => api.delete(`/api/v1/projects/${id}`);

// Catalog data is kept only in memory and discarded whenever the auth session changes.
let pluginCacheSession: string | null = null;
function pluginCacheKey(kind: string, args: unknown = null) {
  const session = localStorage.getItem(AUTH_TOKEN_KEY) || '';
  if (pluginCacheSession !== session) {
    invalidateRequestCache('plugins:');
    pluginCacheSession = session;
  }
  return `plugins:${kind}:${JSON.stringify(args)}`;
}

// Skills
export const getSkills = () => api.get<Skill[]>('/api/v1/skills/');
export const getSkill = (id: string) => api.get<Skill>(`/api/v1/skills/${id}`);
export const createSkill = (data: Partial<Skill>) => api.post<Skill>('/api/v1/skills/', data);
export const updateSkill = (id: string, data: Partial<Skill>) => api.put<Skill>(`/api/v1/skills/${id}`, data);
export const deleteSkill = (id: string) => api.delete(`/api/v1/skills/${id}`);
export const scanPlugins = (params?: { source_mode?: 'local' | 'git'; git_repo?: string; local_path?: string }, forceRefresh = false) =>
  cachedRequest(pluginCacheKey('scan', params), () =>
    api.get<{ status: string; marketplace_path?: string; plugins: PluginPackage[]; total_skills: number }>('/api/v1/skills/plugins/scan',
      { params: { ...params, refresh: forceRefresh } }), 60_000, forceRefresh);
export const getPluginsConfig = () => cachedRequest(pluginCacheKey('config'),
  () => api.get<PluginsConfig>('/api/v1/skills/plugins/config'), 30_000);
export const updatePluginsConfig = async (data: { source_mode: 'local' | 'git'; git_repo?: string; local_path?: string }) => {
  invalidateRequestCache('plugins:');
  const response = await api.put<PluginsConfig>('/api/v1/skills/plugins/config', data);
  invalidateRequestCache('plugins:');
  return response;
};
export const getPluginGitRepos = (token?: string) => cachedRequest(pluginCacheKey('repos', token),
  () => api.get<{ repositories: any[]; has_token: boolean; provider?: string }>('/api/v1/skills/plugins/git-repos', {
    params: token ? { token } : {},
  }), 60_000);
export const getPluginSkillContent = (path: string) => api.get<{ path: string; content: string }>('/api/v1/skills/plugins/content', { params: { path } });

// Tasks
export const getTasks = (params?: { agent_id?: string; project_id?: string; status?: string; limit?: number; execution_scope?: 'all' | 'office' | 'workflow' }) =>
  api.get<Task[]>('/api/v1/tasks/', { params });
export const getTask = (id: string) => api.get<Task>(`/api/v1/tasks/${id}`);
export const getTaskLogs = (id: string) => api.get<{ run_id: string; events: any[]; status: string; result: any; error: any }>(`/api/v1/tasks/${id}/logs`);
export const createTask = (data: TaskCreateDto) => api.post<Task>('/api/v1/tasks/', data);
export const updateTask = (id: string, data: Partial<TaskCreateDto>) => api.put<Task>(`/api/v1/tasks/${id}`, data);
export const deleteTask = (id: string) => api.delete(`/api/v1/tasks/${id}`);
export const cancelTask = (id: string) => api.post(`/api/v1/tasks/${id}/cancel`);
export const delegateTask = (taskId: string, data: TaskDelegateDto) => api.post<Task>(`/api/v1/tasks/${taskId}/delegate`, data);
export const getSubtasks = (taskId: string) => api.get<Task[]>(`/api/v1/tasks/${taskId}/subtasks`);
export const getTaskTree = (taskId: string) => api.get<TaskTreeNode>(`/api/v1/tasks/${taskId}/tree`);

// Distributed Queue & RabbitMQ Broker
export interface QueueStatus {
  broker: string;
  connected: boolean;
  queues: Record<string, number>;
  dead_letter_count: number;
  worker_running: boolean;
  active_worker_tasks: number;
  timestamp: string;
}

export const getQueueStatus = () => api.get<QueueStatus>('/api/v1/queue/status');
export const getDeadLetterQueue = () => api.get<any[]>('/api/v1/queue/dlq');
export const retryDeadLetter = (messageId: string) => api.post(`/api/v1/queue/retry/${messageId}`);

// System Stats & Real-Time Monitoring
export const getSystemStats = () => api.get('/api/v1/events/system/stats');
export const getSystemHealth = () => api.get('/api/v1/events/system/health');
export const getRecentActivity = (limit = 25, executionScope: 'all' | 'office' | 'workflow' = 'all') => api.get<{ activity: ActivityEvent[]; timestamp: string }>(`/api/v1/events/system/recent-activity?limit=${limit}&execution_scope=${executionScope}`);

// Models Discovery
export interface DiscoveredModel {
  id: string;
  name: string;
  provider: string;
  description: string;
  context_window: number;
  is_default?: boolean;
}
export const getAvailableModels = () => api.get<DiscoveredModel[]>('/api/v1/models/');

// Schedules & Cron Jobs
import { ScheduledJob, ScheduledJobCreateDto, ApprovalRequest, ApprovalResponseDto } from '../types/scheduler';

export const getSchedules = (params?: { agent_id?: string; project_id?: string; enabled?: boolean }) =>
  api.get<ScheduledJob[]>('/api/v1/schedules/', { params });
export const getSchedule = (id: string) => api.get<ScheduledJob>(`/api/v1/schedules/${id}`);
export const createSchedule = (data: ScheduledJobCreateDto) => api.post<ScheduledJob>('/api/v1/schedules/', data);
export const updateSchedule = (id: string, data: Partial<ScheduledJobCreateDto>) => api.put<ScheduledJob>(`/api/v1/schedules/${id}`, data);
export const deleteSchedule = (id: string) => api.delete(`/api/v1/schedules/${id}`);
export const toggleSchedule = (id: string, enabled: boolean) => api.post(`/api/v1/schedules/${id}/toggle`, { enabled });
export const triggerScheduleNow = (id: string) => api.post<{ message: string; task_id: string }>(`/api/v1/schedules/${id}/trigger`);
export const validateCronExpression = (cron_expression: string) => api.post<{ valid: boolean; upcoming_runs?: string[]; error?: string }>('/api/v1/schedules/validate', { cron_expression });

// Approvals & Human-In-The-Loop
export const getPendingApprovals = (params?: { agent_id?: string; target_approver_id?: string }) =>
  api.get<ApprovalRequest[]>('/api/v1/approvals/pending', { params });
export const createApprovalRequest = (data: any) => api.post<ApprovalRequest>('/api/v1/approvals/', data);
export const respondToApproval = (data: ApprovalResponseDto) => api.post('/api/v1/approvals/respond', data);

// Interactive Agent Mini-Chat
import { ChatHistoryResponse, ChatMessage, AgentSession } from '../types/chat';

export const getAgentSessions = (agentId: string) =>
  api.get<{ sessions: AgentSession[] }>(`/api/v1/chat/${agentId}/sessions`);

export const createAgentSession = (agentId: string, data?: { title?: string; project_id?: string | null; task_id?: string | null }) =>
  api.post<{ session: AgentSession }>(`/api/v1/chat/${agentId}/sessions`, data || {});

export const activateAgentSession = (agentId: string, conversationId: string) =>
  api.post<{ session: AgentSession }>(`/api/v1/chat/${agentId}/sessions/${conversationId}/activate`);

export const getChatHistory = (agentId: string, conversationId?: string | null, limit: number = 100) =>
  api.get<ChatHistoryResponse>(`/api/v1/chat/${agentId}/messages`, { params: { conversation_id: conversationId, limit } });

export const sendChatMessage = (agentId: string, content: string, projectId?: string | null, conversationId?: string | null) =>
  api.post<{ status: string; task_id?: string; user_message: ChatMessage }>(`/api/v1/chat/${agentId}/messages`, {
    content,
    project_id: projectId,
    conversation_id: conversationId,
  });

export const clearChatHistory = (agentId: string) =>
  api.post<{ status: string }>(`/api/v1/chat/${agentId}/clear`);

// Phase 3: Project Shared Memory & Knowledge Base
import {
  ProjectMemory,
  ProjectMemoryCreateDto,
  WarRoomSession,
  WarRoomDetail,
  WarRoomCreateDto,
  WarRoomMessageCreateDto
} from '../types/collab';

export const getProjectMemories = (projectId: string, category?: string) =>
  api.get<ProjectMemory[]>(`/api/v1/projects/${projectId}/memories`, { params: { category } });
export const createProjectMemory = (projectId: string, data: ProjectMemoryCreateDto) =>
  api.post<ProjectMemory>(`/api/v1/projects/${projectId}/memories`, data);
export const deleteProjectMemory = (projectId: string, memoryId: string) =>
  api.delete(`/api/v1/projects/${projectId}/memories/${memoryId}`);
export const getProjectContextPrompt = (projectId: string) =>
  api.get<{ context_prompt: string; memories_count: number }>(`/api/v1/projects/${projectId}/context-prompt`);

// Phase 3: Multi-Agent War Room & Deliberation
export const getWarRoomSessions = (projectId?: string) =>
  api.get<WarRoomSession[]>('/api/v1/war-room/', { params: { project_id: projectId } });
export const createWarRoomSession = (data: WarRoomCreateDto) =>
  api.post<WarRoomSession>('/api/v1/war-room/', data);
export const getWarRoomSession = (sessionId: string) =>
  api.get<WarRoomDetail>(`/api/v1/war-room/${sessionId}`);
export const sendWarRoomMessage = (sessionId: string, data: WarRoomMessageCreateDto) =>
  api.post('/api/v1/war-room/' + sessionId + '/messages', data);
export const synthesizeWarRoomPlan = (sessionId: string, synthesized_plan: string) =>
  api.post<WarRoomSession>(`/api/v1/war-room/${sessionId}/synthesize`, { synthesized_plan });

// Agent Messaging, Teams & MCP
import {
  AgentMessage,
  AgentTeam,
  MCPConnector,
  MCPTool,
  MCPCatalogItem,
  AgentMCPPermission,
  PlatformWorkflow,
  WorkflowChannelBinding,
  WorkflowExecution,
} from '../types/mcp';

export const getAgentMessages = (agentId?: string, limit: number = 50) =>
  api.get<AgentMessage[]>('/api/v1/messages', { params: agentId ? { agent_id: agentId, limit } : { limit } });

export const sendAgentMessage = (data: { from_agent_id: string; to_agent_id: string; content: string; message_type?: string; task_id?: string; metadata?: any }) =>
  api.post<AgentMessage>('/api/v1/messages', data);

export const replyAgentMessage = (messageId: string, data: { from_agent_id: string; content: string; message_type?: string; metadata?: any }) =>
  api.post<AgentMessage>(`/api/v1/messages/${messageId}/reply`, data);

export const getAgentTeams = (projectId?: string) =>
  api.get<AgentTeam[]>('/api/v1/teams', { params: projectId ? { project_id: projectId } : {} });

export const createAgentTeam = (data: { name: string; manager_agent_id: string; member_agent_ids: string[]; project_id?: string; description?: string }) =>
  api.post<AgentTeam>('/api/v1/teams', data);

export const dispatchAgentTeam = (teamId: string, data: { shared_goal: string; member_prompts?: Record<string, string>; parent_task_id?: string }) =>
  api.post<{ team_id: string; status: string; shared_goal: string; tasks: any[] }>(`/api/v1/teams/${teamId}/dispatch`, data);

export const synthesizeAgentTeam = (teamId: string, data: { task_ids: string[] }) =>
  api.post<{ team_id: string; status: string; synthesis: string; member_results: any[] }>(`/api/v1/teams/${teamId}/synthesize`, data);

// Filesystem & Local Workspace Picker
export interface FolderItem {
  name: string;
  path: string;
  is_project: boolean;
  project_type?: string;
  has_children: boolean;
}

export interface QuickAccessItem {
  name: string;
  path: string;
  icon?: string;
}

export interface BrowseResponse {
  current_path: string;
  parent_path?: string | null;
  name: string;
  is_root: boolean;
  quick_access: QuickAccessItem[];
  folders: FolderItem[];
}

export interface PickFolderResponse {
  path?: string | null;
  name?: string | null;
  is_project: boolean;
  project_type?: string | null;
  cancelled: boolean;
  error?: string | null;
}

export const browseDirectory = (path?: string) =>
  api.get<BrowseResponse>('/api/v1/fs/browse', { params: path ? { path } : {} });

export const pickFolderNative = (initialPath?: string) =>
  api.post<PickFolderResponse>('/api/v1/fs/pick-folder', { initial_path: initialPath }, { timeout: 180000 });

// Model Context Protocol (MCP) Hub
export const getMCPCatalog = () =>
  api.get<{ catalog: MCPCatalogItem[] }>('/api/v1/mcp/catalog');

export const getMCPConnectors = () =>
  api.get<{ connectors: MCPConnector[] }>('/api/v1/mcp/connectors');

export const getMCPConnector = (id: string) =>
  api.get<MCPConnector & { tools: MCPTool[] }>(`/api/v1/mcp/connectors/${id}`);

export const installMCPConnector = (data: {
  id?: string;
  name: string;
  provider: string;
  configuration: Record<string, any>;
  capabilities?: string[];
  custom_command?: string;
}) => api.post<MCPConnector>('/api/v1/mcp/connectors', data);

export const updateMCPConnector = (id: string, data: Partial<MCPConnector>) =>
  api.put<MCPConnector>(`/api/v1/mcp/connectors/${id}`, data);

export const deleteMCPConnector = (id: string) =>
  api.delete<{ status: string; message: string }>(`/api/v1/mcp/connectors/${id}`);

export const testMCPConnector = (id: string) =>
  api.post<{ status: string; connector_id: string; message: string; tools_discovered: number; timestamp: string }>(
    `/api/v1/mcp/connectors/${id}/test`
  );

export const getMCPTools = (connectorId: string) =>
  api.get<{ tools: MCPTool[] }>(`/api/v1/mcp/connectors/${connectorId}/tools`);

export const getMCPPermissions = (agentId?: string) =>
  api.get<{ permissions: AgentMCPPermission[] }>('/api/v1/mcp/permissions', { params: agentId ? { agent_id: agentId } : {} });

export const grantMCPPermission = (data: { agent_id: string; connector_id: string; tool_id?: string | null }) =>
  api.post('/api/v1/mcp/permissions/grant', data);

export const revokeMCPPermission = (data: { agent_id: string; connector_id: string; tool_id?: string | null }) =>
  api.post('/api/v1/mcp/permissions/revoke', data);

export const discoverMCPResources = (provider: string, token?: string, configuration?: any) =>
  api.post<{ provider: string; repositories?: any[]; channels?: any[]; chats?: any[]; requires_token?: boolean; message?: string }>('/api/v1/mcp/discover-resources', {
    provider,
    token,
    configuration,
  });

export const testChannelMessage = (data: { provider: string; channel_id: string; message: string }) =>
  api.post<{ status: string; channel_id: string; message: string; timestamp: string }>('/api/v1/mcp/test-channel-message', data);

// Workflows & Channel Bindings
export const getWorkflows = () =>
  api.get<PlatformWorkflow[]>('/api/v1/workflows/');

export const getWorkflow = (id: string) =>
  api.get<PlatformWorkflow>(`/api/v1/workflows/${id}`);

export const updateWorkflow = (id: string, data: Partial<PlatformWorkflow>) =>
  api.put<PlatformWorkflow>(`/api/v1/workflows/${id}`, data);

export const bindWorkflowChannel = (workflowId: string, data: WorkflowChannelBinding) =>
  api.post<PlatformWorkflow>(`/api/v1/workflows/${workflowId}/channel-binding`, data);

export const unbindWorkflowChannel = (workflowId: string) =>
  api.delete<PlatformWorkflow>(`/api/v1/workflows/${workflowId}/channel-binding`);

export const deleteWorkflow = (workflowId: string) =>
  api.delete<{ status: string; message: string }>(`/api/v1/workflows/${workflowId}`);

export const executeWorkflow = (
  workflowId: string,
  payload?: Record<string, any>,
  useQueue: boolean = true,
  forceRerun: boolean = false
) =>
  api.post<WorkflowExecution>(
    `/api/v1/workflows/${workflowId}/execute?use_queue=${useQueue}&force_rerun=${forceRerun}`,
    payload || {}
  );

export const executeWorkflowPlayground = (workflowId: string, payload: Record<string, unknown>) =>
  api.post<WorkflowExecution>(`/api/v1/workflows/${workflowId}/playground`, payload);

export const getWorkflowExecutions = (workflowId?: string, limit: number = 50) => {
  const params = new URLSearchParams();
  if (workflowId) params.append('workflow_id', workflowId);
  params.append('limit', String(limit));
  return api.get<WorkflowExecution[]>(`/api/v1/workflows/executions?${params.toString()}`);
};

export const getWorkflowExecution = (executionId: string) =>
  api.get<WorkflowExecution>(`/api/v1/workflows/executions/${executionId}`);

export const createWorkflow = (data: {
  name: string;
  description?: string;
  department_id?: string;
  definition_yaml?: string;
  definition_json?: string;
  cron_expression?: string;
  webhook_enabled?: boolean;
}) => api.post<PlatformWorkflow>('/api/v1/workflows/', data);

export const generateWorkflowDefinition = (params: {
  prompt?: string;
  template_type?: string;
  name?: string;
  channel_provider?: string;
  channel_id?: string;
  allowed_mcps?: string[];
  skills?: any[];
  target_repo?: string;
}) =>
  api.post<{
    id: string;
    name: string;
    description: string;
    definition_json: string;
    definition_yaml: string;
    steps_count: number;
  }>('/api/v1/workflows/generate', params);

export const convertWorkflowFormat = (data: { yaml_content?: string; json_content?: string }) =>
  api.post<{ yaml_content: string; json_content: string }>('/api/v1/workflows/convert-format', data);

// Enterprise Organization & Authentication
export const loginOrganizationUser = (data: LoginDto) =>
  api.post<AuthResponse>('/api/v1/auth/login', data);

export const registerOrganization = (data: RegisterOrgDto) =>
  api.post<AuthResponse>('/api/v1/auth/org-register', data);

export const acceptOrgInvitation = (data: AcceptInviteDto) =>
  api.post<AuthResponse>('/api/v1/invitations/accept', data);

export const getCurrentUserProfile = () =>
  api.get<CurrentUserProfileResponse>('/api/v1/auth/me');

export const getDepartments = (organization_id?: string) =>
  api.get<Department[]>('/api/v1/departments', { params: organization_id ? { organization_id } : {} });

export const createDepartment = (data: CreateDepartmentDto) =>
  api.post<Department>('/api/v1/departments', data);

export const getDepartmentMembers = (deptId: string) =>
  api.get<DepartmentMember[]>(`/api/v1/departments/${deptId}/members`);

export const bulkInviteDepartmentMembers = (deptId: string, data: BulkInviteDto) =>
  api.post<BulkInviteResponse>(`/api/v1/departments/${deptId}/members/bulk-invite`, data);

export const removeDepartmentMember = (deptId: string, userId: string) =>
  api.delete<{ status: string; message: string }>(`/api/v1/departments/${deptId}/members/${userId}`);

export const getOrganizationUsers = (orgId: string) =>
  api.get<OrganizationUser[]>(`/api/v1/organizations/${orgId}/users`);

export default api;



