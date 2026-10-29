import { Row, Col, Tag, Button, Input, Modal, Form, message, Popconfirm, Checkbox, Divider, Select, Radio, Space } from 'antd';
import { SendOutlined, SlackOutlined, LinkOutlined, DisconnectOutlined } from '@ant-design/icons';
import type { useMcpPage } from './useMcpPage';

export const McpBindingModal = (model: Pick<
  ReturnType<typeof useMcpPage>,
  | 'loading'
  | 'catalog'
  | 'form'
  | 'handleQuickAddBindingChannel'
  | 'bindingModalVisible'
  | 'setBindingModalVisible'
  | 'bindingWorkflow'
  | 'bindingSubmitting'
  | 'bindingForm'
  | 'quickAddBindingInput'
  | 'setQuickAddBindingInput'
  | 'extraBindingChannels'
  | 'setExtraBindingChannels'
  | 'handleOpenConnect'
  | 'handleSaveBinding'
  | 'handleUnbindChannel'
  | 'slackConnector'
  | 'telegramConnector'
  | 'availableSlackChannels'
  | 'availableTelegramChats'
>) => {
  const {
    loading,
    catalog,
    form,
    handleQuickAddBindingChannel,
    bindingModalVisible,
    setBindingModalVisible,
    bindingWorkflow,
    bindingSubmitting,
    bindingForm,
    quickAddBindingInput,
    setQuickAddBindingInput,
    extraBindingChannels,
    setExtraBindingChannels,
    handleOpenConnect,
    handleSaveBinding,
    handleUnbindChannel,
    slackConnector,
    telegramConnector,
    availableSlackChannels,
    availableTelegramChats,
  } = model;
  return (<>
      {/* Workflow Channel Binding Modal */}
      <Modal
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <LinkOutlined style={{ color: '#10b981' }} />
            <span>Bind Channel to Workflow: {bindingWorkflow?.name}</span>
          </div>
        }
        open={bindingModalVisible}
        onCancel={() => setBindingModalVisible(false)}
        footer={[
          bindingWorkflow?.channel_binding ? (
            <Popconfirm
              key="unbind"
              title="Unbind this channel from the workflow?"
              description="This will disconnect the channel without deleting the workflow."
              onConfirm={async () => {
                if (bindingWorkflow) {
                  await handleUnbindChannel(bindingWorkflow.id);
                  setBindingModalVisible(false);
                }
              }}
              okText="Unbind"
              cancelText="Cancel"
            >
              <Button danger icon={<DisconnectOutlined />} style={{ float: 'left' }}>
                Unbind Channel
              </Button>
            </Popconfirm>
          ) : null,
          <Button key="cancel" onClick={() => setBindingModalVisible(false)}>
            Cancel
          </Button>,
          <Button key="submit" type="primary" loading={bindingSubmitting} onClick={handleSaveBinding}>
            Save Channel Binding
          </Button>,
        ]}
        width={540}
      >
        <p style={{ color: '#8b949e', fontSize: '13px', marginBottom: '16px' }}>
            Choose an authorized Slack or Telegram channel to connect to this workflow. You can enable incoming command triggers and configure automatic reporting.
          </p>

          <Form form={bindingForm} layout="vertical">
            <Form.Item
              name="provider"
              label={<span style={{ color: '#f0f6fc' }}>Communication Provider</span>}
              rules={[{ required: true }]}
            >
              <Radio.Group style={{ width: '100%' }}>
                <Row gutter={12}>
                  <Col span={12}>
                    <Radio.Button value="slack" style={{ width: '100%', textAlign: 'center', height: '42px', lineHeight: '40px' }}>
                      <SlackOutlined style={{ color: '#ECB22E', marginRight: '8px' }} /> Slack
                    </Radio.Button>
                  </Col>
                  <Col span={12}>
                    <Radio.Button value="telegram" style={{ width: '100%', textAlign: 'center', height: '42px', lineHeight: '40px' }}>
                      <SendOutlined style={{ color: '#229ED9', marginRight: '8px' }} /> Telegram
                    </Radio.Button>
                  </Col>
                </Row>
              </Radio.Group>
            </Form.Item>

            <Form.Item noStyle shouldUpdate={(prev, curr) => prev.provider !== curr.provider}>
              {({ getFieldValue }) => {
                const prov = getFieldValue('provider') || 'slack';
                const baseChannels = prov === 'telegram' ? availableTelegramChats : availableSlackChannels;
                const extraList = prov === 'telegram' ? extraBindingChannels.telegram : extraBindingChannels.slack;
                const allChannels = Array.from(new Set([...baseChannels, ...extraList])).filter(Boolean);
                const currentConnector = prov === 'telegram' ? telegramConnector : slackConnector;

                return (
                  <div>
                    <Form.Item
                      name="channel_id"
                      label={<span style={{ color: '#f0f6fc' }}>Target Channel / Chat</span>}
                      rules={[{ required: true, message: 'Please select a channel' }]}
                      style={{ marginBottom: '8px' }}
                    >
                      <Select
                        showSearch
                        filterOption={(input, option) =>
                          (option?.value ?? '').toString().toLowerCase().includes(input.toLowerCase())
                        }
                        style={{ width: '100%' }}
                        placeholder={`Select configured ${prov === 'telegram' ? 'Telegram' : 'Slack'} channel`}
                        options={allChannels.map((ch) => ({
                          label: (
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                              <span>{ch}</span>
                              <Tag color={prov === 'telegram' ? 'blue' : 'gold'} style={{ fontSize: '10px', marginRight: 0 }}>
                                {prov}
                              </Tag>
                            </div>
                          ),
                          value: ch,
                        }))}
                      />
                    </Form.Item>

                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        padding: '6px 10px',
                        background: '#161b22',
                        borderRadius: '6px',
                        border: '1px solid #30363d',
                        marginBottom: '16px',
                        fontSize: '12px',
                      }}
                    >
                      <span style={{ color: '#8b949e' }}>
                        {allChannels.length} configured channel{allChannels.length === 1 ? '' : 's'} in {prov} array
                      </span>
                      <Space size="small">
                        <Input
                          size="small"
                          placeholder={prov === 'telegram' ? '+ Quick add @chat' : '+ Quick add #channel'}
                          value={quickAddBindingInput}
                          onChange={(e) => setQuickAddBindingInput(e.target.value)}
                          onPressEnter={() => handleQuickAddBindingChannel(prov as 'slack' | 'telegram')}
                          style={{ width: 140, background: '#0d1117', borderColor: '#30363d', color: '#f0f6fc', fontSize: '11px' }}
                        />
                        <Button
                          size="small"
                          onClick={() => handleQuickAddBindingChannel(prov as 'slack' | 'telegram')}
                          style={{ fontSize: '11px', height: '24px' }}
                        >
                          Add
                        </Button>
                        {currentConnector && (
                          <Button
                            type="link"
                            size="small"
                            onClick={() => {
                              setBindingModalVisible(false);
                              const catItem = catalog.find((i) => i.provider === prov) || {
                                id: prov,
                                name: prov === 'telegram' ? 'Telegram Bot' : 'Slack',
                                provider: prov,
                                category: 'Communication',
                                description: '',
                                icon: prov,
                                config_schema: {},
                                default_tools: [],
                                package: '',
                              };
                              handleOpenConnect(catItem, currentConnector);
                            }}
                            style={{ padding: '0 4px', fontSize: '11px', color: '#38bdf8' }}
                          >
                            ⚙️ Configure MCP
                          </Button>
                        )}
                      </Space>
                    </div>
                  </div>
                );
              }}
            </Form.Item>

            <Divider style={{ borderColor: '#21262d' }} />

            <Form.Item
              name="trigger_enabled"
              valuePropName="checked"
            >
              <Checkbox style={{ color: '#f0f6fc' }}>
                <span style={{ fontWeight: 600 }}>⚡ Allow incoming messages in this channel to trigger this workflow</span>
              </Checkbox>
            </Form.Item>

            <Form.Item
              name="notify_mode"
              label={<span style={{ color: '#f0f6fc' }}>Outgoing Notification Mode</span>}
              rules={[{ required: true }]}
            >
              <Select
                style={{ width: '100%' }}
                options={[
                  { label: '✓ Post on Complete only', value: 'ON_COMPLETE' },
                  { label: '⚠️ Post on Failure only', value: 'ON_FAILURE' },
                  { label: '📢 Always', value: 'ALWAYS' },
                  { label: '🔒 Read-only (no responses sent)', value: 'NONE' },
                ]}
              />
            </Form.Item>

            <Form.Item
              name="message_template"
              label={<span style={{ color: '#f0f6fc' }}>Custom Message Template (Optional)</span>}
            >
              <Input.TextArea
                rows={2}
                placeholder="e.g. 🚀 Workflow {{workflow_name}} finished with status: {{status}}"
                style={{ background: '#0d1117', borderColor: '#30363d', color: '#f0f6fc' }}
              />
            </Form.Item>
          </Form>
      </Modal>

  </>);
};
