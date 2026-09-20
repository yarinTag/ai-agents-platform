export type TaskStatus = 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';

export interface Task {
  id: string;
  agent_id: string;
  project_id?: string | null;
  skill_id?: string | null;
  status: TaskStatus | string;
  input_data: Record<string, any> | string;
  output_data?: Record<string, any> | string | null;
  created_at: string;
  updated_at?: string;
  ended_at?: string | null;
  run_id?: string;
  error?: string | null;
}

export interface TaskCreateDto {
  agent_id: string;
  project_id?: string | null;
  skill_id?: string | null;
  input_data: Record<string, any>;
}
