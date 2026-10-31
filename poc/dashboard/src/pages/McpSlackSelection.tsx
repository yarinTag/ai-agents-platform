import { useConnectorResourceText } from '../i18n/connectorResources';
import { Tag, Button, Input } from 'antd';
import { SlackOutlined, CheckCircleOutlined, PlusOutlined } from '@ant-design/icons';
import type { useMcpPage } from './useMcpPage';

export const McpSlackSelection = (model: Pick<
  ReturnType<typeof useMcpPage>,
  | 'workflows'
  | 'selectedCatalogItem'
  | 'discoveredResources'
  | 'selectedResources'
  | 'setSelectedResources'
  | 'customResourceInput'
  | 'setCustomResourceInput'
  | 'handleAddCustomResource'
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
  } = model;
  const text = useConnectorResourceText();
  return (<>
            {/* Slack Channels Selection Section */}
            {selectedCatalogItem && selectedCatalogItem.provider === 'slack' && (
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
                  <div style={{ fontWeight: 700, color: '#f59e0b', fontSize: '13px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <SlackOutlined /> Authorized Channels Array
                  </div>
                  <Tag color="gold" style={{ fontSize: '11px', margin: 0 }}>
                    Multi-Channel
                  </Tag>
                </div>
                <div style={{ color: '#8b949e', fontSize: '12px', marginBottom: '12px' }}>
                  Manage authorized Slack channels array for workflows and alerting:
                </div>

                {/* 1. Add Custom Channel Input & Button at TOP */}
                <div style={{ display: 'flex', gap: '8px', marginBottom: '14px' }}>
                  <Input
                    size="middle"
                    placeholder="Add Slack channel to array (e.g. #general, #incidents, C0123456789)"
                    value={customResourceInput}
                    onChange={(e) => setCustomResourceInput(e.target.value)}
                    onPressEnter={handleAddCustomResource}
                    style={{ background: '#161b22', borderColor: '#30363d', color: '#f0f6fc' }}
                  />
                  <Button
                    type="primary"
                    icon={<PlusOutlined />}
                    onClick={handleAddCustomResource}
                    style={{ background: '#ECB22E', borderColor: '#ECB22E', color: '#0d1117', fontWeight: 600, whiteSpace: 'nowrap' }}
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
                    <span style={{ fontSize: '12px', fontWeight: 700, color: '#f59e0b', display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <CheckCircleOutlined style={{ color: '#f59e0b' }} />
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
                      No channels added yet. Type a channel above and click "+ Add Channel" or select from suggestions below.
                    </div>
                  ) : (
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                      {selectedResources.map((chName, idx) => (
                        <Tag
                          key={chName}
                          closable
                          onClose={(e) => {
                            e.preventDefault();
                            setSelectedResources(selectedResources.filter((c) => c !== chName));
                          }}
                          color="gold"
                          style={{
                            fontSize: '12px',
                            padding: '3px 8px',
                            borderRadius: '6px',
                            fontWeight: 600,
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '4px',
                          }}
                        >
                          <span style={{ opacity: 0.65, fontSize: '10px' }}>#{idx + 1}</span>
                          <span>{chName}</span>
                        </Tag>
                      ))}
                    </div>
                  )}
                </div>

                {/* 3. Quick-toggle suggested Slack channels */}
                <div style={{ color: '#8b949e', fontSize: '12px', marginBottom: '8px' }}>
                  {text.availableSlack}
                </div>

                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                  {discoveredResources.map((c: { id?: string }) => c.id || '').filter(Boolean).map((chName: string) => {
                    const isChecked = selectedResources.includes(chName);
                    return (
                      <Tag.CheckableTag
                        key={chName}
                        checked={isChecked}
                        onChange={(checked) => {
                          if (checked) {
                            setSelectedResources([...selectedResources, chName]);
                          } else {
                            setSelectedResources(selectedResources.filter((c) => c !== chName));
                          }
                        }}
                        style={{
                          fontSize: '12px',
                          padding: '4px 10px',
                          borderRadius: '6px',
                          background: isChecked ? '#ECB22E' : '#161b22',
                          color: isChecked ? '#000' : '#8b949e',
                          border: '1px solid #30363d',
                        }}
                      >
                        {chName}
                      </Tag.CheckableTag>
                    );
                  })}
                </div>
              </div>
            )}


  </>);
};
