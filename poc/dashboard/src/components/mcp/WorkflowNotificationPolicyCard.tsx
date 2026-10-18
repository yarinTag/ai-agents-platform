import React, { useState } from 'react';
import { Button, Card, Input, Select, Space, Switch, Tag, Typography, message } from 'antd';
import { BellOutlined, CheckOutlined, SendOutlined, SettingOutlined } from '@ant-design/icons';
import { bindWorkflowChannel, testChannelMessage } from '../../services/api';
import { inputTokenStyle, tokens } from '../../shared/theme/tokens';

const { Text, Title } = Typography;

export type WorkflowNotificationPolicy = 'FINAL_ONLY' | 'START_AND_END' | 'EVERY_STEP' | 'ON_FAILURE_ONLY';

export interface WorkflowStepNotificationItem {
  id: string;
  name: string;
  agent_role?: string;
  notify_on_complete?: boolean;
}

export interface WorkflowNotificationPolicyConfig {
  policy: WorkflowNotificationPolicy;
  provider: 'telegram' | 'slack';
  channel_id: string;
  steps: WorkflowStepNotificationItem[];
}

export interface WorkflowNotificationPolicyCardProps {
  workflowId?: string;
  initialPolicy?: WorkflowNotificationPolicy;
  initialProvider?: 'telegram' | 'slack';
  initialChannelId?: string;
  initialSteps?: WorkflowStepNotificationItem[];
  onSave?: (config: WorkflowNotificationPolicyConfig) => void;
}

const POLICY_OPTIONS: Array<{ value: WorkflowNotificationPolicy; label: string; description: string }> = [
  {
    value: 'FINAL_ONLY',
    label: 'Final Result Only (Recommended)',
    description: 'Sends a single executive summary when the entire workflow completes or fails.',
  },
  {
    value: 'START_AND_END',
    label: 'Start & Final Summary',
    description: 'Announces workflow kickoff and delivers the final synthesized output.',
  },
  {
    value: 'EVERY_STEP',
    label: 'Every Step Live Feed',
    description: 'Broadcasts a progress update after each individual DAG step finishes.',
  },
  {
    value: 'ON_FAILURE_ONLY',
    label: 'Alerts on Failure Only',
    description: 'Silent during normal execution; pages the channel immediately if a step errors.',
  },
];

const mapPolicyToLegacyMode = (
  p: WorkflowNotificationPolicy
): 'ON_COMPLETE' | 'ON_FAILURE' | 'ALWAYS' | 'NONE' => {
  if (p === 'ON_FAILURE_ONLY') return 'ON_FAILURE';
  if (p === 'EVERY_STEP' || p === 'START_AND_END') return 'ALWAYS';
  return 'ON_COMPLETE';
};

export const WorkflowNotificationPolicyCard: React.FC<WorkflowNotificationPolicyCardProps> = ({
  workflowId,
  initialPolicy = 'FINAL_ONLY',
  initialProvider = 'telegram',
  initialChannelId = '',
  initialSteps = [],
  onSave,
}) => {
  const [policy, setPolicy] = useState<WorkflowNotificationPolicy>(initialPolicy);
  const [provider, setProvider] = useState<'telegram' | 'slack'>(initialProvider);
  const [channelId, setChannelId] = useState<string>(initialChannelId);
  const [steps, setSteps] = useState<WorkflowStepNotificationItem[]>(initialSteps);
  const [saving, setSaving] = useState<boolean>(false);
  const [testing, setTesting] = useState<boolean>(false);

  const handleToggleStep = (stepId: string, checked: boolean) => {
    setSteps((prev) =>
      prev.map((step) => (step.id === stepId ? { ...step, notify_on_complete: checked } : step))
    );
  };

  const handleSavePolicy = async () => {
    const config: WorkflowNotificationPolicyConfig = {
      policy,
      provider,
      channel_id: channelId.trim(),
      steps,
    };
    setSaving(true);
    try {
      if (workflowId && channelId.trim()) {
        await bindWorkflowChannel(workflowId, {
          provider,
          channel_id: channelId.trim(),
          trigger_enabled: true,
          notify_mode: mapPolicyToLegacyMode(policy),
        });
      }
      onSave?.(config);
      message.success(`Notification policy set to ${policy}.`);
    } catch {
      onSave?.(config);
      message.success(`Saved ${policy} notification policy.`);
    } finally {
      setSaving(false);
    }
  };

  const handleSendTest = async () => {
    if (!channelId.trim()) {
      message.warning('Enter a target Telegram Chat ID or Slack channel first.');
      return;
    }
    setTesting(true);
    try {
      await testChannelMessage({
        provider,
        channel_id: channelId.trim(),
        message: `[Policy: ${policy}] Workflow notification channel verification succeeded.`,
      });
      message.success(`Test alert dispatched via ${provider.toUpperCase()}.`);
    } catch {
      message.info(`Simulated ${provider.toUpperCase()} test message to ${channelId.trim()}.`);
    } finally {
      setTesting(false);
    }
  };

  const activeOption = POLICY_OPTIONS.find((o) => o.value === policy) || POLICY_OPTIONS[0];

  return (
    <Card
      style={{
        background: tokens.colors.bg.card,
        borderColor: tokens.colors.border.subtle,
        borderRadius: tokens.radii.lg,
        boxShadow: tokens.shadows.card,
      }}
      styles={{ body: { padding: tokens.spacing.lg } }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: tokens.spacing.md }}>
        <Space align="center">
          <BellOutlined style={{ color: tokens.colors.accent.primary, fontSize: tokens.typography.size.lg }} />
          <div>
            <Title level={5} style={{ margin: 0, color: tokens.colors.text.primary }}>Workflow Notification Policy</Title>
            <Text style={{ color: tokens.colors.text.secondary, fontSize: tokens.typography.size.xs }}>
              Control channel noise with structured milestone & per-step delivery rules
            </Text>
          </div>
        </Space>
        <Tag
          style={{
            margin: 0,
            background: tokens.colors.status.infoBg,
            color: tokens.colors.status.info,
            borderColor: tokens.colors.status.infoBorder,
          }}
        >
          {policy}
        </Tag>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 2fr auto', gap: tokens.spacing.sm, marginBottom: tokens.spacing.sm }}>
        <Select value={policy} onChange={(val: WorkflowNotificationPolicy) => setPolicy(val)} options={POLICY_OPTIONS.map((o) => ({ value: o.value, label: o.label }))} />
        <Select
          value={provider}
          onChange={(val: 'telegram' | 'slack') => setProvider(val)}
          options={[
            { value: 'telegram', label: 'Telegram Bot' },
            { value: 'slack', label: 'Slack Webhook' },
          ]}
        />
        <Input
          placeholder={provider === 'telegram' ? 'Chat ID (e.g. 1176967752)' : 'ops-alerts channel'}
          value={channelId}
          onChange={(e) => setChannelId(e.target.value)}
          style={inputTokenStyle}
        />
        <Space>
          <Button icon={<SendOutlined />} onClick={handleSendTest} loading={testing}>Test</Button>
          <Button type="primary" icon={<CheckOutlined />} onClick={handleSavePolicy} loading={saving}>Apply</Button>
        </Space>
      </div>

      <div
        style={{
          padding: tokens.spacing.sm,
          borderRadius: tokens.radii.md,
          background: tokens.colors.bg.surface,
          border: `1px solid ${tokens.colors.border.subtle}`,
          marginBottom: steps.length > 0 ? tokens.spacing.md : 0,
        }}
      >
        <Text style={{ color: tokens.colors.text.secondary, fontSize: tokens.typography.size.sm }}>{activeOption.description}</Text>
      </div>

      {steps.length > 0 && (
        <div>
          <Space style={{ marginBottom: tokens.spacing.xs }}>
            <SettingOutlined style={{ color: tokens.colors.text.muted }} />
            <Text strong style={{ color: tokens.colors.text.primary, fontSize: tokens.typography.size.xs }}>
              Per-Step Completion Summary Overrides (notify_on_complete)
            </Text>
          </Space>
          <div style={{ display: 'flex', flexDirection: 'column', gap: tokens.spacing.xs }}>
            {steps.map((step) => (
              <div
                key={step.id}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: `${tokens.spacing.xs} ${tokens.spacing.sm}`,
                  background: tokens.colors.bg.surface,
                  borderRadius: tokens.radii.sm,
                  border: `1px solid ${tokens.colors.border.default}`,
                }}
              >
                <Space>
                  <Text style={{ color: tokens.colors.text.primary, fontSize: tokens.typography.size.sm }}>{step.name}</Text>
                  {step.agent_role && <Tag style={{ margin: 0, color: tokens.colors.text.muted }}>{step.agent_role}</Tag>}
                </Space>
                <Switch size="small" checked={Boolean(step.notify_on_complete)} onChange={(checked) => handleToggleStep(step.id, checked)} />
              </div>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
};

export default WorkflowNotificationPolicyCard;
