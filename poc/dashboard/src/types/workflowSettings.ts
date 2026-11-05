/** Per-workflow execution settings and write-only secret metadata (`/api/v1/workflows/{id}/settings|secrets`). */
export type ExecutionBackend = 'direct_api' | 'claude_code' | 'codex_cli' | 'antigravity_cli';

export interface ExecutionBackendDescriptor {
  id: ExecutionBackend;
  name: string;
  transport: string;
  implemented: boolean;
  configured?: boolean;
  configuration_error?: string | null;
  requires_container: boolean;
  supports_playground: boolean;
  supports_session_resume?: boolean;
  supports_governed_connectors: boolean;
  credential_provider: string | null;
  unavailable_reason: string | null;
  verification: 'source_contract_only';
}

export type WorkflowMachineSize = 'small' | 'medium' | 'large';

export const WORKFLOW_MACHINE_SIZES: readonly WorkflowMachineSize[] = ['small', 'medium', 'large'];

export interface WorkflowSettingsValues {
  execution_backend?: ExecutionBackend;
  /** null / "default" = platform default; "tier:<name>" = capability tier; otherwise a catalog model ID. */
  model: string | null;
  machine_size: WorkflowMachineSize;
  /** Exact HTTPS hostnames reachable through the egress proxy; empty = no network. */
  network_allowlist: string[];
}

export interface WorkflowMachineSizeSpec {
  cpus: string;
  memory: string;
  pids: string;
}

export type WorkflowSecretKind = 'encrypted' | 'external';

/** Secret metadata only. The API never returns secret values. */
export interface WorkflowSecretSummary {
  name: string;
  kind: WorkflowSecretKind;
  external_ref: string | null;
  created_by: string | null;
  updated_at: string;
}

export interface WorkflowSettingsResponse {
  workflow_id: string;
  revision: number;
  settings: WorkflowSettingsValues;
  settings_error: string | null;
  execution_backends?: ExecutionBackendDescriptor[];
  secrets: WorkflowSecretSummary[];
  can_manage: boolean;
  machine_sizes: Record<WorkflowMachineSize, WorkflowMachineSizeSpec>;
  max_allowed_hosts: number;
}

export interface WorkflowSettingsUpdateRequest {
  settings: {
    execution_backend?: ExecutionBackend;
    model?: string | null;
    machine_size: WorkflowMachineSize;
    network_allowlist: string[];
  };
  expected_revision: number;
  change_summary?: string;
}

/** Exactly one of an encrypted value or an external secret-manager reference. */
export type WorkflowSecretWriteRequest =
  | { value: string; external_ref?: never }
  | { external_ref: string; value?: never };
