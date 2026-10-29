import type { Agent } from '../../types/agent';
import type { Task } from '../../types/task';

export interface OfficeRightSidebarProps {
  agents: Agent[];
  tasks: Task[];
  onTaskCreated: () => void;
  onSelectDepartment?: (dept: string) => void;
  onSelectAgent?: (agent: Agent) => void;
}

export interface DepartmentOption {
  key: string;
  name: string;
  color: string;
  suggestions: string[];
}
