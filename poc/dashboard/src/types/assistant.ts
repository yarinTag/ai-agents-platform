export interface AuthoringTool { connector_id: string; tool_name: string }
export interface AuthoringRepository { connector_id: string; repository: string }
export interface AuthoringChannel { connector_id: string; channel_id: string }
export interface AuthoringStep {
  key: string; name: string; agent_id: string; prompt_template: string;
  depends_on: string[]; tools: AuthoringTool[]; repositories: AuthoringRepository[];
  channels: AuthoringChannel[]; skills: string[]; requires_approval: boolean; timeout_seconds: number;
}
export interface WorkflowProposal {
  name: string; description: string;
  trigger: { kind: 'manual' | 'webhook' | 'cron' | 'channel' | 'repository';
    connector_id?: string | null; repository?: string | null; channel_id?: string | null;
    event?: string | null; cron_expression?: string | null };
  steps: AuthoringStep[]; unresolved_requirements: string[];
}
export interface ProposalValidation {
  valid: boolean; status: 'READY_FOR_REVIEW' | 'BLOCKED' | 'NEEDS_CLARIFICATION';
  errors: Array<{ code: string; path: string; message: string }>;
  warnings: Array<{ code: string; path: string; message: string }>;
  catalog_version: string; proposal_hash: string;
}
export interface AssistantContext {
  user: { id: string; name: string; role: string }; organization_id: string;
  departments: Array<{ id: string; name: string; can_write_drafts: boolean }>;
  supports_generation: boolean; supports_activation: boolean;
  authoring_models: Array<{ model_id: string; provider_id: string; name: string }>;
}
export interface AssistantCatalog {
  department_id: string; can_write_drafts: boolean;
  agents: Array<{ id: string; name: string; model: string; skills: string[]; tools: AuthoringTool[] }>;
  connectors: Array<{ id: string; name: string; provider: string; available: boolean;
    tools: Array<{ id: string; name: string }>; channels: string[]; repositories: string[] }>;
  limitations: string[]; catalog_version: string;
}
export interface WorkflowArtifact {
  definition_yaml: string | null; definition_json: Record<string, unknown> | null;
  workflow_schema_version: number; yaml_error: string | null;
}
export interface AssistantDraft extends WorkflowArtifact {
  id: string; department_id: string; revision: number; status: string; saved_status: string;
  intent_text: string; proposal: WorkflowProposal; validation: ProposalValidation; executable: false;
}
export interface AssistantMessage { role: 'user' | 'assistant'; content: string }
export interface GenerationRequest {
  department_id: string; model_id: string; provider_id: string; locale: 'en' | 'he'; intent_text: string;
  messages: AssistantMessage[]; previous_proposal?: WorkflowProposal;
  draft_id?: string; expected_draft_revision?: number;
}
export interface AssistantGeneration {
  id: string; status: 'QUEUED' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'CANCELLED';
  request: GenerationRequest; department_id: string;
  result: { assistant_message: string; questions: string[]; validation_id?: string | null; proposal: WorkflowProposal | null;
    validation: ProposalValidation | null } & Partial<WorkflowArtifact> | null;
  error_code: string | null; error_message: string | null;
  saved_draft_id: string | null; saved_draft_revision: number | null;
  input_tokens: number; output_tokens: number; cost_usd: number | null;
  model: string | null; cost_source: string | null;
  tool_calls: Array<{ tool_name: string; created_at: string }>;
}
export interface AssistantErrorBody {
  detail?: string | { code?: string; message?: string; validation?: ProposalValidation };
}
