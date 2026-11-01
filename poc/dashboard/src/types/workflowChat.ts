export interface ChatResourceRef {
  connector_id: string;
  repository?: string | null;
  channel_id?: string | null;
  tool_name?: string | null;
}
export interface ChatWorkflow {
  skills?: string[];
  name: string;
  description: string;
  steps: Array<{
    key: string; name: string; agent_id: string; prompt_template: string;
    depends_on: string[]; resources: ChatResourceRef[]; timeout_seconds: number;
    send_output_of?: string | null;
    skills?: string[];
  }>;
  destination: { connector_id: string; channel_id: string } | null;
  cron_expression: string | null;
}
export interface WorkflowChatContext {
  departments: Array<{ id: string; name: string }>;
  selection: { provider_id: string; model_id: string; cost_source: string } | null;
  catalog: {
    agents: Array<{ id: string; name: string; provision_on_create?: boolean; connector_tools: Record<string, string[]> }>;
    connectors: Array<{ id: string; name: string; provider: string;
      tools: string[]; repositories: string[]; channels: string[]; channel_labels?: Record<string, string>; execution_supported: boolean }>;
    skills?: Array<{ id: string; name: string; plugin: string; description: string }>;
    note: string;
  } | null;
}
export interface WorkflowChatMessage { role: 'user' | 'assistant'; content: string }
export interface WorkflowChatJob {
  id: string;
  status: 'GENERATING' | 'READY' | 'FAILED' | 'CANCELLED' | 'CREATING' | 'CREATED';
  department_id: string;
  messages: WorkflowChatMessage[];
  previous_workflow: ChatWorkflow | null;
  result: { message: string; workflow: ChatWorkflow | null; errors: string[]; ready: boolean } | null;
  error: string | null;
  model: string;
  provider: string;
  workflow_id: string | null;
}
export interface WorkflowChatRequest {
  request_id: string; department_id: string; messages: WorkflowChatMessage[];
  previous_workflow?: ChatWorkflow | null; locale: 'en' | 'he';
}
