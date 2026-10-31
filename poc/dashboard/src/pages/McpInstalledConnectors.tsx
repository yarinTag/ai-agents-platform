import { useConnectorResourceText } from '../i18n/connectorResources';
import { ResourceSection } from './ResourceSection';
import { Card, Row, Col, Tag, Button, Badge, Popconfirm } from 'antd';
import { ApiOutlined, SettingOutlined, SafetyCertificateOutlined, DeleteOutlined, ToolOutlined, ThunderboltOutlined } from '@ant-design/icons';
import type { useMcpPage } from './useMcpPage';

export const McpInstalledConnectors = (model: Pick<
  ReturnType<typeof useMcpPage>,
  | 'loading'
  | 'catalog'
  | 'resourceErrors'
  | 'loadData'
  | 'connectors'
  | 'agents'
  | 'permissions'
  | 'testingMap'
  | 'testingChannelMap'
  | 'handleTestChannelMessage'
  | 'handleOpenConnect'
  | 'handleTestConnection'
  | 'handleUninstall'
  | 'handleOpenToolsDrawer'
  | 'handleOpenPermissions'
  | 'getProviderIcon'
>) => {
  const {
    loading,
    catalog,
    resourceErrors,
    loadData,
    connectors,
    agents,
    permissions,
    testingMap, testingChannelMap, handleTestChannelMessage,
    handleOpenConnect,
    handleTestConnection,
    handleUninstall,
    handleOpenToolsDrawer,
    handleOpenPermissions,
    getProviderIcon,
  } = model;
  const text = useConnectorResourceText();
  return (<>
    <ResourceSection error={resourceErrors.permissions || resourceErrors.agents} onRetry={loadData}><span /></ResourceSection>
              <div>
                {connectors.length === 0 ? (
                  <Card style={{ background: '#161b22', borderColor: '#30363d', textAlign: 'center', padding: '40px' }}>
                    <ApiOutlined style={{ fontSize: '42px', color: '#6e7681', marginBottom: '12px' }} />
                    <h3 style={{ color: '#f0f6fc' }}>No MCP Connectors Installed Yet</h3>
                    <p style={{ color: '#8b949e', maxWidth: '400px', margin: '0 auto 20px auto' }}>
                      Go to the marketplace tab to install Git, Trello, Telegram, or Slack connectors for your agents.
                    </p>
                  </Card>
                ) : (
                  <Row gutter={[16, 16]}>
                    {connectors.map((conn) => {
                      const isConnected = conn.status === 'CONNECTED';
                      const catDef = catalog.find((c) => c.provider === conn.provider || c.id === conn.id);
                      const permittedAgentCount = permissions.filter((p) => p.connector_id === conn.id).length;

                      const isGit = conn.provider === 'github' || conn.provider === 'git' || conn.provider === 'gitlab';
                      const isSlack = conn.provider === 'slack';
                      const isTelegram = conn.provider === 'telegram';
                      const allowedRepos: string[] = conn.configuration?.allowed_repos || [];
                      const allowedChannels: string[] = conn.configuration?.allowed_channels || [];

                      return (
                        <Col xs={24} md={12} lg={8} key={conn.id}>
                          <Card
                            style={{
                              background: '#161b22',
                              border: '1px solid #30363d',
                              borderRadius: '12px',
                              boxShadow: '0 4px 20px rgba(0,0,0,0.3)',
                            }}
                          >
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '12px' }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                                <div
                                  style={{
                                    width: '42px',
                                    height: '42px',
                                    borderRadius: '8px',
                                    background: '#0d1117',
                                    border: '1px solid #30363d',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                  }}
                                >
                                  {getProviderIcon(conn.provider, 22)}
                                </div>
                                <div>
                                  <div style={{ fontSize: '16px', fontWeight: 700, color: '#f0f6fc' }}>
                                    {conn.name}
                                  </div>
                                  <div style={{ fontSize: '11px', color: '#8b949e' }}>
                                    ID: <code style={{ color: '#38bdf8' }}>{conn.id}</code>
                                  </div>
                                </div>
                              </div>

                              <Badge
                                status={isConnected ? 'success' : 'error'}
                                text={
                                  <span style={{ fontSize: '12px', fontWeight: 600, color: isConnected ? '#52c41a' : '#ff4d4f' }}>
                                    {conn.status}
                                  </span>
                                }
                              />
                            </div>

                            {/* Config preview */}
                            <div
                              style={{
                                background: '#0d1117',
                                borderRadius: '8px',
                                padding: '10px',
                                marginBottom: '14px',
                                fontSize: '12px',
                                border: '1px solid #21262d',
                              }}
                            >
                              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                                <span style={{ color: '#8b949e' }}>Exposed Tools:</span>
                                <span style={{ color: '#34d399', fontWeight: 600 }}>{conn.tools_count || 0} registered</span>
                              </div>
                              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
                                <span style={{ color: '#8b949e' }}>Authorized Agents:</span>
                                <span style={{ color: '#60a5fa', fontWeight: 600 }}>
                                  {resourceErrors.permissions ? 'Unavailable' : permittedAgentCount > 0 ? `${permittedAgentCount} agents` : 'All (Default)'}
                                </span>
                              </div>

                              {/* Allowed Repos */}
                              {isGit && allowedRepos.length > 0 && (
                                <div style={{ marginTop: '6px', paddingTop: '6px', borderTop: '1px solid #21262d' }}>
                                  <div style={{ color: '#38bdf8', fontSize: '11px', fontWeight: 600, marginBottom: '4px' }}>
                                    APPROVED REPOS ({allowedRepos.length}):
                                  </div>
                                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                                    {allowedRepos.map((r) => (
                                      <Tag key={r} color="cyan" style={{ fontSize: '10px' }}>
                                        {r}
                                      </Tag>
                                    ))}
                                  </div>
                                </div>
                              )}

                              {/* Allowed Channels */}
                              {(isSlack || isTelegram) && allowedChannels.length > 0 && (
                                <div style={{ marginTop: '6px', paddingTop: '6px', borderTop: '1px solid #21262d' }}>
                                  <div style={{ color: '#f59e0b', fontSize: '11px', fontWeight: 600, marginBottom: '4px' }}>
                                    APPROVED CHANNELS ({allowedChannels.length}):
                                  </div>
                                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                                    {allowedChannels.map((ch) => (
                                      <div key={ch} title={ch}>
                                      <Tag color="gold" style={{ fontSize: '10px' }}>
                                        {conn.configuration?.channel_labels?.[ch] || ch}
                                      </Tag>
                                      <Button size="small" loading={testingChannelMap[`${conn.id}:${ch}`]}
                                        disabled={!isConnected}
                                        onClick={() => void handleTestChannelMessage(conn.provider, ch, conn.id)}>
                                        {text.sendTest}
                                      </Button>
                                      </div>

                                    ))}
                                  </div>
                                </div>
                              )}
                            </div>

                            {/* Buttons */}
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', justifyContent: 'space-between' }}>
                              <div style={{ display: 'flex', gap: '6px' }}>
                                <Button
                                  size="small"
                                  icon={<ThunderboltOutlined />}
                                  loading={testingMap[conn.id]}
                                  onClick={() => handleTestConnection(conn)}
                                  style={{ background: '#064e3b', borderColor: '#059669', color: '#34d399' }}
                                >
                                  {text.connectionTest}
                                </Button>
                                <Button
                                  size="small"
                                  icon={<ToolOutlined />}
                                  onClick={() => handleOpenToolsDrawer(conn)}
                                  style={{ background: '#1c2128', borderColor: '#30363d', color: '#60a5fa' }}
                                >
                                  Tools
                                </Button>
                                <Button
                                  size="small"
                                  icon={<SafetyCertificateOutlined />}
                                  disabled={Boolean(resourceErrors.permissions || resourceErrors.agents)}
                                  onClick={() => handleOpenPermissions(conn)}
                                  style={{ background: '#1c2128', borderColor: '#30363d', color: '#c084fc' }}
                                >
                                  Access
                                </Button>
                              </div>

                              <div style={{ display: 'flex', gap: '6px' }}>
                                {catDef && (
                                  <Button
                                    size="small"
                                    icon={<SettingOutlined />}
                                    onClick={() => handleOpenConnect(catDef, conn)}
                                    style={{ background: '#1c2128', borderColor: '#30363d', color: '#f0f6fc' }}
                                  />
                                )}
                                <Popconfirm
                                  title="Uninstall this MCP connector?"
                                  description="This will remove the integration and its registered tools."
                                  onConfirm={() => handleUninstall(conn.id)}
                                  okText="Uninstall"
                                  cancelText="Cancel"
                                  okButtonProps={{ danger: true }}
                                >
                                  <Button
                                    size="small"
                                    danger
                                    icon={<DeleteOutlined />}
                                    style={{ background: '#1c2128', borderColor: '#30363d' }}
                                  />
                                </Popconfirm>
                              </div>
                            </div>
                          </Card>
                        </Col>
                      );
                    })}
                  </Row>
                )}
              </div>
  </>);
};
