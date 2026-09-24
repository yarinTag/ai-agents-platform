import React, { useState, useEffect } from 'react';
import {
  Modal,
  Form,
  Input,
  Select,
  Radio,
  Button,
  Space,
  Typography,
  Card,
  Tag,
  Divider,
  Alert,
  message
} from 'antd';
import {
  ClockCircleOutlined,
  ThunderboltOutlined,
  CalendarOutlined,
  CheckCircleOutlined,
  InfoCircleOutlined
} from '@ant-design/icons';
import { Agent } from '../../types/agent';
import { Project } from '../../types/project';
import { ScheduledJobCreateDto } from '../../types/scheduler';
import { createSchedule, validateCronExpression } from '../../services/api';

const { Text, Paragraph } = Typography;

interface CronBuilderModalProps {
  visible: boolean;
  onClose: () => void;
  onSuccess: () => void;
  agents: Agent[];
  projects: Project[];
}

const CRON_PRESETS = [
  { label: '⚡ Every 15 minutes', value: '*/15 * * * *', desc: 'Frequent interval for real-time monitors' },
  { label: '🕒 Every Hour', value: '0 * * * *', desc: 'Runs at the beginning of every hour' },
  { label: '🌅 Daily at 09:00 AM', value: '0 9 * * *', desc: 'Morning standup / daily review' },
  { label: '💼 Weekdays at 09:00 AM', value: '0 9 * * 1-5', desc: 'Runs Monday through Friday' },
  { label: '🌙 Nightly at Midnight', value: '0 0 * * *', desc: 'Nightly builds, backups and cleanup' },
  { label: '📅 Weekly on Sunday', value: '0 0 * * 0', desc: 'Weekly summary and planning' },
];

export const CronBuilderModal: React.FC<CronBuilderModalProps> = ({
  visible,
  onClose,
  onSuccess,
  agents,
  projects,
}) => {
  const [form] = Form.useForm();
  const [submitting, setSubmitting] = useState(false);
  const [selectedPreset, setSelectedPreset] = useState<string>('0 9 * * *');
  const [cronExpression, setCronExpression] = useState<string>('0 9 * * *');
  const [upcomingRuns, setUpcomingRuns] = useState<string[]>([]);
  const [validationError, setValidationError] = useState<string | null>(null);

  // Validate cron expression whenever it changes
  useEffect(() => {
    let active = true;
    const checkCron = async () => {
      if (!cronExpression || cronExpression.trim().length < 5) return;
      try {
        const res = await validateCronExpression(cronExpression);
        if (active) {
          if (res.data.valid && res.data.upcoming_runs) {
            setUpcomingRuns(res.data.upcoming_runs);
            setValidationError(null);
          } else {
            setUpcomingRuns([]);
            setValidationError(res.data.error || 'Invalid cron format');
          }
        }
      } catch (err: any) {
        if (active) {
          setUpcomingRuns([]);
          setValidationError(err.response?.data?.detail || 'Invalid cron format');
        }
      }
    };

    const timer = setTimeout(checkCron, 400);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [cronExpression]);

  const handlePresetChange = (val: string) => {
    setSelectedPreset(val);
    setCronExpression(val);
    form.setFieldsValue({ cron_expression: val });
  };

  const handleCronInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setCronExpression(val);
    setSelectedPreset('');
  };

  const handleFinish = async (values: any) => {
    if (validationError) {
      message.error('Please fix the cron expression before saving.');
      return;
    }

    try {
      setSubmitting(true);
      const payload: ScheduledJobCreateDto = {
        name: values.name,
        description: values.description,
        cron_expression: cronExpression,
        agent_id: values.agent_id,
        project_id: values.project_id || null,
        prompt: values.prompt,
        concurrency_policy: values.concurrency_policy || 'SKIP',
        enabled: true,
      };

      await createSchedule(payload);
      message.success(`Scheduled job "${values.name}" created successfully!`);
      form.resetFields();
      onSuccess();
      onClose();
    } catch (err: any) {
      console.error('Failed to create schedule:', err);
      message.error(err.response?.data?.detail || 'Failed to create scheduled job');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      title={
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <CalendarOutlined style={{ color: '#10b981', fontSize: '20px' }} />
          <span>New Scheduled Task (Cron Job)</span>
        </div>
      }
      open={visible}
      onCancel={onClose}
      footer={null}
      width={680}
      styles={{
        header: { borderBottom: '1px solid #30363d' },
        body: { padding: '20px 24px' }
      }}
    >
      <Form
        form={form}
        layout="vertical"
        onFinish={handleFinish}
        initialValues={{
          cron_expression: '0 9 * * *',
          concurrency_policy: 'SKIP',
        }}
      >
        <Form.Item
          name="name"
          label={<span style={{ fontWeight: 600 }}>Job Name</span>}
          rules={[{ required: true, message: 'Please provide a name for this job' }]}
        >
          <Input placeholder="e.g. Daily Vulnerability Scan or Weekly Summary Report" />
        </Form.Item>

        <Form.Item
          name="agent_id"
          label={<span style={{ fontWeight: 600 }}>Target Agent</span>}
          rules={[{ required: true, message: 'Select an agent to execute this job' }]}
        >
          <Select
            placeholder="Select responsible agent"
            options={agents.map((a) => ({
              label: (
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span>{a.avatar || '🤖'}</span>
                  <span style={{ fontWeight: 500 }}>{a.name}</span>
                  <Tag color="blue" style={{ fontSize: '11px', marginInlineStart: 'auto' }}>
                    {a.department || 'Engineering'}
                  </Tag>
                </div>
              ),
              value: a.id,
            }))}
          />
        </Form.Item>

        <Form.Item
          name="project_id"
          label={<span style={{ fontWeight: 600 }}>Project Context (Optional)</span>}
        >
          <Select
            allowClear
            placeholder="Global / No specific project"
            options={projects.map((p) => ({ label: `📁 ${p.name}`, value: p.id }))}
          />
        </Form.Item>

        <Form.Item
          name="prompt"
          label={<span style={{ fontWeight: 600 }}>Task Instruction / Prompt</span>}
          rules={[{ required: true, message: 'Enter the prompt instructions for the agent' }]}
        >
          <Input.TextArea
            rows={3}
            placeholder="Explain what the agent should do upon each trigger (e.g. Scan repo for syntax errors, compile audit log and post findings)."
          />
        </Form.Item>

        <Divider style={{ margin: '16px 0', borderColor: '#30363d' }}>
          <Space>
            <ClockCircleOutlined />
            <span>Schedule Frequency</span>
          </Space>
        </Divider>

        {/* Quick Presets */}
        <div style={{ marginBottom: '16px' }}>
          <Text type="secondary" style={{ fontSize: '13px', display: 'block', marginBottom: '8px' }}>
            Quick Presets:
          </Text>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
            {CRON_PRESETS.map((p) => (
              <Button
                key={p.value}
                type={selectedPreset === p.value ? 'primary' : 'default'}
                onClick={() => handlePresetChange(p.value)}
                style={{ textAlign: 'left', height: 'auto', padding: '8px 12px' }}
              >
                <div style={{ fontWeight: 500 }}>{p.label}</div>
                <div style={{ fontSize: '11px', opacity: 0.7 }}>{p.value}</div>
              </Button>
            ))}
          </div>
        </div>

        {/* Custom Cron Input */}
        <Form.Item
          name="cron_expression"
          label={<span style={{ fontWeight: 600 }}>Cron Expression (5-Field Format: min hour dom mon dow)</span>}
          rules={[{ required: true, message: 'Please enter a valid cron expression' }]}
        >
          <Input
            value={cronExpression}
            onChange={handleCronInputChange}
            placeholder="e.g. 0 9 * * 1-5"
            style={{ fontFamily: 'monospace', fontSize: '14px' }}
          />
        </Form.Item>

        {/* Live Validation & Next Runs Preview */}
        {validationError ? (
          <Alert
            type="error"
            showIcon
            message="Invalid Schedule Format"
            description={validationError}
            style={{ marginBottom: '16px' }}
          />
        ) : upcomingRuns.length > 0 ? (
          <Card
            size="small"
            style={{
              marginBottom: '16px',
              background: '#0d1117',
              borderColor: '#30363d',
              borderRadius: '8px'
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#10b981', fontWeight: 600, marginBottom: '8px' }}>
              <CheckCircleOutlined />
              <span>Projected Next 5 Runs:</span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              {upcomingRuns.map((run, idx) => (
                <div key={idx} style={{ fontSize: '12px', color: '#8b949e', fontFamily: 'monospace' }}>
                  {idx + 1}. {new Date(run).toLocaleString()}
                </div>
              ))}
            </div>
          </Card>
        ) : null}

        <Form.Item
          name="concurrency_policy"
          label={
            <Space>
              <span style={{ fontWeight: 600 }}>Concurrency Policy</span>
              <InfoCircleOutlined style={{ color: '#8b949e' }} />
            </Space>
          }
        >
          <Radio.Group>
            <Radio value="SKIP">
              <b>SKIP (Recommended)</b> - Skip if agent is already busy executing
            </Radio>
            <Radio value="COALESCE">
              <b>COALESCE</b> - Run once immediately after current task finishes
            </Radio>
            <Radio value="ALLOW">
              <b>ALLOW</b> - Concurrently launch new task
            </Radio>
          </Radio.Group>
        </Form.Item>

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', marginTop: '20px' }}>
          <Button onClick={onClose}>Cancel</Button>
          <Button
            type="primary"
            htmlType="submit"
            loading={submitting}
            icon={<ThunderboltOutlined />}
            style={{ background: '#10b981', borderColor: '#10b981' }}
          >
            Create Scheduled Job
          </Button>
        </div>
      </Form>
    </Modal>
  );
};
