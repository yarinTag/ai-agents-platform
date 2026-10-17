export type AgentStatus = 'idle' | 'running' | 'thinking' | 'reviewing' | 'error';

export type Department = 'Engineering' | 'Architecture' | 'QA & Testing' | 'Research & Ops';

export type AgentRole = 'ROOT_ORCHESTRATOR' | 'MANAGER' | 'WORKER' | 'SPECIALIST' | 'WORKFLOW_AUTOMATION';

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

  // Workflow automation fields (detached from office floor)
  is_workflow_agent?: boolean;
  workflow_id?: string | null;

  // Enterprise organization & department link
  organization_id?: string | null;
  department_id?: string | null;
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

  // Enterprise organization & department link
  organization_id?: string | null;
  department_id?: string | null;

  parent_id?: string | null;
  role_type?: AgentRole | string;
  max_concurrent_children?: number;
  delegation_strategy?: string;
  allowed_child_ids?: string[];
  allowed_tools?: string[];
  template_id?: string | null;
  /** null/undefined = inherit the platform-default runtime provider */
  runtime_provider?: string | null;
}

export interface AgentUpdateDto extends Partial<AgentCreateDto> {
  organization_id?: string | null;
  department_id?: string | null;
}

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
