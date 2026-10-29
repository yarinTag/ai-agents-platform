import { api } from './httpClient';
import type { Agent, AgentCreateDto, AgentUpdateDto, AgentTemplate, TemplateInstantiateDto } from '../types/agent';

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
