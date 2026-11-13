import type { PlatformWorkflow } from '../../types/mcp';

export interface RepositoryWorkspaceConfig {
  connector_id: string;
  repository: string;
  mode: 'read' | 'write';
  ref?: string | null;
  pr_title?: string | null;
}

export interface DagApprovalPolicy {
  approver_roles?: ('OPERATOR' | 'MANAGER' | 'ORG_ADMIN')[];
  timeout_seconds?: number;
  quorum?: number;
}

export interface WorkflowStep {
  key: string;
  name: string;
  agent_id: string;
  prompt_template: string;
  depends_on: string[];
  timeout_seconds?: number;
  mcp_servers?: string[];
  skills?: string[];
  params?: { workspace?: RepositoryWorkspaceConfig; required_outcome?: 'pull_request';
    agentId?: string; dag_approval?: DagApprovalPolicy; [key: string]: unknown };
}

export interface AttachedSkill {
  id: string;
  name: string;
  source: string; // 'git' | 'local' | 'builtin' | 'custom'
  location?: string; // Git repo url or local directory/file path
  description?: string;
  content?: string;
}

export interface CreateWorkflowModalProps {
  open: boolean;
  onClose: () => void;
  onSuccess: (workflow: PlatformWorkflow) => void;
  defaultChannelProvider?: string;
  defaultChannelId?: string;
  departmentId?: string;
  workflow?: PlatformWorkflow | null;
}

