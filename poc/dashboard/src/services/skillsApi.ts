import { api, AUTH_TOKEN_KEY } from './httpClient';
import { cachedRequest, invalidateRequestCache } from './requestCache';
import type { Skill, PluginPackage, PluginsConfig } from '../types/skill';

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
export const scanPlugins = (params?: { department_id?: string; source_mode?: 'local' | 'git'; git_repo?: string; local_path?: string }, forceRefresh = false) =>
  cachedRequest(pluginCacheKey('scan', params), () =>
    api.get<{ status: string; marketplace_path?: string; plugins: PluginPackage[]; total_skills: number }>('/api/v1/skills/plugins/scan',
      { params: { ...params, refresh: forceRefresh } }), 60_000, forceRefresh);
export const getPluginsConfig = (departmentId?: string | null) => cachedRequest(pluginCacheKey('config', departmentId),
  () => api.get<PluginsConfig>('/api/v1/skills/plugins/config', { params: { department_id: departmentId } }), 30_000);
export const updatePluginsConfig = async (data: { source_mode: 'local' | 'git' | 'inherit'; git_repo?: string; local_path?: string }, departmentId?: string | null) => {
  invalidateRequestCache('plugins:');
  const response = await api.put<PluginsConfig>('/api/v1/skills/plugins/settings', data, { params: { department_id: departmentId } });
  invalidateRequestCache('plugins:');
  return response;
};
export const getPluginGitRepos = (token?: string) => token
  ? api.post<{ repositories: any[]; has_token?: boolean; provider?: string }>('/api/v1/mcp/discover-resources', {
      provider: /^glpat[-_]/.test(token) ? 'gitlab' : 'github', token,
    }).then(response => ({ ...response, data: { ...response.data, has_token: true } }))
  : cachedRequest(pluginCacheKey('repos'),
      () => api.get<{ repositories: any[]; has_token: boolean; provider?: string }>('/api/v1/skills/plugins/git-repos'), 60_000);

export const getPluginSkillContent = (path: string, departmentId?: string | null) => api.get<{ path: string; content: string }>('/api/v1/skills/plugins/content', { params: { path, department_id: departmentId } });

