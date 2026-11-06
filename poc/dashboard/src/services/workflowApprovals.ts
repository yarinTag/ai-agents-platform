import { api } from './httpClient';

export interface WorkflowApproval {
  id: string; status: string; report: string; kind: string; merge_after_approval: boolean;
  expires_at: string; resolved_by?: string; error?: string;
  subjects: Array<{ repository: string; pull_number: number; head_sha: string; base_sha: string; url: string }>;
  receipts: Array<{ repository: string; pull_number: number; status: string; merge_commit_sha?: string }>;
}
export const getWorkflowApproval = (executionId: string) =>
  api.get<WorkflowApproval | null>(`/api/v1/workflows/executions/${encodeURIComponent(executionId)}/approval`);
export const decideWorkflowApproval = (executionId: string, approve: boolean) =>
  api.post(`/api/v1/workflows/executions/${encodeURIComponent(executionId)}/approval`, { approve });
