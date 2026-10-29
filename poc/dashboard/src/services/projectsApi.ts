import { api } from './httpClient';
import type { Project } from '../types/project';

// Projects
export const getProjects = () => api.get<Project[]>('/api/v1/projects/');
export const getProject = (id: string) => api.get<Project>(`/api/v1/projects/${id}`);
export const createProject = (data: Partial<Project>) => api.post<Project>('/api/v1/projects/', data);
export const updateProject = (id: string, data: Partial<Project>) => api.put<Project>(`/api/v1/projects/${id}`, data);
export const deleteProject = (id: string) => api.delete(`/api/v1/projects/${id}`);
