import { api } from './httpClient';
import type { ApprovalRequest, ApprovalResponseDto } from '../types/scheduler';

// Approvals & Human-In-The-Loop
export const getPendingApprovals = (params?: { agent_id?: string; target_approver_id?: string }) =>
  api.get<ApprovalRequest[]>('/api/v1/approvals/pending', { params });
export const createApprovalRequest = (data: any) => api.post<ApprovalRequest>('/api/v1/approvals/', data);
export const respondToApproval = (data: ApprovalResponseDto) => api.post('/api/v1/approvals/respond', data);
