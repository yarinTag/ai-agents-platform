export type ConcurrencyPolicy = 'SKIP' | 'COALESCE' | 'ALLOW';
export type MisfirePolicy = 'RUN_ONCE' | 'SKIP';

export interface ScheduledJob {
  id: string;
  name: string;
  description?: string;
  cron_expression: string;
  agent_id: string;
  project_id?: string | null;
  prompt: string;
  input_data?: Record<string, any> | null;
  enabled: boolean;
  concurrency_policy: ConcurrencyPolicy;
  misfire_policy: MisfirePolicy;
  timezone: string;
  last_run_at?: string | null;
  last_run_id?: string | null;
  last_status?: 'RUNNING' | 'SUCCESS' | 'FAILED' | 'SKIPPED' | null;
  next_run_at: string;
  created_at: string;
  updated_at: string;
}

export interface ScheduledJobCreateDto {
  name: string;
  description?: string;
  cron_expression: string;
  agent_id: string;
  project_id?: string | null;
  prompt: string;
  input_data?: Record<string, any>;
  enabled?: boolean;
  concurrency_policy?: ConcurrencyPolicy;
}

export interface ApprovalRequest {
  id: string;
  task_id: string;
  requester_agent_id: string;
  target_approver_id: string;
  interaction_type: 'QUESTION' | 'PERMISSION_APPROVAL' | 'REVIEW';
  title: string;
  content: string;
  context_data?: Record<string, any> | null;
  status: 'PENDING' | 'RESOLVED' | 'REJECTED' | 'CANCELLED';
  resolution_response?: string | null;
  resolved_by?: string | null;
  created_at: string;
  resolved_at?: string | null;
}

export interface ApprovalResponseDto {
  interaction_id: string;
  decision: 'approve' | 'reject';
  response_text: string;
  responder?: string;
}
