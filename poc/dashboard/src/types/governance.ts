export type PolicyEffect = 'allow' | 'deny' | 'require_approval';
export interface PolicyRule {
  id: string;
  capability_id: string;
  capability_version: 1;
  connector_id: string;
  resource_type: string;
  resource_ids: string[];
  effect: PolicyEffect;
  user_ids: string[];
  agent_ids: string[];
  workflow_ids: string[];
  branches: string[];
  not_before: string | null;
  expires_at: string | null;
}
export interface PolicyDocument { schema_version: 1; default: 'inherit' | 'deny'; rules: PolicyRule[] }
export interface ResourceOption {
  capability_id: string; connector_id: string; connector_name: string; resource_type: string; resource_ids: string[];
}
export interface PolicyRecord {
  organization_id: string; scope_type: 'organization' | 'department'; scope_id: string;
  revision: number; document: PolicyDocument; updated_by: string | null; updated_at: string | null;
  resource_options?: ResourceOption[];
}
export interface CapabilityDescriptor {
  id: string; provider: string; operation: string; effect: string; resource_type: string;
  description: string; version: number; implemented: boolean; server_only: boolean; approval_required: boolean;
}
export interface CapabilityDecision {
  decision: 'allowed' | 'denied' | 'requires_approval'; reason: string; non_executable: true;
  policy_revisions: { source: string; scope_type: string; revision: number }[];
}
export interface CapabilityCatalog {
  schema_version: number; department_id: string; non_executable: true;
  entries: {
    connector_id: string; capability: CapabilityDescriptor; provider_verified: boolean; readiness: string;
    resources: { resource_id: string; authoring: CapabilityDecision; execution: CapabilityDecision }[];
  }[];
}
