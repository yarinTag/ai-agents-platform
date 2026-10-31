import { useEffect, useRef } from 'react';
import { Alert, Button, Card, Collapse, Empty, Input, Modal, Select, Space, Spin, Steps, Tag, Typography } from 'antd';
import { SendOutlined, BulbOutlined } from '@ant-design/icons';
import { useTranslation } from '../../i18n';
import { useWorkflowChat } from './useWorkflowChat';

interface Props { onClose: () => void; onCreated: () => void }

export function WorkflowChatModal({ onClose, onCreated }: Props) {
  const model = useWorkflowChat(onCreated);
  const { text, context, department, messages, input, job, workflow, error, working, loading, active } = model;
  const { dir } = useTranslation();
  const tail = useRef<HTMLDivElement>(null);
  useEffect(() => { tail.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' }); }, [messages.length, active]);
  const created = job?.status === 'CREATED';
  const allowed = !!context?.selection && !!department;
  const close = async () => {
    if (active) { if (await model.stop()) onClose(); } else if (!model.submitting) onClose();
  };
  const connectors = context?.catalog?.connectors || [];
  const agentLabel = (id: string) => {
    const agent = context?.catalog?.agents.find(item => item.id === id);
    return agent?.provision_on_create ? text.plannedRunner : agent?.name || id;
  };
  const skillLabel = (id: string) => context?.catalog?.skills?.find(skill => skill.id === id)?.name || id;
  const channelLabel = (connectorId: string, id: string) => connectors.find(c => c.id === connectorId)?.channel_labels?.[id] || id;
  return <Modal open title={<Space><BulbOutlined />{text.title}</Space>} onCancel={() => void close()}
    closable={!model.submitting || active} mask={{ closable: false }} footer={null} width={1120} styles={{ body: { paddingTop: 12 } }}>
    <div dir={dir}>
      <Typography.Paragraph type="secondary">{text.intro}</Typography.Paragraph>
      <Space wrap style={{ marginBottom: 20 }}>
        <Select aria-label={text.department} placeholder={text.department} value={department || undefined}
          style={{ minWidth: 200 }} disabled={working || messages.length > 0}
          options={context?.departments.map(d => ({ label: d.name, value: d.id }))} onChange={model.setDepartment} />
        <Typography.Text type="secondary">{text.using}: <strong>{job?.model || context?.selection?.model_id || '—'}</strong></Typography.Text>
        <Button size="small" disabled={working} onClick={() => window.dispatchEvent(new Event('platform:configure-runtime'))}>{text.settings}</Button>
        {messages.length > 0 && <Button type="text" disabled={working} onClick={model.reset}>{text.newChat}</Button>}
      </Space>
      {error && <Alert type="error" showIcon message={error} style={{ marginBottom: 12 }} action={<Button size="small" onClick={model.refresh}>{text.retry}</Button>} />}
      {loading && <Spin />}
      {!loading && context && !context.departments.length && <Alert type="info" message={text.noDepartments} />}
      {!loading && context && !context.selection && <Alert type="warning" message={text.noModel} />}
      {context?.catalog && !context.catalog.agents.length && <Alert type="info" message={text.noAgents} style={{ marginBottom: 12 }} />}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 360px), 1fr))', gap: 20 }}>
        <div style={{ display: 'flex', flexDirection: 'column', minWidth: 0 }}>
          <div style={{ height: 360, overflowY: 'auto', padding: 8 }} aria-live="polite">
            {!messages.length && <div style={{ paddingBlock: 45, textAlign: 'center' }}>
              <Typography.Title level={4}>{text.empty}</Typography.Title>
              <Space direction="vertical">
                {[text.example1, text.example2].map(example => <Button key={example} onClick={() => model.setInput(example)}>{example}</Button>)}
              </Space>
            </div>}
            {messages.map((message, index) => <div key={index} style={{ marginBottom: 18, padding: 12, borderRadius: 12,
              background: message.role === 'user' ? 'rgba(99,102,241,.15)' : 'rgba(128,128,128,.06)' }}>
              <Typography.Text strong>{message.role === 'user' ? text.you : text.assistant}</Typography.Text>
              <div style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', marginTop: 6 }}>{message.content}</div>
            </div>)}
            {active && <Space><Spin size="small" /><Typography.Text type="secondary">{text.thinking}</Typography.Text></Space>}
            <div ref={tail} />
          </div>
          <Input.TextArea aria-label={text.placeholder} value={input} onChange={e => model.setInput(e.target.value)}
            placeholder={text.placeholder} maxLength={8000} autoSize={{ minRows: 3, maxRows: 6 }}
            disabled={working || !allowed || loading || created}
            onPressEnter={e => { if ((e.ctrlKey || e.metaKey) && !e.nativeEvent.isComposing) { e.preventDefault(); void model.send(); } }} />
          <Space style={{ marginTop: 10, justifyContent: 'flex-end' }}>
            {active ? <Button disabled={working && !active} onClick={() => void model.stop()}>{text.stop}</Button> :
              <Button type="primary" icon={<SendOutlined />} loading={working} disabled={!input.trim() || !allowed || loading || created}
                onClick={() => void model.send()}>{text.send}</Button>}
          </Space>
        </div>
        <Card title={text.preview} style={{ minWidth: 0 }}>
          {!workflow ? <Empty description={text.previewEmpty} image={Empty.PRESENTED_IMAGE_SIMPLE} /> : <>
            <Typography.Title level={4} style={{ marginTop: 0 }}>{workflow.name}</Typography.Title>
            <Typography.Paragraph type="secondary">{workflow.description}</Typography.Paragraph>
            <Tag>{workflow.cron_expression ? `${text.schedule}: ${workflow.cron_expression}` : text.manual}</Tag>
            <Steps direction="vertical" size="small" style={{ marginTop: 20, marginBottom: 16 }}
              items={workflow.steps.map(step => ({ status: 'wait' as const, title: step.name, description: <>
                <Typography.Text type="secondary">{agentLabel(step.agent_id)}</Typography.Text>
                {!!step.resources.length && <div dir="ltr">{step.resources.map((r, i) =>
                  <Tag key={i} style={{ whiteSpace: 'normal', overflowWrap: 'anywhere' }}>{[r.repository, r.channel_id ? channelLabel(r.connector_id, r.channel_id) : null, r.tool_name].filter(Boolean).join(' · ')}</Tag>)}</div>}
              </> }))} />
            <Typography.Paragraph>{text.workflowSkills}: </Typography.Paragraph>
            {[...new Set([...(workflow.skills || []), ...workflow.steps.flatMap(step => step.skills || [])])].map(id =>
              <Tag color="purple" key={id} title={id}>{skillLabel(id)}</Tag>)}
            <Typography.Paragraph type="secondary">{text.skillInheritance}</Typography.Paragraph>
            {workflow.destination && <Typography.Paragraph>{text.delivery}: <Typography.Text code>{channelLabel(workflow.destination.connector_id, workflow.destination.channel_id)}</Typography.Text></Typography.Paragraph>}
            {!!job?.result?.errors.length && <Alert type="warning" message={text.invalid}
              description={job.result.errors.map((value, index) => <div key={index}>{value}</div>)} style={{ marginBottom: 12 }} />}
            {created ? <Alert type="success" showIcon message={text.created} /> : <>
              <Button type="primary" block disabled={!job?.result?.ready || working || loading} onClick={() => void model.create()}>{text.create}</Button>
              <Typography.Paragraph type="secondary" style={{ fontSize: 12, marginTop: 8 }}>{text.inactive}</Typography.Paragraph>
            </>}
          </>}
        </Card>
      </div>
      <Collapse ghost style={{ marginTop: 12 }} items={[{ key: 'resources', label: text.resources, children: <>
        <Typography.Paragraph type="secondary">{text.missing}</Typography.Paragraph>
        {!!context?.catalog?.skills?.length && <div style={{ marginBottom: 12 }}>
          <Typography.Text strong>{text.skills}: </Typography.Text>
          {context.catalog.skills.map(skill => <Tag key={skill.id} title={skill.description}>{skill.plugin} / {skill.name}</Tag>)}
        </div>}
        {connectors.map(connector => <div key={connector.id} style={{ marginBottom: 12 }}>
          <Typography.Text strong>{connector.name}</Typography.Text>{' '}
          <Tag color={connector.execution_supported ? 'success' : 'default'}>{connector.execution_supported ? text.available : text.unavailable}</Tag>
          {[{ label: text.repositories, items: connector.repositories }, { label: text.channels, items: connector.channels.map(id => connector.channel_labels?.[id] || id) }, { label: text.tools, items: connector.tools }].map(({ label, items }) =>
            items.length > 0 ? <div key={String(label)}><Typography.Text type="secondary">{String(label)}: </Typography.Text>
              {items.map(value => <Tag key={value}>{value}</Tag>)}</div> : null)}
        </div>)}
      </> }]} />
    </div>
  </Modal>;
}
