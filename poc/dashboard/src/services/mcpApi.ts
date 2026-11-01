import { api } from './httpClient';
import type { MCPConnector, MCPTool, MCPCatalogItem, AgentMCPPermission } from '../types/mcp';

// Model Context Protocol (MCP) Hub
export const getMCPCatalog = () =>
  api.get<{ catalog: MCPCatalogItem[] }>('/api/v1/mcp/catalog');

export const getMCPConnectors = () =>
  api.get<{ connectors: MCPConnector[] }>('/api/v1/mcp/connectors');

export const getMCPConnector = (id: string) =>
  api.get<MCPConnector & { tools: MCPTool[] }>(`/api/v1/mcp/connectors/${id}`);

export const installMCPConnector = (data: {
  id?: string;
  name: string;
  provider: string;
  configuration: Record<string, any>;
  capabilities?: string[];
  custom_command?: string;
}) => api.post<MCPConnector>('/api/v1/mcp/connectors', data);

export const updateMCPConnector = (id: string, data: Partial<MCPConnector>) =>
  api.put<MCPConnector>(`/api/v1/mcp/connectors/${id}`, data);

export const deleteMCPConnector = (id: string) =>
  api.delete<{ status: string; message: string }>(`/api/v1/mcp/connectors/${id}`);

export const testMCPConnector = (id: string) =>
  api.post<{ status: string; connector_id: string; message: string; tools_discovered: number; timestamp: string }>(
    `/api/v1/mcp/connectors/${id}/test`
  );

export const getMCPTools = (connectorId: string) =>
  api.get<{ tools: MCPTool[] }>(`/api/v1/mcp/connectors/${connectorId}/tools`);

export const getMCPPermissions = (agentId?: string) =>
  api.get<{ permissions: AgentMCPPermission[] }>('/api/v1/mcp/permissions', { params: agentId ? { agent_id: agentId } : {} });

export const grantMCPPermission = (data: { agent_id: string; connector_id: string; tool_id?: string | null }) =>
  api.post('/api/v1/mcp/permissions/grant', data);

export const revokeMCPPermission = (data: { agent_id: string; connector_id: string; tool_id?: string | null }) =>
  api.post('/api/v1/mcp/permissions/revoke', data);

export const discoverMCPResources = (provider: string, token?: string, configuration?: any, connectorId?: string) =>
  api.post<{ provider: string; repositories?: any[]; channels?: any[]; chats?: any[]; requires_token?: boolean; message?: string }>('/api/v1/mcp/discover-resources', {
    provider,
    token,
    configuration,
    connector_id: connectorId,
  }, provider === 'telegram' ? { timeout: 20000 } : undefined);

export const testChannelMessage = (data: { provider: string; connector_id?: string; channel_id: string; message: string }) =>
  api.post<{ status: string; delivery: string; channel_id: string; delivered_channel_id: string; provider_message_id: string; timestamp: string }>('/api/v1/mcp/test-channel-message', data);
