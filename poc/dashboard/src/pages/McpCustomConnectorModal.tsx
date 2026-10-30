import { Input, Modal, Form, message, Space } from 'antd';
import { ApiOutlined } from '@ant-design/icons';
import type { useMcpPage } from './useMcpPage';

export const McpCustomConnectorModal = (model: Pick<
  ReturnType<typeof useMcpPage>,
  | 'submitting'
  | 'form'
  | 'customModalVisible'
  | 'setCustomModalVisible'
  | 'customForm'
  | 'handleSaveCustom'
>) => {
  const { submitting, form, customModalVisible, setCustomModalVisible, customForm, handleSaveCustom } = model;
  return (<>
      {/* Custom MCP Modal */}
      <Modal
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <ApiOutlined style={{ color: '#10b981' }} />
            <span>Register Custom MCP Server</span>
          </div>
        }
        open={customModalVisible}
        onCancel={() => setCustomModalVisible(false)}
        onOk={handleSaveCustom}
        confirmLoading={submitting}
        okText="Register Server"
        width={560}
      >
        <p style={{ color: '#8b949e', fontSize: '13px', marginBottom: '16px' }}>
            Register any local or external MCP stdio server command (e.g. <code>npx -y @modelcontextprotocol/server-...</code> or <code>python mcp_server.py</code>).
          </p>

          <Form form={customForm} layout="vertical">
            <Form.Item
              name="name"
              label={<span style={{ color: '#f0f6fc' }}>Connector Name</span>}
              rules={[{ required: true, message: 'Please enter a name' }]}
            >
              <Input placeholder="e.g. My Custom Weather MCP" style={{ background: '#0d1117', borderColor: '#30363d', color: '#f0f6fc' }} />
            </Form.Item>

            <Form.Item
              name="command"
              label={<span style={{ color: '#f0f6fc' }}>Execution Command</span>}
              rules={[{ required: true, message: 'Command is required' }]}
            >
              <Input placeholder="e.g. npx -y @modelcontextprotocol/server-postgres" style={{ background: '#0d1117', borderColor: '#30363d', color: '#f0f6fc' }} />
            </Form.Item>

            <Form.Item
              name="args"
              label={<span style={{ color: '#f0f6fc' }}>CLI Arguments (Space Separated)</span>}
            >
              <Input placeholder="e.g. --port 5000 /path/to/db" style={{ background: '#0d1117', borderColor: '#30363d', color: '#f0f6fc' }} />
            </Form.Item>

            <Form.Item
              name="env"
              label={<span style={{ color: '#f0f6fc' }}>Environment Variables (JSON)</span>}
            >
              <Input.TextArea
                rows={3}
                placeholder='{"API_KEY": "secret_123"}'
                style={{ background: '#0d1117', borderColor: '#30363d', color: '#f0f6fc', fontFamily: 'monospace' }}
              />
            </Form.Item>
          </Form>
      </Modal>

  </>);
};
