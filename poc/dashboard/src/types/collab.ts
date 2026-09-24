export type MemoryCategory = 'ADR' | 'CONVENTION' | 'INSIGHT' | 'LESSON';

export interface ProjectMemory {
  id: string;
  project_id: string;
  category: MemoryCategory;
  title: string;
  content: string;
  tags: string[];
  author_agent_id?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProjectMemoryCreateDto {
  category: MemoryCategory;
  title: string;
  content: string;
  tags?: string[];
  author_agent_id?: string;
}

export type WarRoomStatus = 'GATHERING' | 'DEBATING' | 'CONSENSUS_REACHED' | 'EXECUTING' | 'COMPLETED';
export type WarRoomMessageType = 'PROPOSAL' | 'CRITIQUE' | 'CONSENSUS_VOTE' | 'SUMMARY';

export interface WarRoomSession {
  id: string;
  title: string;
  topic: string;
  project_id?: string | null;
  moderator_agent_id: string;
  participant_agent_ids: string[];
  status: WarRoomStatus;
  synthesized_plan?: string | null;
  created_at: string;
  updated_at: string;
}

export interface WarRoomMessage {
  id: string;
  session_id: string;
  agent_id: string;
  round_number: number;
  message_type: WarRoomMessageType;
  content: string;
  created_at: string;
}

export interface WarRoomDetail {
  session: WarRoomSession;
  messages: WarRoomMessage[];
}

export interface WarRoomCreateDto {
  title: string;
  topic: string;
  project_id?: string;
  moderator_agent_id: string;
  participant_agent_ids: string[];
}

export interface WarRoomMessageCreateDto {
  agent_id: string;
  round_number: number;
  message_type: WarRoomMessageType;
  content: string;
}
