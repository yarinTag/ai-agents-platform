import { Input, Button, Space } from 'antd';
import { CopyOutlined, DownloadOutlined, CheckOutlined, SyncOutlined } from '@ant-design/icons';

import { useWorkflowBuilder } from './useWorkflowBuilder';

export function WorkflowYamlPanel({ model }: { model: ReturnType<typeof useWorkflowBuilder> }) {
  const {
    copied, yamlContent, setYamlContent, yamlDirty, setYamlDirty,
    handleCopyYaml, handleDownloadYaml, handleSyncYamlToVisual,
  } = model;
  return (
<div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                  <div style={{ color: '#8b949e', fontSize: '12px' }}>
                    Production-ready declarative YAML file generated automatically with MCPs and skills:
                  </div>
                  <Space>
                    {yamlDirty && (
                      <Button
                        size="small"
                        icon={<SyncOutlined />}
                        onClick={handleSyncYamlToVisual}
                        style={{ background: '#1e3a8a', borderColor: '#2563eb', color: '#60a5fa' }}
                      >
                        Sync to Visual Builder
                      </Button>
                    )}
                    <Button
                      size="small"
                      icon={copied ? <CheckOutlined /> : <CopyOutlined />}
                      onClick={handleCopyYaml}
                      style={{ background: '#161b22', borderColor: '#30363d', color: '#f0f6fc' }}
                    >
                      {copied ? 'Copied!' : 'Copy YAML'}
                    </Button>
                    <Button
                      size="small"
                      icon={<DownloadOutlined />}
                      onClick={handleDownloadYaml}
                      style={{ background: '#161b22', borderColor: '#30363d', color: '#38bdf8' }}
                    >
                      Download .yaml
                    </Button>
                  </Space>
                </div>

                <Input.TextArea
                  rows={15}
                  value={yamlContent}
                  onChange={(e) => {
                    setYamlContent(e.target.value);
                    setYamlDirty(true);
                  }}
                  style={{
                    fontFamily: 'monospace',
                    fontSize: '12px',
                    background: '#090d13',
                    borderColor: '#30363d',
                    color: '#34d399',
                    borderRadius: '8px',
                    padding: '12px',
                    lineHeight: '1.5',
                  }}
                />
              </div>
  );
}
