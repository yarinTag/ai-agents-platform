import { api } from './httpClient';
import type { PlatformWorkflow } from '../types/mcp';
import type { WorkflowChatContext, WorkflowChatJob, WorkflowChatRequest } from '../types/workflowChat';

export const getWorkflowChatContext = (departmentId?: string) =>
  api.get<WorkflowChatContext>('/api/v1/workflows/ai/context', { params: { department_id: departmentId } });
export const startWorkflowChat = (request: WorkflowChatRequest) =>
  api.post<WorkflowChatJob>('/api/v1/workflows/ai/chat', request);
export const getWorkflowChat = (id: string) => api.get<WorkflowChatJob>(`/api/v1/workflows/ai/chat/${id}`);
export const cancelWorkflowChat = (id: string) => api.post<WorkflowChatJob>(`/api/v1/workflows/ai/chat/${id}/cancel`);
export const createWorkflowFromChat = (id: string) => api.post<PlatformWorkflow>(`/api/v1/workflows/ai/chat/${id}/create`);
