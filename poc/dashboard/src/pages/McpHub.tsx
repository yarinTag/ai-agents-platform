import { usePermissions } from '../hooks/usePermissions';
import React from 'react';
import { Tag, Button } from 'antd';
import { ApiOutlined, SyncOutlined, PlusOutlined } from '@ant-design/icons';
import { McpDepartmentTools } from './McpDepartmentTools';
import { useMcpPage } from './useMcpPage';
import { McpConnectorModal } from './McpConnectorModal';
import { McpHubTabs } from './McpHubTabs';
import { McpCustomConnectorModal } from './McpCustomConnectorModal';
import { McpToolsDrawer } from './McpToolsDrawer';
import { McpPermissionsModal } from './McpPermissionsModal';

export const McpHubPage: React.FC = () => {
  const { isAdmin } = usePermissions();
  return isAdmin ? <McpAdminHub /> : <McpDepartmentTools />;
};

const McpAdminHub: React.FC = () => {
  const model = useMcpPage();
  const { loading, resourceErrors, setCustomModalVisible, customForm, loadData } = model;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Hero Header */}
      <div
        style={{
          background: 'radial-gradient(ellipse at top left, #1e1b4b 0%, #0d1117 70%)',
          borderRadius: '16px',
          border: '1px solid #30363d',
          padding: '24px 32px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
            <span
              style={{
                background: 'linear-gradient(135deg, #10b981 0%, #3b82f6 100%)',
                padding: '8px',
                borderRadius: '10px',
                display: 'inline-flex',
                color: '#fff',
                fontSize: '20px',
              }}
            >
              <ApiOutlined />
            </span>
            <h1 style={{ margin: 0, fontSize: '26px', fontWeight: 800, color: '#f0f6fc' }}>
              MCP Integrations Hub
            </h1>
            <Tag color="#10b981" style={{ borderRadius: '12px', fontWeight: 600 }}>
              Model Context Protocol
            </Tag>
          </div>
          <p style={{ margin: 0, color: '#8b949e', fontSize: '14px', maxWidth: '720px' }}>
            Connect <strong>Git Repositories</strong>, <strong>Slack Channels</strong>, <strong>Telegram Chats</strong>, and custom MCP servers to equip your autonomous agents with external tools and authorized resources.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
          <Button
            icon={<SyncOutlined spin={loading} />}
            onClick={loadData}
            style={{ background: '#161b22', borderColor: '#30363d', color: '#f0f6fc' }}
          >
            Refresh
          </Button>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            disabled={loading || Boolean(resourceErrors.connectors)}
            onClick={() => {
              customForm.resetFields();
              setCustomModalVisible(true);
            }}
            style={{
              background: '#10b981',
              borderColor: '#10b981',
              fontWeight: 600,
              boxShadow: '0 4px 14px rgba(16, 185, 129, 0.4)',
            }}
          >
            Add Custom MCP
          </Button>
        </div>
      </div>
      <McpHubTabs {...model} />
      <McpConnectorModal {...model} />
      <McpCustomConnectorModal {...model} />
      <McpToolsDrawer {...model} />
      <McpPermissionsModal {...model} />
    </div>
  );
};
export default McpHubPage;
