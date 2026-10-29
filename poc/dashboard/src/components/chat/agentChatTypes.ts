import type { Agent } from '../../types/agent';
import type { Task } from '../../types/task';

export interface AgentMiniChatDrawerProps {
  agent: Agent | null;
  tasks?: Task[];
  visible: boolean;
  onClose: () => void;
  onTaskDispatched?: () => void;
}
