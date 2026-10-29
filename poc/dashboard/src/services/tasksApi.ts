import { api } from './httpClient';
import type { Task, TaskCreateDto, TaskDelegateDto, TaskTreeNode } from '../types/task';

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
