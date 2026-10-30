import { api } from './httpClient';
import type { ScheduledJob, ScheduledJobCreateDto } from '../types/scheduler';

// Schedules & Cron Jobs


export const getSchedules = (params?: { agent_id?: string; project_id?: string; enabled?: boolean }) =>
  api.get<ScheduledJob[]>('/api/v1/schedules/', { params });
export const getSchedule = (id: string) => api.get<ScheduledJob>(`/api/v1/schedules/${id}`);
export const createSchedule = (data: ScheduledJobCreateDto) => api.post<ScheduledJob>('/api/v1/schedules/', data);
export const updateSchedule = (id: string, data: Partial<ScheduledJobCreateDto>) => api.put<ScheduledJob>(`/api/v1/schedules/${id}`, data);
export const deleteSchedule = (id: string) => api.delete(`/api/v1/schedules/${id}`);
export const toggleSchedule = (id: string, enabled: boolean) => api.post(`/api/v1/schedules/${id}/toggle`, { enabled });
export const triggerScheduleNow = (id: string) => api.post<{ message: string; task_id: string }>(`/api/v1/schedules/${id}/trigger`);
export const validateCronExpression = (cron_expression: string) => api.post<{ valid: boolean; upcoming_runs?: string[]; error?: string }>('/api/v1/schedules/validate', { cron_expression });
