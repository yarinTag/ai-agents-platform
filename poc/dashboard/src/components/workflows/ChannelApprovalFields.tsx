import { useEffect, useState } from 'react';
import { Alert, Card, Button, ConfigProvider, Form, Select, Space, Typography } from 'antd';
import { usePermissions } from '../../hooks/usePermissions';
import { useTranslation } from '../../i18n';
import { useChannelApprovalsText } from '../../i18n/channelApprovals';
import { useDagApprovalsText } from '../../i18n/dagApprovals';
import { listChannelBindings, type ChannelBinding } from '../../services/channelBindingsApi';
import { getIngressDiagnostics, type IngressDiagnostics } from '../../services/channelIngressApi';
import { getPersonalIdentityLinks } from '../../services/externalIdentitiesApi';
import type { DagApprovalPolicy, WorkflowStep } from './workflowBuilderTypes';

export function ChannelApprovalFields({ department, step, policy, onChange }: {
  department?: string | null; step: WorkflowStep; policy: DagApprovalPolicy;
  onChange: (patch: Partial<DagApprovalPolicy>) => void;
}) {
  const text = useChannelApprovalsText();
  const { dir } = useTranslation();
  const [bindings, setBindings] = useState<ChannelBinding[]>();
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!department) return;
    const request = new AbortController();
    const load = async () => {
      const result: ChannelBinding[] = [];
      let after: string | undefined;
      do {
        const { data } = await listChannelBindings(department, after, request.signal);
        result.push(...data.bindings);
        after = data.next_after ?? undefined;
      } while (after && !request.signal.aborted);
      if (!request.signal.aborted) setBindings(result);
    };
    void load().catch(() => { if (!request.signal.aborted) setFailed(true); });
    return () => request.abort();
  }, [department]);

  const eligible = (bindings ?? []).filter(binding =>
    binding.uses.send_notifications && binding.uses.approve_decisions);
  const selected = eligible.find(binding => binding.id === policy.channel_binding_id);
  const options = [{ value: '', label: text.dashboard }, ...eligible.map(binding => ({
    value: binding.id, label: binding.channel_name ? `${binding.channel_name} (${binding.channel_id})` : binding.channel_id,
  }))];
  const missing = policy.channel_binding_id && !selected && (bindings || !department);
  return <ConfigProvider direction={dir}>
    <Form.Item label={text.destination} extra={text.support}>
      <Select aria-label={text.destination} loading={Boolean(department && !bindings && !failed)}
        value={policy.channel_binding_id || ''} options={options}
        onChange={value => onChange({ channel_binding_id: value || undefined, ...(value ? {} : { summary_step: undefined }) })} />
    </Form.Item>
    {failed && <Alert showIcon type="warning" title={text.loadError} />}
    {missing && <Alert showIcon type="warning" title={text.unavailable} />}
    {selected && <>
      <Form.Item label={text.summary}>
        <Select aria-label={text.summary} allowClear value={policy.summary_step}
          options={step.depends_on.map(key => ({ value: key, label: key }))}
          onChange={summary_step => onChange({ summary_step })} />
      </Form.Item>
      <ChannelPreview key={selected.connector_id} connector={selected.connector_id} step={step} policy={policy} />
    </>}
    <Typography.Text type="secondary">{text.fallback}</Typography.Text>
  </ConfigProvider>;
}

function ChannelPreview({ connector, step, policy }: {
  connector: string; step: WorkflowStep; policy: DagApprovalPolicy;
}) {
  const text = useChannelApprovalsText();
  const approval = useDagApprovalsText();
  const { isAdmin } = usePermissions();
  const { locale } = useTranslation();
  const [linked, setLinked] = useState<boolean>();
  const [checks, setChecks] = useState<IngressDiagnostics>();
  useEffect(() => {
    const request = new AbortController();
    void getPersonalIdentityLinks(request.signal).then(({ data }) => {
      if (!request.signal.aborted) setLinked(data.some(link => link.connector_id === connector));
    }).catch(() => {});
    if (isAdmin) void getIngressDiagnostics(connector, request.signal).then(({ data }) => {
      if (!request.signal.aborted) setChecks(data);
    }).catch(() => {});
    return () => request.abort();
  }, [connector, isAdmin]);
  const deadline = new Intl.DateTimeFormat(locale, {
    dateStyle: 'medium', timeStyle: 'short', timeZone: 'UTC',
  }).format(Date.now() + (policy.timeout_seconds ?? 86400) * 1000);
  return <Space orientation="vertical" style={{ width: '100%' }}>
    <Card size="small" title={text.preview}>
      <Space orientation="vertical">
        <Typography.Text strong>ConduitCross · {approval.waiting} · <bdi>0/{policy.quorum ?? 1}</bdi></Typography.Text>
        <Typography.Text><bdi>{step.key}</bdi></Typography.Text>
        <Typography.Text>{approval.expires} <bdi>{deadline} UTC</bdi></Typography.Text>
        {policy.summary_step && <Typography.Text>{text.findings} <bdi>{policy.summary_step}</bdi></Typography.Text>}
        <Space><Button size="small" disabled>{approval.approve}</Button><Button size="small" disabled>{approval.reject}</Button></Space>
        <Typography.Text type="secondary">{text.sample} {text.details}</Typography.Text>
      </Space>
    </Card>
    <Alert type={linked === true ? 'success' : 'info'} title={linked == null ? text.unknownIdentity : linked ? text.linked : text.unlinked} />
    {!checks && <Alert type="info" title={text.unknown} />}
    {checks && (!checks.ingress_mode || checks.ingress_mode === 'webhook') && !checks.https_configured && <Alert type="warning" title={text.missingHttps} />}
    {checks && !checks.secret_configured && <Alert type="warning" title={text.missingSecret} />}
  </Space>;
}
