import type { WorkflowStep } from './workflowBuilderTypes';
export interface WorkflowCanvasStep {
  key: string;
  name: string;
  agent_id: string;
  prompt_template: string;
  depends_on: string[];
  timeout_seconds?: number;
  mcp_servers?: string[];
  skills?: string[];
  params?: WorkflowStep['params'];
}

export interface WorkflowCanvasSkill {
  id: string;
  name: string;
  source?: string;
  location?: string;
  description?: string;
}

export interface WorkflowCanvasGraphProps {
  workflowName?: string;
  steps: WorkflowCanvasStep[];
  waitingStepKeys?: readonly string[];
  channelBinding?: {
    provider?: string;
    channel_id?: string;
    channel_name?: string;
    trigger_enabled?: boolean;
    notify_mode?: string;
  };
  skills?: WorkflowCanvasSkill[];
  allowedMcps?: string[];
  onSelectStep?: (step: WorkflowCanvasStep) => void;
  onDeleteStep?: (stepKey: string) => void | Promise<void>;
  height?: number | string;
}

