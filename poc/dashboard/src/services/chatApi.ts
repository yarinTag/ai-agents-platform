import { api } from './httpClient';
import type { ChatHistoryResponse, ChatMessage, AgentSession } from '../types/chat';

// Interactive Agent Mini-Chat


export const getAgentSessions = (agentId: string) =>
  api.get<{ sessions: AgentSession[] }>(`/api/v1/chat/${agentId}/sessions`);

export const createAgentSession = (agentId: string, data?: { title?: string; project_id?: string | null; task_id?: string | null }) =>
  api.post<{ session: AgentSession }>(`/api/v1/chat/${agentId}/sessions`, data || {});

export const activateAgentSession = (agentId: string, conversationId: string) =>
  api.post<{ session: AgentSession }>(`/api/v1/chat/${agentId}/sessions/${conversationId}/activate`);

export const getChatHistory = (agentId: string, conversationId?: string | null, limit: number = 100) =>
  api.get<ChatHistoryResponse>(`/api/v1/chat/${agentId}/messages`, { params: { conversation_id: conversationId, limit } });

export const sendChatMessage = (agentId: string, content: string, projectId?: string | null, conversationId?: string | null) =>
  api.post<{ status: string; task_id?: string; user_message: ChatMessage }>(`/api/v1/chat/${agentId}/messages`, {
    content,
    project_id: projectId,
    conversation_id: conversationId,
  });

export const clearChatHistory = (agentId: string) =>
  api.post<{ status: string }>(`/api/v1/chat/${agentId}/clear`);
