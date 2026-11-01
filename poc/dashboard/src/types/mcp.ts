export interface MCPCatalogField {
  type: 'text' | 'password' | 'number';
  label: string;
  required: boolean;
  placeholder?: string;
  default?: any;
}

export interface MCPCatalogTool {
  name: string;
  description: string;
}

export interface MCPCatalogItem {
  id: string;
  name: string;
  provider: string;
  category: string;
  icon: string;
  description: string;
  package: string;
  config_schema: Record<string, MCPCatalogField>;
  default_tools: MCPCatalogTool[];
}

export interface MCPConnector {
  id: string;
  name: string;
  provider: string;
  connector_type?: string;
  status: 'CONNECTED' | 'CONNECTING' | 'DISCONNECTED' | 'ERROR';
  configuration?: Record<string, any>;
  configuration_masked?: Record<string, any>;
  capabilities?: string[];
  error_message?: string | null;
  tools_count?: number;
  created_at?: string;
  updated_at?: string;
}

export interface MCPTool {
  id: string;
  connector_id: string;
  name: string;
  description?: string;
  input_schema?: Record<string, any>;
  created_at?: string;
}

export interface MCPToolCall {
  id: string;
  connector_id: string;
  tool_name: string;
  agent_id: string;
  task_id?: string;
  input_args?: Record<string, any>;
  output_result?: string;
  status: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED';
  error?: string;
  started_at: string;
  completed_at?: string;
}

export interface AgentMCPPermission {
  id: string;
  agent_id: string;
  agent_name?: string;
  connector_id: string;
  tool_id?: string | null;
  created_at?: string;
}

export interface AgentMessage {
  id: string;
  from_agent_id: string;
  to_agent_id: string;
  content: string;
  task_id?: string;
  run_id?: string;
  parent_message_id?: string;
  message_type: 'QUESTION' | 'ANSWER' | 'REQUEST' | 'DELEGATION' | 'STATUS' | 'RESULT' | 'HANDOFF';
  status: 'SENT' | 'DELIVERED' | 'READ' | 'RESPONDED';
  metadata?: Record<string, any>;
  created_at?: string;
  responded_at?: string;
  replies?: AgentMessage[];
}

export interface AgentTeam {
  id: string;
  name: string;
  manager_agent_id: string;
  project_id?: string;
  description?: string;
  status: string;
  members: Array<{ agent_id: string; role_in_team: string }>;
  created_at?: string;
  updated_at?: string;
}

export interface WorkflowChannelBinding {
  provider: 'slack' | 'telegram';
  connector_id?: string;
  channel_id: string;
  channel_name?: string;
  trigger_enabled: boolean;
  notify_mode: 'COMPLETION_ONLY' | 'START_AND_COMPLETE' | 'EACH_STEP' | 'ON_COMPLETE' | 'ON_FAILURE' | 'ALWAYS' | 'NONE';
  message_template?: string;
}

export interface PlatformWorkflow {
  revision?: number;
  id: string;
  name: string;
  description?: string;
  department_id?: string;
  definition_json: string;
  definition_yaml?: string;
  webhook_enabled: boolean;
  webhook_token?: string;
  cron_expression?: string;
  is_active: boolean;
  channel_binding?: WorkflowChannelBinding;
  created_at?: string;
  updated_at?: string;
}

export interface CostSummary {
  cost_usd: number | null;
  status: string;
  reference_cost_usd?: number | null;
  known_cost_usd?: number;
  complete?: boolean;
  calls?: number;
  input_tokens?: number;
  output_tokens?: number;
}

export interface WorkflowExecution {
  cost_summary?: CostSummary | null;
  step_runs?: Array<{
    id: string;
    step_key: string;
    status: string;
    agent_id?: string;
    task_run_id?: string;
    started_at?: string;
    completed_at?: string;
    error?: string;
    task_status?: string;
    events?: Array<Record<string, unknown>>;
    input_data?: string;
    output_data?: string;
    cost_usd: number;
    cost_summary?: CostSummary | null;
    session_cost_summary?: CostSummary | null;
  }>;

  id: string;
  workflow_id: string;
  trigger_type: string;
  trigger_payload?: string;
  status: string;
  department_id?: string;
  sandbox_path?: string;
  total_input_tokens: number;
  total_output_tokens: number;
  total_cost_usd: number;
  started_at?: string;
  completed_at?: string;
  error_message?: string;
  notification_error?: string | null;
  created_at?: string;
  payload_hash?: string;
  is_deduplicated?: boolean;
  message?: string;
}

export interface WorkflowRevision {
  workflow_id: string;
  revision: number;
  snapshot: Record<string, unknown>;
  changed_fields: string[];
  actor_id?: string | null;
  actor_label: string;
  change_summary?: string | null;
  created_at: string;
}
