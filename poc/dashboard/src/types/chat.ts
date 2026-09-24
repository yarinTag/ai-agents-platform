export type SenderType = 'USER' | 'AGENT' | 'ASSISTANT' | 'SYSTEM';
export type MessageType =
  | 'CHAT'
  | 'THOUGHT'
  | 'TOOL_CALL'
  | 'TOOL_RESULT'
  | 'APPROVAL_REQUEST'
  | 'APPROVAL_RESPONSE';

export interface ChatMessage {
  id: string;
  conversation_id: string;
  agent_id: string;
  task_id?: string | null;
  sender_type: SenderType;
  message_type: MessageType;
  content: string;
  metadata?: Record<string, any> | null;
  created_at: string;
}

export interface Conversation {
  id: string;
  agent_id: string;
  project_id?: string | null;
  title: string;
  claude_session_id?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ChatHistoryResponse {
  conversation: Conversation;
  messages: ChatMessage[];
  tasks?: any[];
}
