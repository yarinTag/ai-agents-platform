import { api } from './httpClient';
import type { ProjectMemory, ProjectMemoryCreateDto } from '../types/collab';

// Phase 3: Project Shared Memory & Knowledge Base


export const getProjectMemories = (projectId: string, category?: string) =>
  api.get<ProjectMemory[]>(`/api/v1/projects/${projectId}/memories`, { params: { category } });
export const createProjectMemory = (projectId: string, data: ProjectMemoryCreateDto) =>
  api.post<ProjectMemory>(`/api/v1/projects/${projectId}/memories`, data);
export const deleteProjectMemory = (projectId: string, memoryId: string) =>
  api.delete(`/api/v1/projects/${projectId}/memories/${memoryId}`);
export const getProjectContextPrompt = (projectId: string) =>
  api.get<{ context_prompt: string; memories_count: number }>(`/api/v1/projects/${projectId}/context-prompt`);
