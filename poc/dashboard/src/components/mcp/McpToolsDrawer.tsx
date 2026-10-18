import React from 'react';
import { Drawer, Spin, List } from 'antd';
import { ToolOutlined } from '@ant-design/icons';
import { MCPConnector, MCPTool } from '../../types/mcp';
import { tokens, StatusBadge } from '../../shared/ui';

export interface McpToolsDrawerProps {
  open: boolean;
  connector: MCPConnector | null;
  loading: boolean;
  tools: MCPTool[];
  onClose: () => void;
}

export const McpToolsDrawer: React.FC<McpToolsDrawerProps> = ({
  open,
  connector,
  loading,
  tools,
  onClose,
}) => {
  return (
    <Drawer
      title={
        <div style={{ display: 'flex', alignItems: 'center', gap: tokens.spacing.sm }}>
          <ToolOutlined style={{ color: tokens.colors.status.success }} />
          <span>Tools exposed by {connector?.name}</span>
        </div>
      }
      placement="right"
      width={480}
      onClose={onClose}
      open={open}
      styles={{
        body: {
          background: tokens.colors.bg.canvas,
          color: tokens.colors.text.primary,
          padding: tokens.spacing.lg,
        },
        header: {
          background: tokens.colors.bg.card,
          borderBottom: `1px solid ${tokens.colors.border.subtle}`,
          color: tokens.colors.text.primary,
        },
      }}
    >
      {loading ? (
        <div style={{ textAlign: 'center', padding: `${tokens.spacing.xxxl} 0` }}>
          <Spin />
        </div>
      ) : tools.length === 0 ? (
        <div
          style={{
            textAlign: 'center',
            padding: `${tokens.spacing.xxxl} 0`,
            color: tokens.colors.text.secondary,
          }}
        >
          No tools registered under this connector.
        </div>
      ) : (
        <List
          dataSource={tools}
          renderItem={(tool) => (
            <List.Item
              style={{
                border: `1px solid ${tokens.colors.border.subtle}`,
                borderRadius: tokens.radii.md,
                background: tokens.colors.bg.card,
                marginBottom: tokens.spacing.sm,
                padding: tokens.spacing.md,
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'flex-start',
              }}
            >
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  width: '100%',
                  alignItems: 'center',
                }}
              >
                <code
                  style={{
                    fontSize: tokens.typography.size.sm,
                    fontWeight: tokens.typography.weight.bold,
                    color: tokens.colors.status.success,
                  }}
                >
                  {tool.name}
                </code>
                <StatusBadge tone="neutral" label="MCP Tool" />
              </div>
              <p
                style={{
                  margin: `${tokens.spacing.xs} 0 0 0`,
                  color: tokens.colors.text.secondary,
                  fontSize: tokens.typography.size.sm,
                }}
              >
                {tool.description || 'No description provided.'}
              </p>
            </List.Item>
          )}
        />
      )}
    </Drawer>
  );
};
