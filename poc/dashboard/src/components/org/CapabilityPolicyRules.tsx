import React from 'react';
import { Button, Space, Table, Tag, Typography } from 'antd';
import type { GovernanceText } from '../../i18n/governance';
import type { PolicyRule } from '../../types/governance';

export default function CapabilityPolicyRules({ rules, text, editable, onEdit, onRemove }: {
  rules: PolicyRule[]; text: GovernanceText; editable?: (rule: PolicyRule) => boolean;
  onEdit?: (rule: PolicyRule) => void; onRemove?: (rule: PolicyRule) => void;
}) {
  return <Table size="small" rowKey="id" pagination={{ pageSize: 8 }} scroll={{ x: 650 }} dataSource={rules}
    columns={[
      { title: text.capability, key: 'action', render: (_, rule) => <Space direction="vertical" size={0}>
        <bdi dir="ltr">{rule.capability_id}</bdi><Typography.Text type="secondary"><bdi dir="ltr">{rule.connector_id}</bdi></Typography.Text>
        <Typography.Text type="secondary"><bdi dir="ltr">{rule.id}</bdi></Typography.Text>
      </Space> },
      { title: text.resource, key: 'resources', render: (_, rule) => <Space direction="vertical" size={0}>
        {rule.resource_ids.map(id => <bdi dir="ltr" key={id}>{id}</bdi>)}
      </Space> },
      { title: text.effect, key: 'effect', render: (_, rule) => <Tag color={rule.effect === 'allow' ? 'green' : rule.effect === 'deny' ? 'red' : 'gold'}>{text[rule.effect]}</Tag> },
      { title: text.constraints, key: 'constraints', render: (_, rule) => {
        const constraints = [
          ...rule.user_ids.map(id => `${text.users}: ${id}`), ...rule.agent_ids.map(id => `${text.agents}: ${id}`),
          ...rule.workflow_ids.map(id => `${text.workflows}: ${id}`), ...rule.branches.map(id => `${text.branches}: ${id}`),
          rule.not_before && `${text.validFrom}: ${rule.not_before}`, rule.expires_at && `${text.validUntil}: ${rule.expires_at}`,
        ].filter(Boolean);
        return <Space direction="vertical" size={0}>{constraints.map((value, index) => <bdi key={index} dir="ltr">{value}</bdi>)}</Space>;
      } },
      ...(editable ? [{ title: text.edit, key: 'edit', render: (_: unknown, rule: PolicyRule) => editable(rule)
        ? <Space><Button size="small" onClick={() => onEdit?.(rule)}>{text.change}</Button>
          <Button size="small" danger onClick={() => onRemove?.(rule)}>{text.remove}</Button></Space>
        : <Typography.Text type="secondary">{text.savedRestriction}</Typography.Text> }] : []),
    ]} />;
}
