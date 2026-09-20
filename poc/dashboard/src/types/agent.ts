export type AgentStatus = 'idle' | 'running' | 'thinking' | 'reviewing' | 'error';

export type Department = 'Engineering' | 'Architecture' | 'QA & Testing' | 'Research & Ops';

export type AgentRole = 'ROOT_ORCHESTRATOR' | 'MANAGER' | 'WORKER' | 'SPECIALIST';

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

  // Hierarchy and delegation fields
  parent_id?: string | null;
  role_type?: AgentRole | string;
  max_concurrent_children?: number;
  delegation_strategy?: string;
  allowed_child_ids?: string[];
  allowed_tools?: string[];
  template_id?: string | null;
  children?: Agent[];
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

  parent_id?: string | null;
  role_type?: AgentRole | string;
  max_concurrent_children?: number;
  delegation_strategy?: string;
  allowed_child_ids?: string[];
  allowed_tools?: string[];
  template_id?: string | null;
}

export interface AgentUpdateDto extends Partial<AgentCreateDto> {}

export interface AgentTemplate {
  id: string;
  name: string;
  description: string;
  role: AgentRole | string;
  system_prompt: string;
  model: string;
  skills: string[];
  tools: string[];
  suggested_children: string[];
  category: string;
  created_at?: string;
  updated_at?: string;
}

export interface TemplateInstantiateDto {
  name: string;
  parent_id?: string | null;
  department?: string;
  repo_path?: string;
  github_url?: string;
  system_prompt_override?: string;
  model_override?: string;
  avatar?: string;
}
