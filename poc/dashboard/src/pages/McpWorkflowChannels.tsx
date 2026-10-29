import { Tag, Button, Tooltip, Popconfirm, Space, Table } from 'antd';
import { SendOutlined, SlackOutlined, DeleteOutlined, ToolOutlined, ThunderboltOutlined, LinkOutlined, MessageOutlined, DisconnectOutlined, RocketOutlined, CaretRightOutlined, ApartmentOutlined, FileTextOutlined } from '@ant-design/icons';
import { PlatformWorkflow } from '../types/mcp';
import { Agent } from '../types/agent';
import type { useMcpPage } from './useMcpPage';

export const McpWorkflowChannels = (model: Pick<
  ReturnType<typeof useMcpPage>,
  | 'resourceErrors'
  | 'departments'
  | 'loading'
  | 'workflows'
  | 'setCreateWfModalVisible'
  | 'setCanvasModalVisible'
  | 'setCanvasWorkflow'
  | 'testingChannelMap'
  | 'runningWfMap'
  | 'handleTestChannelMessage'
  | 'handleOpenBindingModal'
  | 'handleUnbindChannel'
  | 'handleRunWorkflow'
  | 'handleDeleteWorkflow'
>) => {
  const {
    resourceErrors,
    departments,
    loading,
    workflows,
    setCreateWfModalVisible,
    setCanvasModalVisible,
    setCanvasWorkflow,
    testingChannelMap,
    runningWfMap,
    handleTestChannelMessage,
    handleOpenBindingModal,
    handleUnbindChannel,
    handleRunWorkflow,
    handleDeleteWorkflow,
  } = model;
  return (<>
              <div>
                {/* Information banner */}
                <div
                  style={{
                    background: '#161b22',
                    border: '1px solid #30363d',
                    borderRadius: '12px',
                    padding: '16px 20px',
                    marginBottom: '20px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <MessageOutlined style={{ fontSize: '24px', color: '#ECB22E' }} />
                    <div>
                      <div style={{ fontWeight: 700, color: '#f0f6fc', fontSize: '15px' }}>
                        Bind Workflows to Communication Channels (Slack / Telegram)
                      </div>
                      <div style={{ color: '#8b949e', fontSize: '12px' }}>
                        Connected channels can trigger workflows (incoming commands/webhooks) and receive automatic execution reports and status updates.
                      </div>
                    </div>
                  </div>

                  <Button
                    type="primary"
                    icon={<RocketOutlined />}
                    onClick={() => setCreateWfModalVisible(true)}
                    style={{
                      background: 'linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%)',
                      borderColor: '#3b82f6',
                      fontWeight: 700,
                      height: '38px',
                      borderRadius: '8px',
                      boxShadow: '0 4px 12px rgba(37, 99, 235, 0.3)',
                    }}
                  >
                    + Create Workflow (Auto YAML)
                  </Button>
                </div>

                <Table
                  dataSource={workflows}
                  rowKey="id"
                  pagination={false}
                  scroll={{ x: 1650 }}
                  style={{ background: '#161b22', borderRadius: '12px', border: '1px solid #30363d' }}
                  columns={[
                    {
                      title: 'Workflow Name',
                      dataIndex: 'name',
                      key: 'name',
                      width: 230,
                      render: (text: string, record: PlatformWorkflow) => (
                        <div>
                          <div style={{ fontWeight: 700, color: '#f0f6fc' }}>{text}</div>
                          <div style={{ fontSize: '11px', color: '#8b949e' }}>ID: {record.id}</div>
                        </div>
                      ),
                    },
                    {
                      title: 'Department',
                      key: 'department',
                      width: 150,
                      render: (_: any, record: PlatformWorkflow) => {
                        const dept = departments.find((d) => d.id === record.department_id);
                        if (dept) {
                          return (
                            <Tag color="geekblue" style={{ fontSize: '11px', borderRadius: '4px' }}>
                              📁 {dept.name}
                            </Tag>
                          );
                        }
                        if (record.department_id) {
                          return (
                            <Tag style={{ background: '#21262d', color: '#8b949e', fontSize: '11px' }}>
                              {record.department_id}
                            </Tag>
                          );
                        }
                        return <span style={{ color: '#6e7681', fontSize: '11px' }}>Global</span>;
                      },
                    },
                    {
                      title: 'Bound Channel',
                      key: 'channel',
                      width: 160,
                      render: (_: any, record: PlatformWorkflow) => {
                        const b = record.channel_binding;
                        if (!b) {
                          return <Tag style={{ background: '#21262d', color: '#8b949e', border: 'none' }}>None (Unbound)</Tag>;
                        }
                        const isSlack = b.provider === 'slack';
                        return (
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <Tag
                              icon={isSlack ? <SlackOutlined /> : <SendOutlined />}
                              color={isSlack ? 'warning' : 'processing'}
                              style={{ fontWeight: 600, borderRadius: '6px', padding: '2px 8px' }}
                            >
                              {b.channel_id}
                            </Tag>
                          </div>
                        );
                      },
                    },
                    {
                      title: 'Trigger Enabled',
                      key: 'trigger',
                      width: 140,
                      render: (_: any, record: PlatformWorkflow) => {
                        const b = record.channel_binding;
                        if (!b) return <span style={{ color: '#6e7681' }}>-</span>;
                        return b.trigger_enabled ? (
                          <Tag color="success" icon={<ThunderboltOutlined />}>
                            Trigger Active
                          </Tag>
                        ) : (
                          <Tag style={{ background: '#21262d', color: '#8b949e' }}>Disabled</Tag>
                        );
                      },
                    },
                    {
                      title: 'Reporting Mode',
                      key: 'notify',
                      width: 150,
                      render: (_: any, record: PlatformWorkflow) => {
                        const b = record.channel_binding;
                        if (!b) return <span style={{ color: '#6e7681' }}>-</span>;
                        switch (b.notify_mode) {
                          case 'ALWAYS':
                            return <Tag color="cyan">Always</Tag>;
                          case 'ON_COMPLETE':
                            return <Tag color="green">On Complete</Tag>;
                          case 'ON_FAILURE':
                            return <Tag color="red">On Failure</Tag>;
                          default:
                            return <Tag style={{ background: '#21262d', color: '#8b949e' }}>Read Only</Tag>;
                        }
                      },
                    },
                    {
                      title: 'Configured MCP Scope',
                      key: 'mcp_scope',
                      width: 180,
                      render: (_: any, record: PlatformWorkflow) => {
                        let mcps: string[] = [];
                        try {
                          const def = JSON.parse(record.definition_json);
                          mcps = def.mcp_servers || [];
                        } catch (e) {}
                        if (mcps.length === 0) {
                          return <span style={{ color: '#6e7681', fontSize: '11px' }}>All Connectors</span>;
                        }
                        return (
                          <Space size="small" wrap>
                            {mcps.map((m) => (
                              <Tag key={m} color={m === 'github' ? 'purple' : m === 'telegram' ? 'blue' : 'cyan'} style={{ fontSize: '10px', margin: 0 }}>
                                <ToolOutlined /> {m.toUpperCase()}
                              </Tag>
                            ))}
                          </Space>
                        );
                      },
                    },
                    {
                      title: 'Connected Skills',
                      key: 'skills',
                      width: 180,
                      render: (_: any, record: PlatformWorkflow) => {
                        let wfSkills: any[] = [];
                        try {
                          const def = JSON.parse(record.definition_json);
                          wfSkills = def.skills || [];
                        } catch (e) {}
                        if (wfSkills.length === 0) {
                          return <span style={{ color: '#6e7681', fontSize: '11px' }}>None</span>;
                        }
                        return (
                          <Space size="small" wrap>
                            {wfSkills.map((sk: any, idx: number) => (
                              <Tooltip key={sk.id || idx} title={sk.location ? `Location: ${sk.location}` : sk.description}>
                                <Tag color="gold" style={{ fontSize: '10px', margin: 0 }}>
                                  <FileTextOutlined /> {sk.name || sk.id}
                                </Tag>
                              </Tooltip>
                            ))}
                          </Space>
                        );
                      },
                    },
                    {
                      title: 'Dedicated Runner Agent',
                      key: 'runner_agent',
                      width: 190,
                      render: (_: any, record: PlatformWorkflow) => {
                        let runnerAgentId = '';
                        try {
                          const def = JSON.parse(record.definition_json);
                          runnerAgentId = def.runner_agent_id || def.agent_id || `wf-agent-${record.id}`;
                        } catch (e) {
                          runnerAgentId = `wf-agent-${record.id}`;
                        }
                        return (
                          <Tooltip title="Autonomous background agent dedicated to this workflow. Decoupled from office canvas desks.">
                            <Tag color="purple" style={{ fontSize: '11px', padding: '2px 8px', borderRadius: '6px' }}>
                              ⚡ {runnerAgentId}
                            </Tag>
                          </Tooltip>
                        );
                      },
                    },
                    {
                      title: 'Canvas Graph',
                      key: 'canvas',
                      width: 140,
                      render: (_: any, record: PlatformWorkflow) => {
                        let stepsCount = 0;
                        try {
                          const def = JSON.parse(record.definition_json);
                          stepsCount = (def.steps || []).length;
                        } catch (e) {}
                        return (
                          <Button
                            size="small"
                            icon={<ApartmentOutlined />}
                            onClick={() => {
                              setCanvasWorkflow(record);
                              setCanvasModalVisible(true);
                            }}
                            style={{ background: '#1e1b4b', borderColor: '#6366f1', color: '#a5b4fc', fontSize: '11px' }}
                          >
                            🎨 Canvas ({stepsCount})
                          </Button>
                        );
                      },
                    },
                    {
                      title: 'Actions',
                      key: 'actions',
                      width: 270,
                      render: (_: any, record: PlatformWorkflow) => {
                        const b = record.channel_binding;
                        return (
                          <Space>
                            <Button
                              size="small"
                              type="primary"
                              icon={<CaretRightOutlined />}
                              loading={runningWfMap[record.id]}
                              onClick={() => handleRunWorkflow(record)}
                              style={{ background: '#059669', borderColor: '#059669', color: '#fff', fontWeight: 600 }}
                            >
                              Run
                            </Button>

                            <Button
                              size="small"
                              type={b ? 'default' : 'primary'}
                              icon={<LinkOutlined />}
                              disabled={Boolean(resourceErrors.connectors)}
                              onClick={() => handleOpenBindingModal(record)}
                              style={
                                !b
                                  ? { background: '#2563eb', borderColor: '#2563eb' }
                                  : { background: '#1c2128', borderColor: '#30363d', color: '#f0f6fc' }
                              }
                            >
                              {b ? 'Edit Channel' : 'Bind Channel'}
                            </Button>

                            {b && (
                              <>
                                <Button
                                  size="small"
                                  icon={<SendOutlined />}
                                  loading={testingChannelMap[`${b.provider}:${b.channel_id}`]}
                                  disabled={Boolean(resourceErrors.connectors)}
                                  onClick={() => handleTestChannelMessage(b.provider, b.channel_id)}
                                  style={{ background: '#064e3b', borderColor: '#059669', color: '#34d399' }}
                                >
                                  Ping
                                </Button>
                                <Popconfirm
                                  title="Unbind this channel from the workflow?"
                                  description="This will disconnect the channel without deleting the workflow."
                                  onConfirm={() => handleUnbindChannel(record.id)}
                                  okText="Unbind"
                                  cancelText="Cancel"
                                >
                                  <Button
                                    size="small"
                                    icon={<DisconnectOutlined style={{ color: '#f59e0b' }} />}
                                    style={{ background: '#1c2128', borderColor: '#30363d', color: '#f59e0b' }}
                                    title="Unbind Channel"
                                  >
                                    Unbind
                                  </Button>
                                </Popconfirm>
                              </>
                            )}

                            <Popconfirm
                              title="Delete this workflow completely?"
                              description="This will permanently delete the workflow and its run history."
                              onConfirm={() => handleDeleteWorkflow(record.id)}
                              okText="Delete"
                              cancelText="Cancel"
                              okButtonProps={{ danger: true }}
                            >
                              <Button size="small" danger icon={<DeleteOutlined />} title="Delete Workflow" />
                            </Popconfirm>
                          </Space>
                        );
                      },
                    },
                  ]}
                />
              </div>
  </>);
};
