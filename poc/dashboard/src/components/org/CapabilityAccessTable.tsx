import React from 'react';
import { Alert, Collapse, Empty, Space, Table, Tag, Typography } from 'antd';
import type { CapabilityCatalog, CapabilityDecision, CapabilityDescriptor } from '../../types/governance';
import type { GovernanceText } from '../../i18n/governance';

export function DecisionBadge({ value, text }: { value: CapabilityDecision; text: GovernanceText }) {
  const labels = { allowed: text.allowed, denied: text.denied, requires_approval: text.requires_approval };
  const colors = { allowed: 'green', denied: 'red', requires_approval: 'gold' };
  return <Space direction="vertical" size={0}>
    <Tag color={colors[value.decision]}>{labels[value.decision] || text.unknown}</Tag>
    {value.decision !== 'allowed' && <Typography.Text type="secondary" style={{ fontSize: 11 }}>
      {value.reason === 'CURRENT_ROLE_REQUIRED' ? text.readOnly
        : value.decision === 'requires_approval' ? text.conditional : text.ceiling}
    </Typography.Text>}
  </Space>;
}

export default function CapabilityAccessTable({ catalog, capabilities, text }: {
  catalog: CapabilityCatalog; capabilities: CapabilityDescriptor[]; text: GovernanceText;
}) {
  const rows = catalog.entries.flatMap(entry => entry.resources.map(resource => ({
    ...resource, ...entry, key: JSON.stringify([entry.connector_id, entry.capability.id, resource.resource_id]),
  })));
  const unsupported = capabilities.filter(cap => !cap.implemented);
  return <Space direction="vertical" style={{ width: '100%' }} size="middle">
    <Alert type="info" showIcon message={text.readiness} description={text.conditional} />
    <Table dataSource={rows} rowKey="key" scroll={{ x: 850 }} pagination={{ pageSize: 10 }}
      locale={{ emptyText: <Empty description={text.empty} /> }} columns={[
        { title: text.capability, key: 'capability', render: (_, row) => <Space direction="vertical" size={2}>
          <bdi dir="ltr">{row.capability.id}</bdi>
          <Tag>{({ read: text.read, write: text.write, destructive: text.destructive } as Record<string, string>)[row.capability.effect] || text.unknown}</Tag>
          <Typography.Text type="secondary">{row.capability.description}</Typography.Text>
        </Space> },
        { title: text.connector, dataIndex: 'connector_id', render: value => <bdi dir="ltr">{value}</bdi> },
        { title: text.resource, dataIndex: 'resource_id', render: value => <Typography.Text copyable><bdi dir="ltr">{value}</bdi></Typography.Text> },
        { title: text.authoring, key: 'authoring', render: (_, row) => <DecisionBadge value={row.authoring} text={text} /> },
        { title: text.execution, key: 'execution', render: (_, row) => <DecisionBadge value={row.execution} text={text} /> },
      ]} />
    {!!unsupported.length && <Collapse items={[{ key: 'unsupported', label: text.unsupported, children: <>
      <p>{text.unsupportedHelp}</p>
      {unsupported.map(cap => <Tag key={cap.id}><bdi dir="ltr">{cap.id}</bdi> · {text.unsupported}</Tag>)}
    </> }]} />}
  </Space>;
}
