import { useConnectorResourceText } from '../i18n/connectorResources';
import { Tag, Button, Input } from 'antd';
import { SendOutlined, CheckCircleOutlined, PlusOutlined } from '@ant-design/icons';
import type { useMcpPage } from './useMcpPage';

export const McpTelegramSelection = (model: Pick<
  ReturnType<typeof useMcpPage>,
  | 'workflows'
  | 'selectedCatalogItem'
  | 'discoveredResources'
  | 'selectedResources'
  | 'setSelectedResources'
  | 'customResourceInput'
  | 'setCustomResourceInput'
  | 'handleAddCustomResource'
  | 'handleFetchResources'
  | 'fetchingResources'
  | 'form'
  | 'editingConnector'
>) => {
  const {
    workflows,
    selectedCatalogItem,
    discoveredResources,
    selectedResources,
    setSelectedResources,
    customResourceInput,
    setCustomResourceInput,
    handleAddCustomResource,
    handleFetchResources, fetchingResources, form, editingConnector,
  } = model;
  const text = useConnectorResourceText();
  return (<>
            {/* Telegram Chats Selection Section */}
            {selectedCatalogItem && selectedCatalogItem.provider === 'telegram' && (
              <div
                style={{
                  marginTop: '16px',
                  padding: '16px',
                  background: '#0d1117',
                  borderRadius: '8px',
                  border: '1px solid #30363d',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                  <div style={{ fontWeight: 700, color: '#38bdf8', fontSize: '13px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <SendOutlined /> Authorized Chats & Channels Array
                  </div>
                  <Tag color="blue" style={{ fontSize: '11px', margin: 0 }}>
                    Multi-Channel
                  </Tag>
                </div>
                <div style={{ color: '#8b949e', fontSize: '12px', marginBottom: '12px' }}>
                  Manage authorized Telegram channels and chats array for workflows and alerting:
                </div>

                <Button loading={fetchingResources} style={{ marginBottom: 8 }}
                  onClick={() => void handleFetchResources('telegram', form.getFieldValue('bot_token') || editingConnector?.configuration?.bot_token, selectedResources, true)}>
                  {text.findChats}
                </Button>
                <div style={{ color: '#8b949e', fontSize: 12, marginBottom: 12 }}>{text.findHint}</div>
                <div style={{ color: '#8b949e', fontSize: 12, marginBottom: 12 }}>{text.testHint}</div>
                {/* 1. Add Custom Channel Input & Button at TOP */}
                <div style={{ display: 'flex', gap: '8px', marginBottom: '14px' }}>
                  <Input
                    size="middle"
                    placeholder={text.telegramPlaceholder}
                    value={customResourceInput}
                    onChange={(e) => setCustomResourceInput(e.target.value)}
                    onPressEnter={handleAddCustomResource}
                    style={{ background: '#161b22', borderColor: '#30363d', color: '#f0f6fc' }}
                  />
                  <Button
                    type="primary"
                    icon={<PlusOutlined />}
                    onClick={handleAddCustomResource}
                    style={{ background: '#229ED9', borderColor: '#229ED9', color: '#fff', fontWeight: 600, whiteSpace: 'nowrap' }}
                  >
                    + Add Channel
                  </Button>
                </div>

                {/* 2. Configured Channels Array Box */}
                <div
                  style={{
                    background: '#161b22',
                    border: '1px solid #30363d',
                    borderRadius: '8px',
                    padding: '12px',
                    marginBottom: '14px',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                    <span style={{ fontSize: '12px', fontWeight: 700, color: '#38bdf8', display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <CheckCircleOutlined style={{ color: '#38bdf8' }} />
                      Configured Channels Array ({selectedResources.length}):
                    </span>
                    {selectedResources.length > 0 && (
                      <Button
                        size="small"
                        type="link"
                        danger
                        onClick={() => setSelectedResources([])}
                        style={{ padding: 0, height: 'auto', fontSize: '11px' }}
                      >
                        Clear All
                      </Button>
                    )}
                  </div>
                  {selectedResources.length === 0 ? (
                    <div style={{ color: '#8b949e', fontSize: '12px', fontStyle: 'italic' }}>
                      No channels added yet. Type a chat ID or @channel above and click "+ Add Channel" or select from suggestions below.
                    </div>
                  ) : (
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                      {selectedResources.map((chatName, idx) => (
                        <Tag
                          key={chatName}
                          closable
                          onClose={(e) => {
                            e.preventDefault();
                            setSelectedResources(selectedResources.filter((c) => c !== chatName));
                          }}
                          color="blue"
                          style={{
                            fontSize: '12px',
                            padding: '3px 8px',
                            borderRadius: '6px',
                            fontWeight: 600,
                            background: 'rgba(56, 189, 248, 0.15)',
                            border: '1px solid #38bdf8',
                            color: '#38bdf8',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '4px',
                          }}
                        >
                          <span style={{ opacity: 0.65, fontSize: '10px' }}>#{idx + 1}</span>
                          <span>{discoveredResources.find((chat: { id?: string }) => chat.id === chatName)?.name
                            || editingConnector?.configuration?.channel_labels?.[chatName] || chatName}</span>
                        </Tag>
                      ))}
                    </div>
                  )}
                </div>

                {/* 3. Quick-toggle suggested Telegram channels */}
                <div style={{ color: '#8b949e', fontSize: '12px', marginBottom: '8px' }}>
                  {text.availableChats}
                </div>

                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                  {discoveredResources.map((chat: { id?: string; name?: string }) => {
                    const chatName = chat.id || '';
                    if (!chatName) return null;
                    const isChecked = selectedResources.includes(chatName);
                    return (
                      <span key={chatName} title={chatName}>
                      <Tag.CheckableTag
                        checked={isChecked}
                        onChange={(checked) => {
                          if (checked) {
                            setSelectedResources([...selectedResources, chatName]);
                          } else {
                            setSelectedResources(selectedResources.filter((c) => c !== chatName));
                          }
                        }}
                        style={{
                          fontSize: '12px',
                          padding: '4px 10px',
                          borderRadius: '6px',
                          background: isChecked ? '#229ED9' : '#161b22',
                          color: isChecked ? '#fff' : '#8b949e',
                          border: '1px solid #30363d',
                        }}
                      >
                        {chat.name || chatName}
                      </Tag.CheckableTag>
                      </span>
                    );
                  })}
                </div>
              </div>
            )}
  </>);
};
