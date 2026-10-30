import type { Agent } from '../../types/agent';
import type { Task } from '../../types/task';

export interface AgentDeskDrawerProps {
  agent: Agent | null;
  tasks: Task[];
  visible: boolean;
  onClose: () => void;
  onTaskCreated: () => void;
  agents?: Agent[];
}
