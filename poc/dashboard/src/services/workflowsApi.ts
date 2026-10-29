import { api } from './httpClient';
import type { PlatformWorkflow, WorkflowChannelBinding } from '../types/mcp';

// Workflows & Channel Bindings
export const getWorkflows = () =>
  api.get<PlatformWorkflow[]>('/api/v1/workflows/');

export const getWorkflow = (id: string) =>
  api.get<PlatformWorkflow>(`/api/v1/workflows/${id}`);

export const updateWorkflow = (id: string, data: Partial<PlatformWorkflow>) =>
  api.put<PlatformWorkflow>(`/api/v1/workflows/${id}`, data);

export const bindWorkflowChannel = (workflowId: string, data: WorkflowChannelBinding) =>
  api.post<PlatformWorkflow>(`/api/v1/workflows/${workflowId}/channel-binding`, data);

export const unbindWorkflowChannel = (workflowId: string) =>
  api.delete<PlatformWorkflow>(`/api/v1/workflows/${workflowId}/channel-binding`);

export const deleteWorkflow = (workflowId: string) =>
  api.delete<{ status: string; message: string }>(`/api/v1/workflows/${workflowId}`);

export const executeWorkflow = (workflowId: string, payload?: Record<string, any>) =>
  api.post<{ id: string; status: string; workflow_id: string }>(`/api/v1/workflows/${workflowId}/execute`, payload || {});

export const createWorkflow = (data: {
  name: string;
  description?: string;
  department_id?: string;
  definition_yaml?: string;
  definition_json?: string;
  cron_expression?: string;
  webhook_enabled?: boolean;
}) => api.post<PlatformWorkflow>('/api/v1/workflows/', data);

export const generateWorkflowDefinition = (params: {
  prompt?: string;
  template_type?: string;
  name?: string;
  channel_provider?: string;
  channel_id?: string;
  allowed_mcps?: string[];
  skills?: any[];
  target_repo?: string;
}) =>
  api.post<{
    id: string;
    name: string;
    description: string;
    definition_json: string;
    definition_yaml: string;
    steps_count: number;
  }>('/api/v1/workflows/generate', params);

export const convertWorkflowFormat = (data: { yaml_content?: string; json_content?: string }) =>
  api.post<{ yaml_content: string; json_content: string }>('/api/v1/workflows/convert-format', data);
