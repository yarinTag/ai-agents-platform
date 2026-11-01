import { api } from './httpClient';
import type {
  WorkflowSecretSummary,
  WorkflowSecretWriteRequest,
  WorkflowSettingsResponse,
  WorkflowSettingsUpdateRequest,
} from '../types/workflowSettings';

const workflowPath = (workflowId: string) => `/api/v1/workflows/${encodeURIComponent(workflowId)}`;

/** Settings, secret metadata (never values), manage permission and machine-size presets. */
export const getWorkflowSettings = (workflowId: string) =>
  api.get<WorkflowSettingsResponse>(`${workflowPath(workflowId)}/settings`);

/** Optimistic-concurrency update: 409 when expected_revision is stale. */
export const updateWorkflowSettings = (workflowId: string, request: WorkflowSettingsUpdateRequest) =>
  api.put<WorkflowSettingsResponse>(`${workflowPath(workflowId)}/settings`, request);

/** Create or replace a write-only secret. Callers must not retain or log the submitted value. */
export const putWorkflowSecret = (workflowId: string, name: string, body: WorkflowSecretWriteRequest) =>
  api.put<WorkflowSecretSummary>(`${workflowPath(workflowId)}/secrets/${encodeURIComponent(name)}`, body);

export const deleteWorkflowSecret = (workflowId: string, name: string) =>
  api.delete<void>(`${workflowPath(workflowId)}/secrets/${encodeURIComponent(name)}`);
