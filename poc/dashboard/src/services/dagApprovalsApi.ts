import { api } from './httpClient';

export type ApprovalView = 'pending' | 'history';
export type DagApprovalStatus = 'PENDING' | 'APPROVED' | 'REJECTED' | 'TIMED_OUT';

export type DagApproval = {
  id: string;
  execution_id: string;
  workflow_id: string;
  workflow_name: string;
  step_key: string;
  expires_at: number;
  decided_at: number | null;
  status: DagApprovalStatus;
  my_vote: Exclude<DagApprovalStatus, 'PENDING' | 'TIMED_OUT'> | null;
  approver_roles: string[];
  quorum: number;
  approvals: number;
  can_decide: boolean;
  cost_usd: number;
  outputs: { step_key: string; excerpt: string; truncated: boolean }[];
  omitted_outputs: number;
};

const base = '/api/v1/workflows/dag-approvals';
export const listDagApprovals = (department_id: string, after: string | undefined, signal: AbortSignal, view: ApprovalView, execution_id?: string) =>
  api.get<{ items: DagApproval[]; next_after: string | null }>(base, { params: { department_id, after, view, execution_id }, signal });
export type TerminalApprovalSummary = {
  id: string;
  execution_id: string;
  workflow_id: string;
  workflow_name: string;
  status: string;
  expires_at: string;
  resolved_at: string | null;
  created_at: string;
};

export const listTerminalApprovals = (department_id: string, after: string | undefined, signal: AbortSignal, view: ApprovalView, execution_id?: string) =>
  api.get<{ items: TerminalApprovalSummary[]; next_after: string | null }>(base, {
    params: { department_id, after, view, execution_id, kind: 'terminal' }, signal,
  });

export const decideDagApproval = (department_id: string, id: string, approve: boolean, signal: AbortSignal) =>
  api.post<{ status: 'PENDING' | 'APPROVED' | 'REJECTED' | 'TIMED_OUT' }>(
    `${base}/${encodeURIComponent(id)}/decision`, { approve }, { params: { department_id }, signal },
  );
