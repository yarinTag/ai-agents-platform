import axios from 'axios';
import { Agent, AgentCreateDto, AgentUpdateDto, AgentTemplate, TemplateInstantiateDto } from '../types/agent';
import { Task, TaskCreateDto, TaskDelegateDto, TaskTreeNode } from '../types/task';
import { Skill, PluginPackage } from '../types/skill';
import { Project } from '../types/project';
import { ActivityEvent } from '../types/flow';

const API_BASE_URL = 'http://localhost:8000';

export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
});

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

// Skills
export const getSkills = () => api.get<Skill[]>('/api/v1/skills/');
export const getSkill = (id: string) => api.get<Skill>(`/api/v1/skills/${id}`);
export const createSkill = (data: Partial<Skill>) => api.post<Skill>('/api/v1/skills/', data);
export const updateSkill = (id: string, data: Partial<Skill>) => api.put<Skill>(`/api/v1/skills/${id}`, data);
export const deleteSkill = (id: string) => api.delete(`/api/v1/skills/${id}`);
export const scanPlugins = () => api.get<{ status: string; marketplace_path?: string; plugins: PluginPackage[]; total_skills: number }>('/api/v1/skills/plugins/scan');
export const getPluginSkillContent = (path: string) => api.get<{ path: string; content: string }>('/api/v1/skills/plugins/content', { params: { path } });

// Tasks
export const getTasks = (params?: { agent_id?: string; project_id?: string; status?: string; limit?: number }) =>
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

// System Stats & Real-Time Monitoring
export const getSystemStats = () => api.get('/api/v1/events/system/stats');
export const getSystemHealth = () => api.get('/api/v1/events/system/health');
export const getRecentActivity = (limit = 25) => api.get<{ activity: ActivityEvent[]; timestamp: string }>(`/api/v1/events/system/recent-activity?limit=${limit}`);

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
import { ChatHistoryResponse, ChatMessage } from '../types/chat';

export const getChatHistory = (agentId: string, limit: number = 100) =>
  api.get<ChatHistoryResponse>(`/api/v1/chat/${agentId}/messages`, { params: { limit } });
export const sendChatMessage = (agentId: string, content: string, projectId?: string | null) =>
  api.post<{ status: string; task_id?: string; user_message: ChatMessage }>(`/api/v1/chat/${agentId}/messages`, { content, project_id: projectId });
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

export default api;


