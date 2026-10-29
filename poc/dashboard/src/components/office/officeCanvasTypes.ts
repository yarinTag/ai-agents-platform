import type { Agent } from '../../types/agent';
import type { Task } from '../../types/task';

export interface AgentsOfficeV3CanvasProps {
  agents: Agent[];
  tasks: Task[];
  onSelectAgent: (agent: Agent) => void;
  onSelectDepartment?: (dept: string) => void;
  onTaskCreated?: () => void;
}

export interface DeskDef {
  title: string;
  isLead?: boolean;
  relX: number; // offset from platform center in px
  relY: number;
  agentId?: string;
}

export interface DepartmentDef {
  key: string;
  name: string;
  dotColor: string;
  stat1Label: string;
  stat2Label: string;
  posX: number;
  posY: number;
  desks: DeskDef[];
}
