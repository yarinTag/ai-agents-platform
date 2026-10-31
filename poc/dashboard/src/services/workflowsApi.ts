import { api } from './httpClient';
import type { PlatformWorkflow, WorkflowChannelBinding, WorkflowExecution } from '../types/mcp';

// Workflows & Channel Bindings
export const getWorkflows = () =>
  api.get<PlatformWorkflow[]>('/api/v1/workflows/');

export const getWorkflow = (id: string) =>
  api.get<PlatformWorkflow>(`/api/v1/workflows/${id}`);

export const updateWorkflow = (id: string, data: Partial<PlatformWorkflow> & {
  expected_revision?: number; change_summary?: string;
}) =>
  api.put<PlatformWorkflow>(`/api/v1/workflows/${id}`, data);

export const getWorkflowRevisions = (id: string, beforeRevision?: number) =>
  api.get<import('../types/mcp').WorkflowRevision[]>(`/api/v1/workflows/${id}/revisions`, {
    params: { limit: 50, before_revision: beforeRevision },
  });

export const bindWorkflowChannel = (workflowId: string, data: WorkflowChannelBinding) =>
  api.post<PlatformWorkflow>(`/api/v1/workflows/${workflowId}/channel-binding`, data);

export const unbindWorkflowChannel = (workflowId: string) =>
  api.delete<PlatformWorkflow>(`/api/v1/workflows/${workflowId}/channel-binding`);

export const deleteWorkflow = (workflowId: string) =>
  api.delete<{ status: string; message: string }>(`/api/v1/workflows/${workflowId}`);

export const executeWorkflow = (
  workflowId: string,
  payload?: Record<string, any>,
  useQueue: boolean = true,
  forceRerun: boolean = false,
  background: boolean = false
) =>
  api.post<WorkflowExecution>(
    `/api/v1/workflows/${workflowId}/execute?use_queue=${useQueue}&force_rerun=${forceRerun}&background=${background}`,
    payload || {}
  );

export const executeWorkflowPlayground = (workflowId: string, payload: Record<string, unknown>) =>
  api.post<WorkflowExecution>(`/api/v1/workflows/${workflowId}/playground`, payload);

export const getWorkflowExecutions = (workflowId?: string, limit: number = 50) => {
  const params = new URLSearchParams();
  if (workflowId) params.append('workflow_id', workflowId);
  params.append('limit', String(limit));
  return api.get<WorkflowExecution[]>(`/api/v1/workflows/executions?${params.toString()}`);
};

export const getWorkflowExecution = (executionId: string) =>
  api.get<WorkflowExecution>(`/api/v1/workflows/executions/${executionId}`);

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

