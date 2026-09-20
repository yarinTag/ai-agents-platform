export type AgentStatus = 'idle' | 'running' | 'thinking' | 'reviewing' | 'error';

export type Department = 'Engineering' | 'Architecture' | 'QA & Testing' | 'Research & Ops';

export interface Agent {
  id: string;
  name: string;
  description?: string;
  system_prompt: string;
  skills: string[];
  model: string;
  effort: string;
  max_tokens: number;
  temperature: number;
  repo_path?: string;
  github_url?: string;
  department?: Department | string;
  avatar?: string;
  status?: AgentStatus;
  current_task?: string;
  desk_id?: number;
  created_at?: string;
  updated_at?: string;
}

export interface AgentCreateDto {
  name: string;
  description?: string;
  system_prompt: string;
  skills?: string[];
  model?: string;
  effort?: string;
  max_tokens?: number;
  temperature?: number;
  repo_path?: string;
  github_url?: string;
  department?: string;
  avatar?: string;
}

export interface AgentUpdateDto extends Partial<AgentCreateDto> {}
