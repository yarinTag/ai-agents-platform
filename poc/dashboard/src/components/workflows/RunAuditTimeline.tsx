import { Alert, Button, Card, ConfigProvider, Space, Tag, Timeline, Typography } from 'antd';
import { Link } from 'react-router-dom';
import { useTranslation } from '../../i18n';
import { useRunAuditText } from '../../i18n/runAudit';
import type { WorkflowExecution } from '../../types/mcp';

export function auditTime(value?: string | number | null) {
  if (typeof value === 'number') return Number.isFinite(value) ? value * 1000 : null;
  if (!value) return null;
  // SQLite CURRENT_TIMESTAMP uses a space separator and stores UTC.
  const timestamp = /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(\.\d+)?$/.test(value)
    ? value.replace(' ', 'T') + 'Z' : value;
  const time = Date.parse(timestamp);
  return Number.isFinite(time) ? time : null;
}

export function RunAuditTimeline({ execution, onReview }: {
  execution: WorkflowExecution; onReview?: () => void;
}) {
  const audit = execution.run_audit;
  const text = useRunAuditText();
  const { locale, dir } = useTranslation();
  if (!audit) return null;

  const formatTime = (value?: string | number | null) => {
    const time = auditTime(value);
    return time == null ? null : new Date(time).toLocaleString(locale);
  };
  const trigger = audit.trigger;
  const origin = trigger ? [
    { time: auditTime(trigger.received_at), key: trigger.event_id, label: text.ingress, children: <Space wrap>
      <Tag>{trigger.provider}</Tag>
      {trigger.outbox_status && <Tag>{trigger.outbox_status}</Tag>}
      <bdi>{trigger.event_id}</bdi>
      <span>{text.sender} <bdi>{trigger.sender_user_id}</bdi></span>
      <span>{formatTime(trigger.received_at)}</span>
    </Space> },
  ] : [];
  const milestones = [
    ...origin,
    { time: auditTime(execution.started_at || execution.created_at), key: execution.id, label: text.run,
      children: <Space wrap>
        <Tag>{execution.trigger_type}</Tag>
        <Tag>{execution.status}</Tag>
        {audit.workflow_revision != null && <span>{text.revision} {audit.workflow_revision}</span>}
        {audit.principal_id && <span>{text.principal} <bdi>{audit.principal_id}</bdi></span>}
      </Space> },
    ...audit.approvals.map(approval => ({
      key: approval.id, label: text.approval,
      time: auditTime(approval.decided_at ?? approval.opened_at),
      children: <Space wrap>
        <bdi>{approval.step_key}</bdi>
        <Tag>{approval.status}</Tag>
        {approval.decided_by && <span>{text.actor} <bdi>{approval.decided_by}</bdi></span>}
        {approval.decision_source && <Tag>{text[approval.decision_source]}</Tag>}
        {approval.delivery_status && <Tag>{text.delivery} · {approval.delivery_status}</Tag>}
        {approval.message_id && <bdi>#{approval.message_id}</bdi>}
        <span>{formatTime(approval.decided_at ?? approval.opened_at)}</span>
      </Space>,
    })),
    ...audit.receipts.map(receipt => ({
      key: receipt.id, label: text.receipt, time: auditTime(receipt.completed_at || receipt.started_at),
      children: <Space wrap>
        <Tag>{receipt.provider}</Tag>
        <bdi>{receipt.step_key}</bdi><bdi>{receipt.operation}</bdi>
        <Tag>{receipt.receipt.status ?? receipt.status}</Tag>
        {receipt.receipt.message_id && <bdi>#{receipt.receipt.message_id}</bdi>}
        {receipt.receipt.pull_number && <bdi>PR #{receipt.receipt.pull_number}</bdi>}
        <span>{formatTime(receipt.completed_at || receipt.started_at)}</span>
      </Space>,
    })),
  ].sort((a, b) => (a.time ?? Number.MAX_SAFE_INTEGER) - (b.time ?? Number.MAX_SAFE_INTEGER));
  const uncertain = audit.approvals.some(item => item.delivery_status === 'UNCONFIRMED');

  return <ConfigProvider direction={dir}><Card size="small" title={text.title}>
    <Space orientation="vertical" style={{ width: '100%' }}>
      <Typography.Text code copyable><bdi>{audit.correlation_id}</bdi></Typography.Text>
      {uncertain && <Alert type="warning" showIcon title={text.unknown}
        action={<Space wrap><Link to="/mcp">{text.inspect}</Link>
          {onReview && <Button size="small" onClick={onReview}>{text.review}</Button>}</Space>} />}
      <Timeline items={milestones.map(({ key, label, children }) => ({
        key, children: <Space orientation="vertical" size={2}><Typography.Text strong>{label}</Typography.Text>{children}</Space>,
      }))} />
      {audit.receipts_truncated && <Typography.Text type="secondary">{text.truncated}</Typography.Text>}
    </Space>
  </Card></ConfigProvider>;
}
