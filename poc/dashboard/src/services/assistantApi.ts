import { api } from './httpClient';

// Permission-aware workflow authoring (never cached across requests).
export const getAssistantContext = () => api.get<import('../types/assistant').AssistantContext>('/api/v1/workflow-assistant/context');
export const getAssistantCatalog = (departmentId: string) => api.get<import('../types/assistant').AssistantCatalog>('/api/v1/workflow-assistant/catalog', { params: { department_id: departmentId } });
export const getAssistantDrafts = (departmentId: string) => api.get<import('../types/assistant').AssistantDraft[]>('/api/v1/workflow-assistant/drafts', { params: { department_id: departmentId, limit: 100 } });
export const getAssistantDraft = (id: string) => api.get<import('../types/assistant').AssistantDraft>(`/api/v1/workflow-assistant/drafts/${id}`);
export const validateAssistantProposal = (departmentId: string, proposal: import('../types/assistant').WorkflowProposal) =>
  api.post<import('../types/assistant').ProposalValidation>('/api/v1/workflow-assistant/validate', { department_id: departmentId, proposal });
export const createAssistantGeneration = (request: import('../types/assistant').GenerationRequest, key: string) =>
  api.post<import('../types/assistant').AssistantGeneration>('/api/v1/workflow-assistant/generations', request, { headers: { 'Idempotency-Key': key } });
export const getAssistantGeneration = (id: string) => api.get<import('../types/assistant').AssistantGeneration>(`/api/v1/workflow-assistant/generations/${id}`);
export const cancelAssistantGeneration = (id: string) => api.post<import('../types/assistant').AssistantGeneration>(`/api/v1/workflow-assistant/generations/${id}/cancel`);
export const saveAssistantGeneration = (id: string, saveBlocked: boolean) => api.post<import('../types/assistant').AssistantDraft>(`/api/v1/workflow-assistant/generations/${id}/save-draft`, { save_blocked: saveBlocked });

export const getAssistantDraftHistory = (id: string) => api.get<Array<{ revision: number; actor_label: string; created_at: string; snapshot: { proposal: import('../types/assistant').WorkflowProposal; status: string; definition_yaml?: string | null } }>>(`/api/v1/workflow-assistant/drafts/${id}/revisions`);

export const getAssistantWorkflowSchema = () => api.get<{ workflow_schema_version: number; yaml_schema: string }>('/api/v1/workflow-assistant/workflow-schema');
export const validateAssistantYaml = (departmentId: string, yamlContent: string) => api.post<import('../types/assistant').WorkflowArtifact & { proposal: import('../types/assistant').WorkflowProposal; validation: import('../types/assistant').ProposalValidation }>('/api/v1/workflow-assistant/validate-yaml', { department_id: departmentId, yaml_content: yamlContent });
