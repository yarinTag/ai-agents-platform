import { usePermissions } from '../hooks/usePermissions';
import { Card, Row, Col, Tag, Button, Input, Spin } from 'antd';
import { CheckCircleOutlined, PlusOutlined, SettingOutlined, ToolOutlined, SearchOutlined, ThunderboltOutlined } from '@ant-design/icons';
import type { useMcpPage } from './useMcpPage';

export const McpMarketplace = (model: Pick<
  ReturnType<typeof useMcpPage>,
  | 'loading'
  | 'connectors'
  | 'searchQuery'
  | 'setSearchQuery'
  | 'selectedCategory'
  | 'setSelectedCategory'
  | 'testingMap'
  | 'handleOpenConnect'
  | 'handleTestConnection'
  | 'handleOpenToolsDrawer'
  | 'categories'
  | 'filteredCatalog'
  | 'getProviderIcon'
>) => {
  const { isAdmin } = usePermissions();
  const {
    loading,
    connectors,
    searchQuery,
    setSearchQuery,
    selectedCategory,
    setSelectedCategory,
    testingMap,
    handleOpenConnect,
    handleTestConnection,
    handleOpenToolsDrawer,
    categories,
    filteredCatalog,
    getProviderIcon,
  } = model;
  return (<>
              <div>
                {/* Search & Filter Bar */}
                <div
                  style={{
                    display: 'flex',
                    flexWrap: 'wrap',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    gap: '16px',
                    marginBottom: '20px',
                  }}
                >
                  <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                    {categories.map((cat) => (
                      <Button
                        key={cat}
                        size="small"
                        onClick={() => setSelectedCategory(cat)}
                        style={{
                          background: selectedCategory === cat ? '#10b981' : '#161b22',
                          borderColor: selectedCategory === cat ? '#10b981' : '#30363d',
                          color: selectedCategory === cat ? '#0a0d12' : '#8b949e',
                          fontWeight: selectedCategory === cat ? 700 : 500,
                          borderRadius: '16px',
                          padding: '0 14px',
                        }}
                      >
                        {cat}
                      </Button>
                    ))}
                  </div>

                  <Input
                    placeholder="Search integrations by name or package..."
                    prefix={<SearchOutlined style={{ color: '#8b949e' }} />}
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    allowClear
                    style={{ width: '320px', background: '#161b22', borderColor: '#30363d', color: '#f0f6fc' }}
                  />
                </div>

                {loading ? (
                  <div style={{ textAlign: 'center', padding: '60px 0' }}>
                    <Spin size="large" />
                  </div>
                ) : (
                  <Row gutter={[16, 16]}>
                    {filteredCatalog.map((item) => {
                      const installed = connectors.find(
                        (c) => c.provider === item.provider || c.id === item.id
                      );

                      const isGit = item.provider === 'github' || item.provider === 'git' || item.provider === 'gitlab';
                      const isSlack = item.provider === 'slack';
                      const isTelegram = item.provider === 'telegram';

                      const allowedRepos: string[] = installed?.configuration?.allowed_repos || [];
                      const allowedChannels: string[] = installed?.configuration?.allowed_channels || [];

                      return (
                        <Col xs={24} sm={12} lg={8} key={item.id}>
                          <Card
                            style={{
                              background: '#161b22',
                              border: installed ? '1px solid #10b981' : '1px solid #30363d',
                              borderRadius: '12px',
                              height: '100%',
                              display: 'flex',
                              flexDirection: 'column',
                              justifyContent: 'space-between',
                              boxShadow: installed ? '0 0 15px rgba(16, 185, 129, 0.15)' : 'none',
                              transition: 'all 0.2s ease',
                            }}
                            styles={{ body: { display: 'flex', flexDirection: 'column', height: '100%' } }}
                          >
                            <div>
                              {/* Header */}
                              <div
                                style={{
                                  display: 'flex',
                                  justifyContent: 'space-between',
                                  alignItems: 'flex-start',
                                  marginBottom: '14px',
                                }}
                              >
                                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                                  <div
                                    style={{
                                      width: '46px',
                                      height: '46px',
                                      borderRadius: '10px',
                                      background: '#0d1117',
                                      border: '1px solid #30363d',
                                      display: 'flex',
                                      alignItems: 'center',
                                      justifyContent: 'center',
                                    }}
                                  >
                                    {getProviderIcon(item.provider, 26)}
                                  </div>
                                  <div>
                                    <div style={{ fontSize: '16px', fontWeight: 700, color: '#f0f6fc' }}>
                                      {item.name}
                                    </div>
                                    <Tag
                                      color="blue"
                                      style={{
                                        fontSize: '10px',
                                        padding: '1px 6px',
                                        margin: '2px 0 0 0',
                                        borderRadius: '6px',
                                        background: 'rgba(59, 130, 246, 0.1)',
                                        borderColor: 'rgba(59, 130, 246, 0.3)',
                                      }}
                                    >
                                      {item.category}
                                    </Tag>
                                  </div>
                                </div>

                                {installed ? (
                                  <Tag
                                    color="success"
                                    icon={<CheckCircleOutlined />}
                                    style={{ borderRadius: '12px', padding: '2px 8px' }}
                                  >
                                    Connected
                                  </Tag>
                                ) : (
                                  <Tag style={{ borderRadius: '12px', background: '#21262d', color: '#8b949e', border: 'none' }}>
                                    Available
                                  </Tag>
                                )}
                              </div>

                              {/* Description */}
                              <p
                                style={{
                                  color: '#8b949e',
                                  fontSize: '13px',
                                  lineHeight: '1.5',
                                  minHeight: '40px',
                                  margin: '0 0 12px 0',
                                }}
                              >
                                {item.description}
                              </p>

                              {/* Package Name */}
                              <div
                                style={{
                                  background: '#0d1117',
                                  borderRadius: '6px',
                                  padding: '6px 10px',
                                  fontSize: '11px',
                                  fontFamily: 'monospace',
                                  color: '#a5b4fc',
                                  border: '1px solid #21262d',
                                  marginBottom: '12px',
                                  overflow: 'hidden',
                                  textOverflow: 'ellipsis',
                                  whiteSpace: 'nowrap',
                                }}
                              >
                                📦 {item.package}
                              </div>

                              {/* Authorized Repos or Channels Preview */}
                              {installed && isGit && allowedRepos.length > 0 && (
                                <div style={{ marginBottom: '12px', background: '#0d1117', padding: '8px', borderRadius: '6px', border: '1px solid #21262d' }}>
                                  <div style={{ fontSize: '11px', fontWeight: 600, color: '#38bdf8', marginBottom: '4px' }}>
                                    ✓ AUTHORIZED REPOSITORIES ({allowedRepos.length})
                                  </div>
                                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                                    {allowedRepos.slice(0, 3).map((repo) => (
                                      <Tag key={repo} color="cyan" style={{ fontSize: '10px' }}>
                                        {repo}
                                      </Tag>
                                    ))}
                                    {allowedRepos.length > 3 && (
                                      <span style={{ fontSize: '10px', color: '#8b949e' }}>+{allowedRepos.length - 3} more</span>
                                    )}
                                  </div>
                                </div>
                              )}

                              {installed && (isSlack || isTelegram) && allowedChannels.length > 0 && (
                                <div style={{ marginBottom: '12px', background: '#0d1117', padding: '8px', borderRadius: '6px', border: '1px solid #21262d' }}>
                                  <div style={{ fontSize: '11px', fontWeight: 600, color: '#f59e0b', marginBottom: '4px' }}>
                                    ✓ AUTHORIZED CHANNELS ({allowedChannels.length})
                                  </div>
                                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                                    {allowedChannels.slice(0, 3).map((ch) => (
                                      <Tag key={ch} color="gold" style={{ fontSize: '10px' }}>
                                        {ch}
                                      </Tag>
                                    ))}
                                  </div>
                                </div>
                              )}

                              {/* Sample Tools preview */}
                              <div style={{ marginBottom: '16px' }}>
                                <div style={{ fontSize: '11px', fontWeight: 600, color: '#6e7681', marginBottom: '6px' }}>
                                  EXPOSED MCP TOOLS ({item.default_tools.length})
                                </div>
                                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                                  {item.default_tools.slice(0, 3).map((t) => (
                                    <Tag
                                      key={t.name}
                                      style={{
                                        fontSize: '11px',
                                        background: '#1c2128',
                                        borderColor: '#30363d',
                                        color: '#34d399',
                                        borderRadius: '4px',
                                      }}
                                    >
                                      {t.name}
                                    </Tag>
                                  ))}
                                  {item.default_tools.length > 3 && (
                                    <Tag style={{ fontSize: '10px', background: '#161b22', border: 'none', color: '#8b949e' }}>
                                      +{item.default_tools.length - 3} more
                                    </Tag>
                                  )}
                                </div>
                              </div>
                            </div>

                            {/* Actions Footer */}
                            <div
                              style={{
                                borderTop: '1px solid #21262d',
                                paddingTop: '12px',
                                display: 'flex',
                                justifyContent: 'space-between',
                                alignItems: 'center',
                              }}
                            >
                              {installed ? (
                                <>
                                  <Button
                                    size="small"
                                    icon={<SettingOutlined />}
                                    disabled={!isAdmin} onClick={() => handleOpenConnect(item, installed)}
                                    style={{ background: '#1c2128', borderColor: '#30363d', color: '#f0f6fc' }}
                                  >
                                    Configure
                                  </Button>
                                  <div style={{ display: 'flex', gap: '8px' }}>
                                    <Button
                                      size="small"
                                      icon={<ThunderboltOutlined />}
                                      loading={testingMap[installed.id]}
                                      disabled={!isAdmin} onClick={() => handleTestConnection(installed)}
                                      style={{ background: '#064e3b', borderColor: '#059669', color: '#34d399' }}
                                    >
                                      Ping
                                    </Button>
                                    <Button
                                      size="small"
                                      icon={<ToolOutlined />}
                                      onClick={() => handleOpenToolsDrawer(installed)}
                                      style={{ background: '#1c2128', borderColor: '#30363d', color: '#60a5fa' }}
                                    >
                                      Tools
                                    </Button>
                                  </div>
                                </>
                              ) : (
                                <Button
                                  type="primary"
                                  block
                                  icon={<PlusOutlined />}
                                  disabled={!isAdmin} onClick={() => handleOpenConnect(item)}
                                  style={{
                                    background: '#10b981',
                                    borderColor: '#10b981',
                                    fontWeight: 600,
                                  }}
                                >
                                  Connect Integration
                                </Button>
                              )}
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
