import React from 'react';
import { Modal, Form, Input } from 'antd';
import type { FormInstance } from 'antd';
import { ApiOutlined } from '@ant-design/icons';
import { tokens, modalTokenStyles, inputTokenStyle } from '../../shared/ui';

export interface CustomMcpServerModalProps {
  open: boolean;
  form: FormInstance;
  submitting: boolean;
  onCancel: () => void;
  onSave: () => void;
}

export const CustomMcpServerModal: React.FC<CustomMcpServerModalProps> = ({
  open,
  form,
  submitting,
  onCancel,
  onSave,
}) => {
  return (
    <Modal
      title={
        <div style={{ display: 'flex', alignItems: 'center', gap: tokens.spacing.sm }}>
          <ApiOutlined style={{ color: tokens.colors.status.success }} />
          <span>Register Custom MCP Server</span>
        </div>
      }
      open={open}
      onCancel={onCancel}
      onOk={onSave}
      confirmLoading={submitting}
      okText="Register Server"
      width={560}
      styles={modalTokenStyles}
    >
      <div style={{ padding: `${tokens.spacing.sm} 0` }}>
        <p
          style={{
            color: tokens.colors.text.secondary,
            fontSize: tokens.typography.size.sm,
            marginBottom: tokens.spacing.lg,
          }}
        >
          Register any local or external MCP stdio server command (e.g.{' '}
          <code>npx -y @modelcontextprotocol/server-...</code> or <code>python mcp_server.py</code>).
        </p>

        <Form form={form} layout="vertical">
          <Form.Item
            name="name"
            label={<span style={{ color: tokens.colors.text.primary }}>Connector Name</span>}
            rules={[{ required: true, message: 'Please enter a name' }]}
          >
            <Input placeholder="e.g. My Custom Weather MCP" style={inputTokenStyle} />
          </Form.Item>

          <Form.Item
            name="command"
            label={<span style={{ color: tokens.colors.text.primary }}>Execution Command</span>}
            rules={[{ required: true, message: 'Command is required' }]}
          >
            <Input
              placeholder="e.g. npx -y @modelcontextprotocol/server-postgres"
              style={inputTokenStyle}
            />
          </Form.Item>

          <Form.Item
            name="args"
            label={<span style={{ color: tokens.colors.text.primary }}>CLI Arguments (Space Separated)</span>}
          >
            <Input placeholder="e.g. --port 5000 /path/to/db" style={inputTokenStyle} />
          </Form.Item>

          <Form.Item
            name="env"
            label={<span style={{ color: tokens.colors.text.primary }}>Environment Variables (JSON)</span>}
          >
            <Input.TextArea
              rows={3}
              placeholder='{"API_KEY": "secret_123"}'
              style={{
                ...inputTokenStyle,
                fontFamily: tokens.typography.fontMono,
              }}
            />
          </Form.Item>
        </Form>
      </div>
    </Modal>
  );
};
