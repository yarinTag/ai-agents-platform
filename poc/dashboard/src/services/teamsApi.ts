import { api } from './httpClient';
import type { AgentTeam } from '../types/mcp';

export const getAgentTeams = (projectId?: string) =>
  api.get<AgentTeam[]>('/api/v1/teams', { params: projectId ? { project_id: projectId } : {} });

export const createAgentTeam = (data: { name: string; manager_agent_id: string; member_agent_ids: string[]; project_id?: string; description?: string }) =>
  api.post<AgentTeam>('/api/v1/teams', data);

export const dispatchAgentTeam = (teamId: string, data: { shared_goal: string; member_prompts?: Record<string, string>; parent_task_id?: string }) =>
  api.post<{ team_id: string; status: string; shared_goal: string; tasks: any[] }>(`/api/v1/teams/${teamId}/dispatch`, data);

export const synthesizeAgentTeam = (teamId: string, data: { task_ids: string[] }) =>
  api.post<{ team_id: string; status: string; synthesis: string; member_results: any[] }>(`/api/v1/teams/${teamId}/synthesize`, data);
