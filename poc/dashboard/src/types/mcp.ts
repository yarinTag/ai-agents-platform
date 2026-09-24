export interface MCPConnector {
  id: string;
  name: string;
  description?: string;
  connector_type: string;
  status: 'CONNECTED' | 'CONNECTING' | 'DISCONNECTED' | 'ERROR';
  capabilities?: string[];
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
