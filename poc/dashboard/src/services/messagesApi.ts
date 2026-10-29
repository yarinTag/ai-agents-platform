import { api } from './httpClient';
import type { AgentMessage } from '../types/mcp';

export const getAgentMessages = (agentId?: string, limit: number = 50) =>
  api.get<AgentMessage[]>('/api/v1/messages', { params: agentId ? { agent_id: agentId, limit } : { limit } });

export const sendAgentMessage = (data: { from_agent_id: string; to_agent_id: string; content: string; message_type?: string; task_id?: string; metadata?: any }) =>
  api.post<AgentMessage>('/api/v1/messages', data);

export const replyAgentMessage = (messageId: string, data: { from_agent_id: string; content: string; message_type?: string; metadata?: any }) =>
  api.post<AgentMessage>(`/api/v1/messages/${messageId}/reply`, data);
