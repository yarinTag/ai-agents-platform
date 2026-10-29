import { Tag, Button, Modal, Typography, Space } from 'antd';
import { ToolOutlined, FileTextOutlined, ApartmentOutlined } from '@ant-design/icons';

const { Text, Paragraph } = Typography;

import type { WorkflowCanvasStep } from './workflowGraphTypes';

export function WorkflowStepInspector({ selectedStep, detailModalVisible, setDetailModalVisible }: { selectedStep: WorkflowCanvasStep | null; detailModalVisible: boolean; setDetailModalVisible: (visible: boolean) => void }) {
  return (<>
      {/* Step Inspector Modal */}
      <Modal
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <ApartmentOutlined style={{ color: '#38bdf8' }} />
            <span>Step Details: {selectedStep?.name} ({selectedStep?.key})</span>
          </div>
        }
        open={detailModalVisible}
        onCancel={() => setDetailModalVisible(false)}
        footer={[
          <Button key="close" onClick={() => setDetailModalVisible(false)} style={{ background: '#21262d', color: '#f0f6fc' }}>
            Close
          </Button>,
        ]}
        styles={{
          body: { background: '#0d1117', color: '#f0f6fc' },
          header: { background: '#0d1117', borderBottom: '1px solid #21262d' },
        }}
      >
        {selectedStep && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            <div>
              <div style={{ fontSize: '12px', color: '#8b949e', marginBottom: '4px' }}>Assigned Agent:</div>
              <Tag color="cyan" style={{ fontSize: '13px', padding: '4px 10px' }}>
                🤖 {selectedStep.agent_id}
              </Tag>
            </div>

            {selectedStep.mcp_servers && selectedStep.mcp_servers.length > 0 && (
              <div>
                <div style={{ fontSize: '12px', color: '#8b949e', marginBottom: '4px' }}>Restricted MCP Connectors:</div>
                <Space>
                  {selectedStep.mcp_servers.map((mcp) => (
                    <Tag key={mcp} color="purple">
                      <ToolOutlined /> {mcp.toUpperCase()}
                    </Tag>
                  ))}
                </Space>
              </div>
            )}

            {selectedStep.skills && selectedStep.skills.length > 0 && (
              <div>
                <div style={{ fontSize: '12px', color: '#8b949e', marginBottom: '4px' }}>Attached Skills:</div>
                <Space>
                  {selectedStep.skills.map((sk) => (
                    <Tag key={sk} color="gold">
                      <FileTextOutlined /> {sk}
                    </Tag>
                  ))}
                </Space>
              </div>
            )}

            <div>
              <div style={{ fontSize: '12px', color: '#8b949e', marginBottom: '4px' }}>Prompt Template:</div>
              <div
                style={{
                  background: '#161b22',
                  border: '1px solid #30363d',
                  borderRadius: '8px',
                  padding: '12px',
                  fontFamily: 'monospace',
                  fontSize: '12px',
                  color: '#34d399',
                  lineHeight: 1.5,
                  whiteSpace: 'pre-wrap',
                }}
              >
                {selectedStep.prompt_template}
              </div>
            </div>

            <div>
              <div style={{ fontSize: '12px', color: '#8b949e', marginBottom: '4px' }}>DAG Dependencies:</div>
              {selectedStep.depends_on && selectedStep.depends_on.length > 0 ? (
                <Space>
                  {selectedStep.depends_on.map((dep) => (
                    <Tag key={dep} color="blue">
                      ↳ {dep}
                    </Tag>
                  ))}
                </Space>
              ) : (
                <span style={{ color: '#6e7681', fontSize: '12px' }}>None (Root step)</span>
              )}
            </div>
          </div>
        )}
      </Modal>
  </>);
}
