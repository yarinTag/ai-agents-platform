import React from 'react';
import { Modal, List, Button } from 'antd';
import { SafetyCertificateOutlined } from '@ant-design/icons';
import { MCPConnector, AgentMCPPermission } from '../../types/mcp';
import { Agent } from '../../types/agent';
import { tokens, modalTokenStyles } from '../../shared/ui';

export interface AgentMcpPermissionsModalProps {
  open: boolean;
  connector: MCPConnector | null;
  agents: Agent[];
  permissions: AgentMCPPermission[];
  updating: boolean;
  onCancel: () => void;
  onTogglePermission: (agentId: string, isCurrentlyAllowed: boolean) => void;
}

export const AgentMcpPermissionsModal: React.FC<AgentMcpPermissionsModalProps> = ({
  open,
  connector,
  agents,
  permissions,
  updating,
  onCancel,
  onTogglePermission,
}) => {
  return (
    <Modal
      title={
        <div style={{ display: 'flex', alignItems: 'center', gap: tokens.spacing.sm }}>
          <SafetyCertificateOutlined style={{ color: tokens.colors.accent.purple }} />
          <span>Agent Access Control — {connector?.name}</span>
        </div>
      }
      open={open}
      onCancel={onCancel}
      footer={null}
      width={500}
      styles={modalTokenStyles}
    >
      <div style={{ padding: `${tokens.spacing.sm} 0` }}>
        <p
          style={{
            color: tokens.colors.text.secondary,
            fontSize: tokens.typography.size.sm,
            marginBottom: tokens.spacing.lg,
          }}
        >
          Control which agents are authorized to invoke tools from this MCP connector.
        </p>

        <List
          dataSource={agents}
          renderItem={(agent) => {
            const isAllowed = permissions.some(
              (p) => p.agent_id === agent.id && p.connector_id === connector?.id
            );

            return (
              <List.Item
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: `${tokens.spacing.sm} ${tokens.spacing.md}`,
                  background: tokens.colors.bg.primary,
                  borderRadius: tokens.radii.md,
                  border: `1px solid ${tokens.colors.border.subtle}`,
                  marginBottom: tokens.spacing.sm,
                }}
              >
                <div>
                  <div
                    style={{
                      color: tokens.colors.text.primary,
                      fontWeight: tokens.typography.weight.semibold,
                      fontSize: tokens.typography.size.md,
                    }}
                  >
                    {agent.name}
                  </div>
                  <div
                    style={{
                      color: tokens.colors.text.secondary,
                      fontSize: tokens.typography.size.xs,
                    }}
                  >
                    {(agent as any).role || agent.name} &bull; {agent.department || 'General'}
                  </div>
                </div>

                <Button
                  size="small"
                  loading={updating}
                  onClick={() => onTogglePermission(agent.id, isAllowed)}
                  style={{
                    background: isAllowed
                      ? tokens.colors.status.successBg
                      : tokens.colors.bg.card,
                    borderColor: isAllowed
                      ? tokens.colors.status.success
                      : tokens.colors.border.default,
                    color: isAllowed
                      ? tokens.colors.status.success
                      : tokens.colors.text.secondary,
                    fontWeight: tokens.typography.weight.semibold,
                  }}
                >
                  {isAllowed ? '✓ Granted' : '+ Grant Access'}
                </Button>
              </List.Item>
            );
          }}
        />
      </div>
    </Modal>
  );
};
