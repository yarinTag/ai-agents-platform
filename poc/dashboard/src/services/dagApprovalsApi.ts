import { api } from './httpClient';

export type DagApproval = {
  id: string;
  execution_id: string;
  workflow_id: string;
  workflow_name: string;
  step_key: string;
  expires_at: number;
  approver_roles: string[];
  quorum: number;
  approvals: number;
  can_decide: boolean;
  cost_usd: number;
  outputs: { step_key: string; excerpt: string; truncated: boolean }[];
  omitted_outputs: number;
};

const base = '/api/v1/workflows/dag-approvals';
export const listDagApprovals = (department_id: string, after: string | undefined, signal: AbortSignal) =>
  api.get<{ items: DagApproval[]; next_after: string | null }>(base, { params: { department_id, after }, signal });
export const decideDagApproval = (department_id: string, id: string, approve: boolean, signal: AbortSignal) =>
  api.post<{ status: 'PENDING' | 'APPROVED' | 'REJECTED' | 'TIMED_OUT' }>(
    `${base}/${encodeURIComponent(id)}/decision`, { approve }, { params: { department_id }, signal },
  );
