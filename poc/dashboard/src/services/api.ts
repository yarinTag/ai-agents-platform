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
export const deleteAgent = (id: string) => api.delete(`/api/v1/agents/${id}/`);
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
export const scanPlugins = () => api.get<{ status: string; plugins: PluginPackage[]; total_skills: number }>('/api/v1/skills/plugins/scan');

// Tasks
export const getTasks = () => api.get<Task[]>('/api/v1/tasks/');
export const getTask = (id: string) => api.get<Task>(`/api/v1/tasks/${id}/`);
export const createTask = (data: TaskCreateDto) => api.post<Task>('/api/v1/tasks/', data);
export const updateTask = (id: string, data: Partial<TaskCreateDto>) => api.put<Task>(`/api/v1/tasks/${id}/`, data);
export const deleteTask = (id: string) => api.delete(`/api/v1/tasks/${id}/`);
export const cancelTask = (id: string) => api.post(`/api/v1/tasks/${id}/cancel/`);
export const delegateTask = (taskId: string, data: TaskDelegateDto) => api.post<Task>(`/api/v1/tasks/${taskId}/delegate/`, data);
export const getSubtasks = (taskId: string) => api.get<Task[]>(`/api/v1/tasks/${taskId}/subtasks/`);
export const getTaskTree = (taskId: string) => api.get<TaskTreeNode>(`/api/v1/tasks/${taskId}/tree/`);

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

export default api;
