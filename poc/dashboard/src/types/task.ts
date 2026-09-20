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
  parent_task_id?: string | null;
  root_task_id?: string | null;
  assigned_by?: string | null;
  subtasks?: Task[];
}

export interface TaskCreateDto {
  agent_id: string;
  project_id?: string | null;
  skill_id?: string | null;
  input_data: Record<string, any>;
}

export interface TaskDelegateDto {
  target_agent_id: string;
  subtask_prompt: string;
  timeout_seconds?: number;
  project_id?: string;
}

export interface TaskTreeNode {
  id: string;
  run_id: string;
  agent_id: string;
  prompt: string;
  status: string;
  created_at: string;
  started_at?: string | null;
  ended_at?: string | null;
  result?: string | null;
  error?: string | null;
  parent_task_id?: string | null;
  root_task_id?: string | null;
  assigned_by?: string | null;
  children: TaskTreeNode[];
}
