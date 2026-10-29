import type { Agent } from '../../types/agent';
import type { Task } from '../../types/task';

export interface WarRoomModalProps {
  open: boolean;
  onClose: () => void;
  agents: any[];
  projectId?: string;
}
