import React from 'react';
import {
  Modal,
  Form,
  Radio,
  Row,
  Col,
  Select,
  Divider,
  Checkbox,
  Input,
  Button,
  Popconfirm,
} from 'antd';
import type { FormInstance } from 'antd';
import {
  LinkOutlined,
  DisconnectOutlined,
  SlackOutlined,
  SendOutlined,
} from '@ant-design/icons';
import { PlatformWorkflow } from '../../types/mcp';
import { tokens, modalTokenStyles, inputTokenStyle } from '../../shared/ui';

export interface WorkflowChannelBindingModalProps {
  open: boolean;
  workflow: PlatformWorkflow | null;
  form: FormInstance;
  submitting: boolean;
  availableTelegramChats: string[];
  availableSlackChannels: string[];
  onCancel: () => void;
  onSave: () => void;
  onUnbind: (workflowId: string) => Promise<void>;
}

export const WorkflowChannelBindingModal: React.FC<WorkflowChannelBindingModalProps> = ({
  open,
  workflow,
  form,
  submitting,
  availableTelegramChats,
  availableSlackChannels,
  onCancel,
  onSave,
  onUnbind,
}) => {
  return (
    <Modal
      title={
        <div style={{ display: 'flex', alignItems: 'center', gap: tokens.spacing.sm }}>
          <LinkOutlined style={{ color: tokens.colors.status.success }} />
          <span>Bind Channel to Workflow: {workflow?.name}</span>
        </div>
      }
      open={open}
      onCancel={onCancel}
      footer={[
        workflow?.channel_binding ? (
          <Popconfirm
            key="unbind"
            title="Unbind this channel from the workflow?"
            description="This will disconnect the channel without deleting the workflow."
            onConfirm={async () => {
              if (workflow) {
                await onUnbind(workflow.id);
                onCancel();
              }
            }}
            okText="Unbind"
            cancelText="Cancel"
          >
            <Button danger icon={<DisconnectOutlined />} style={{ float: 'left' }}>
              Unbind Channel (נתק ערוץ)
            </Button>
          </Popconfirm>
        ) : null,
        <Button key="cancel" onClick={onCancel}>
          Cancel
        </Button>,
        <Button key="submit" type="primary" loading={submitting} onClick={onSave}>
          Save Channel Binding
        </Button>,
      ]}
      width={540}
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
          Choose an authorized Slack or Telegram channel to connect to this workflow. You can enable incoming command triggers and configure automatic reporting.
        </p>

        <Form form={form} layout="vertical">
          <Form.Item
            name="provider"
            label={<span style={{ color: tokens.colors.text.primary }}>Communication Provider</span>}
            rules={[{ required: true }]}
          >
            <Radio.Group style={{ width: '100%' }}>
              <Row gutter={12}>
                <Col span={12}>
                  <Radio.Button
                    value="slack"
                    style={{ width: '100%', textAlign: 'center', height: '42px', lineHeight: '40px' }}
                  >
                    <SlackOutlined style={{ color: tokens.colors.accent.amber, marginRight: tokens.spacing.sm }} /> Slack
                  </Radio.Button>
                </Col>
                <Col span={12}>
                  <Radio.Button
                    value="telegram"
                    style={{ width: '100%', textAlign: 'center', height: '42px', lineHeight: '40px' }}
                  >
                    <SendOutlined style={{ color: tokens.colors.accent.blue, marginRight: tokens.spacing.sm }} /> Telegram
                  </Radio.Button>
                </Col>
              </Row>
            </Radio.Group>
          </Form.Item>

          <Form.Item noStyle shouldUpdate={(prev, curr) => prev.provider !== curr.provider}>
            {({ getFieldValue }) => {
              const prov = getFieldValue('provider');
              const channels = prov === 'telegram' ? availableTelegramChats : availableSlackChannels;

              return (
                <Form.Item
                  name="channel_id"
                  label={<span style={{ color: tokens.colors.text.primary }}>Target Channel / Chat</span>}
                  rules={[{ required: true, message: 'Please select a channel' }]}
                >
                  <Select
                    style={{ width: '100%' }}
                    placeholder="Select authorized channel"
                    options={channels.map((ch) => ({ label: ch, value: ch }))}
                  />
                </Form.Item>
              );
            }}
          </Form.Item>

          <Divider style={{ borderColor: tokens.colors.border.subtle }} />

          <Form.Item name="trigger_enabled" valuePropName="checked">
            <Checkbox style={{ color: tokens.colors.text.primary }}>
              <span style={{ fontWeight: tokens.typography.weight.semibold }}>
                ⚡ Allow incoming messages in this channel to trigger this workflow
              </span>
            </Checkbox>
          </Form.Item>

          <Form.Item
            name="notify_mode"
            label={
              <span style={{ color: tokens.colors.text.primary }}>
                Outgoing Notification Mode (כתיבת תוצאות לערוץ)
              </span>
            }
            rules={[{ required: true }]}
          >
            <Select
              style={{ width: '100%' }}
              options={[
                { label: '✓ Post on Complete only (הודעה בסיום מוצלח)', value: 'ON_COMPLETE' },
                { label: '⚠️ Post on Failure only (התראה רק בכשלון)', value: 'ON_FAILURE' },
                { label: '📢 Always (הודעה בהתחלה ובסיום)', value: 'ALWAYS' },
                { label: '🔒 Read-only (ללא שליחת הודעות חזרה)', value: 'NONE' },
              ]}
            />
          </Form.Item>

          <Form.Item
            name="message_template"
            label={<span style={{ color: tokens.colors.text.primary }}>Custom Message Template (Optional)</span>}
          >
            <Input.TextArea
              rows={2}
              placeholder="e.g. 🚀 Workflow {{workflow_name}} finished with status: {{status}}"
              style={inputTokenStyle}
            />
          </Form.Item>
        </Form>
      </div>
    </Modal>
  );
};
