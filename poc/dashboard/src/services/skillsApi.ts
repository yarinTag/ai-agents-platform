import { api } from './httpClient';
import type { Skill, PluginPackage, PluginsConfig } from '../types/skill';

// Skills
export const getSkills = () => api.get<Skill[]>('/api/v1/skills/');
export const getSkill = (id: string) => api.get<Skill>(`/api/v1/skills/${id}`);
export const createSkill = (data: Partial<Skill>) => api.post<Skill>('/api/v1/skills/', data);
export const updateSkill = (id: string, data: Partial<Skill>) => api.put<Skill>(`/api/v1/skills/${id}`, data);
export const deleteSkill = (id: string) => api.delete(`/api/v1/skills/${id}`);
export const scanPlugins = (params?: { source_mode?: 'local' | 'git'; git_repo?: string; local_path?: string }) =>
  api.get<{ status: string; marketplace_path?: string; plugins: PluginPackage[]; total_skills: number }>('/api/v1/skills/plugins/scan', { params });
export const getPluginsConfig = () => api.get<PluginsConfig>('/api/v1/skills/plugins/config');
export const updatePluginsConfig = (data: { source_mode: 'local' | 'git'; git_repo?: string; local_path?: string }) =>
  api.put<PluginsConfig>('/api/v1/skills/plugins/config', data);
export const getPluginGitRepos = (token?: string) =>
  api.get<{ repositories: any[]; has_token: boolean; provider?: string }>('/api/v1/skills/plugins/git-repos', {
    params: token ? { token } : {},
  });
export const getPluginSkillContent = (path: string) => api.get<{ path: string; content: string }>('/api/v1/skills/plugins/content', { params: { path } });
