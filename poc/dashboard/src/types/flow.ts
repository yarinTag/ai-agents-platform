import { Agent } from './agent';
import { Task } from './task';

export interface FlowNode {
  id: string;
  agent: Agent;
  status: 'idle' | 'active' | 'waiting' | 'error';
  currentTask?: Task | null;
  progress?: number;
  x: number;
  y: number;
}

export interface FlowConnection {
  fromId: string;
  toId: string;
  label?: string;
  active?: boolean;
}

export interface ActivityEvent {
  type: string;
  action: string;
  description: string;
  timestamp: string;
  entity_id: string;
  entity_type: string;
  agent_id?: string;
  project_id?: string;
}
