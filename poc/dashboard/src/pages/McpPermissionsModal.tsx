import { Button, Modal, List } from 'antd';
import { SafetyCertificateOutlined } from '@ant-design/icons';
import { Agent } from '../types/agent';
import type { useMcpPage } from './useMcpPage';

export const McpPermissionsModal = (model: Pick<
  ReturnType<typeof useMcpPage>,
  | 'loading'
  | 'agents'
  | 'permissions'
  | 'permModalVisible'
  | 'setPermModalVisible'
  | 'permConnector'
  | 'updatingPerms'
  | 'handleToggleAgentPerm'
>) => {
  const {
    loading,
    agents,
    permissions,
    permModalVisible,
    setPermModalVisible,
    permConnector,
    updatingPerms,
    handleToggleAgentPerm,
  } = model;
  return (<>
      {/* Agent Permissions Modal */}
      <Modal
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <SafetyCertificateOutlined style={{ color: '#c084fc' }} />
            <span>Agent Access Control — {permConnector?.name}</span>
          </div>
        }
        open={permModalVisible}
        onCancel={() => setPermModalVisible(false)}
        footer={null}
        width={500}
      >
        <p style={{ color: '#8b949e', fontSize: '13px', marginBottom: '16px' }}>
            Control which agents are authorized to invoke tools from this MCP connector.
          </p>

          <List
            dataSource={agents}
            renderItem={(agent) => {
              const isAllowed = permissions.some(
                (p) => p.agent_id === agent.id && p.connector_id === permConnector?.id
              );

              return (
                <List.Item
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    padding: '10px 14px',
                    background: '#0d1117',
                    borderRadius: '8px',
                    border: '1px solid #21262d',
                    marginBottom: '8px',
                  }}
                >
                  <div>
                    <div style={{ color: '#f0f6fc', fontWeight: 600, fontSize: '14px' }}>
                      {agent.name}
                    </div>
                    <div style={{ color: '#8b949e', fontSize: '11px' }}>
                      {(agent as any).role || agent.name} &bull; {agent.department || 'General'}
                    </div>
                  </div>

                  <Button
                    size="small"
                    loading={updatingPerms}
                    onClick={() => handleToggleAgentPerm(agent.id, isAllowed)}
                    style={{
                      background: isAllowed ? 'rgba(16, 185, 129, 0.2)' : '#161b22',
                      borderColor: isAllowed ? '#10b981' : '#30363d',
                      color: isAllowed ? '#34d399' : '#8b949e',
                      fontWeight: 600,
                    }}
                  >
                    {isAllowed ? '✓ Granted' : '+ Grant Access'}
                  </Button>
                </List.Item>
              );
            }}
          />
      </Modal>

  </>);
};
