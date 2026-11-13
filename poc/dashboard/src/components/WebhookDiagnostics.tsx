import { useEffect, useRef, useState } from 'react';
import { Alert, Button, Card, ConfigProvider, Descriptions, Empty, Select, Space, Table, Tag, Typography, message } from 'antd';
import { ExperimentOutlined, ReloadOutlined } from '@ant-design/icons';
import { isAxiosError } from 'axios';
import { useAuth } from '../context/AuthContext';
import { useTranslation } from '../i18n';
import { useChannelIngressText } from '../i18n/channelIngress';
import {
  getIngressDiagnostics, testIngressConfiguration,
  type IngressDiagnostics, type IngressEvent, type IngressTest,
} from '../services/channelIngressApi';
import type { MCPConnector } from '../types/mcp';
import { getChannelCatalog } from '../services/channelBindingsApi';
import type { ChannelCatalog } from '../services/channelBindingsApi';

type Connector = Pick<MCPConnector, 'id' | 'name' | 'provider'>;
type ErrorKey = 'accessDenied' | 'routeUnavailable' | 'refreshFailed' | 'testFailed';
const providers = { slack: 'Slack', telegram: 'Telegram' } as const;
const providerName = (provider: string) => providers[provider as keyof typeof providers] ?? provider;
const has = (object: object, key: string) => Object.prototype.hasOwnProperty.call(object, key);

function errorKey(error: unknown, fallback: ErrorKey): ErrorKey {
  const status = isAxiosError(error) ? error.response?.status : undefined;
  if (status === 401 || status === 403) return 'accessDenied';
  return status === 404 ? 'routeUnavailable' : fallback;
}

export function WebhookDiagnostics({ connectors }: { connectors: Connector[] }) {
  const { organization, user, activeDepartmentId } = useAuth();
  const { dir } = useTranslation();
  if (!organization || user?.role !== 'ORG_ADMIN') return null;
  const key = JSON.stringify([organization.id, user.id, activeDepartmentId]);
  return <ConfigProvider direction={dir}><ConnectorSelection key={key} connectors={connectors} /></ConfigProvider>;
}

function ConnectorSelection({ connectors }: { connectors: Connector[] }) {
  const text = useChannelIngressText();
  const [catalog, setCatalog] = useState<ChannelCatalog>();
  const [error, setError] = useState(false);
  const [revision, setRevision] = useState(0);
  const [selected, setSelected] = useState<string>();
  useEffect(() => {
    const request = new AbortController();
    setError(false);
    void getChannelCatalog(null, request.signal).then(({ data }) => {
      if (!request.signal.aborted) setCatalog(data);
    }).catch(() => { if (!request.signal.aborted) setError(true); });
    return () => request.abort();
  }, [revision]);
  if (error) return <Alert type="error" showIcon title={text.connectorLoadFailed}
    action={<Button onClick={() => setRevision(value => value + 1)}>{text.refresh}</Button>} />;
  if (!catalog) return <Typography.Text role="status">{text.loadingConnectors}</Typography.Text>;
  const supported = connectors.filter(({ provider }) => catalog.providers[provider.toLowerCase()]?.ingress_supported);
  const connector = supported.find(({ id }) => id === selected) ?? (supported.length === 1 ? supported[0] : undefined);
  if (!supported.length) return <Empty description={text.emptyConnectors} />;
  return <Space orientation="vertical" size="middle" style={{ width: '100%' }}>
    <Select aria-label={text.connector} placeholder={text.selectConnector} value={connector?.id} onChange={setSelected}
      style={{ width: 'min(100%, 360px)' }}
      options={supported.map(({ id, name, provider }) => ({ value: id, label: `${name} · ${catalog.providers[provider.toLowerCase()].label}` }))} />
    {connector && <ConnectorDiagnostics key={connector.id} connectorId={connector.id} />}
  </Space>;
}

function ConnectorDiagnostics({ connectorId }: { connectorId: string }) {
  const text = useChannelIngressText();
  const { locale } = useTranslation();
  const [messageApi, messageContext] = message.useMessage();
  const [revision, setRevision] = useState(0);
  const [details, setDetails] = useState<IngressDiagnostics>();
  const [error, setError] = useState<ErrorKey>();
  const [loading, setLoading] = useState(true);
  const [probeResult, setProbeResult] = useState<IngressTest>();
  const [checkedTls, setCheckedTls] = useState<IngressTest['tls_status']>();
  const [probing, setProbing] = useState<'configuration' | 'tls'>();
  const probe = useRef<AbortController | undefined>(undefined);
  useEffect(() => () => { probe.current?.abort(); }, []);

  useEffect(() => {
    const request = new AbortController();
    setLoading(true);
    setDetails(undefined);
    setError(undefined);
    setProbeResult(undefined);
    setCheckedTls(undefined);
    void getIngressDiagnostics(connectorId, request.signal).then(({ data }) => {
      if (!request.signal.aborted) setDetails(data);
    }).catch((reason: unknown) => {
      if (!request.signal.aborted) setError(errorKey(reason, 'refreshFailed'));
    }).finally(() => {
      if (!request.signal.aborted) setLoading(false);
    });
    return () => request.abort();
  }, [connectorId, revision]);

  const check = async (verifyTls = false) => {
    if (!details || probe.current) return;
    const request = new AbortController();
    probe.current = request;
    setProbeResult(undefined);
    if (verifyTls) setCheckedTls(undefined);
    setProbing(verifyTls ? 'tls' : 'configuration');
    try {
      const { data } = await testIngressConfiguration(connectorId, request.signal, verifyTls);
      if (!request.signal.aborted) {
        setProbeResult(data);
        if (verifyTls) setCheckedTls(data.tls_status);
      }
    } catch (reason) {
      if (!request.signal.aborted) {
        const reasonKey = errorKey(reason, 'testFailed');
        if (reasonKey !== 'testFailed') {
          setDetails(undefined);
          setError(reasonKey);
        } else {
          void messageApi.error(text[reasonKey]);
        }
      }
    } finally {
      if (!request.signal.aborted) {
        probe.current = undefined;
        setProbing(undefined);
      }
    }
  };

  const dateFormat = new Intl.DateTimeFormat(locale, { dateStyle: 'short', timeStyle: 'medium' });
  const numberFormat = new Intl.NumberFormat(locale);
  const time = (seconds: number | null) => {
    const date = new Date((seconds ?? Number.NaN) * 1000);
    return Number.isFinite(date.getTime()) ? <bdi>{dateFormat.format(date)}</bdi> : null;
  };
  const readyTag = (configured: boolean) => <Tag color={configured ? 'success' : 'warning'}>{configured ? text.configured : text.missing}</Tag>;
  const checks = probeResult?.checks ?? details;
  const tlsStatus = checkedTls ?? details?.ssl_status;
  const stateLabel = (state: string) => has(text.states, state)
    ? text.states[state as keyof typeof text.states] : text.states.UNKNOWN;
  const failureLabel = (code: string) => has(text.failureCodes, code)
    ? text.failureCodes[code as keyof typeof text.failureCodes] : text.failureCodes.UNKNOWN;

  return <Space orientation="vertical" size="middle" style={{ width: '100%' }}>
    {messageContext}
    <Space wrap>
      <Button icon={<ReloadOutlined />} loading={loading} disabled={Boolean(probing)}
        onClick={() => setRevision(value => value + 1)}>{text.refresh}</Button>
      <Button icon={<ExperimentOutlined />} loading={probing === 'configuration'} disabled={!details || loading || probing === 'tls'}
        onClick={() => void check()}>{text.test}</Button>
      <Button loading={probing === 'tls'} disabled={!details?.https_configured || loading || probing === 'configuration'}
        onClick={() => void check(true)}>{text.testTls}</Button>
    </Space>
    {error && <Alert type="error" showIcon title={text[error]} />}
    {details && checks && <>
      <Card size="small" title={text.title}>
        <Descriptions column={{ xs: 1, md: 2 }} items={[
          { key: 'endpoint', label: text.endpoint, span: 'filled', children: details.webhook_url
            ? <Typography.Text style={{ overflowWrap: 'anywhere' }}
              copyable={{ text: details.webhook_url, tooltips: [text.copyEndpoint, text.copiedEndpoint] }}>
              <bdi dir="ltr">{details.webhook_url}</bdi>
            </Typography.Text> : text.endpointMissing },
          { key: 'https', label: text.https, children: readyTag(checks.https_configured) },
          { key: 'secret', label: text.secret, children: readyTag(checks.secret_configured) },
          { key: 'connector', label: text.connectorConnection, children: <Tag color={checks.connector_connected ? 'success' : 'warning'}>
            {checks.connector_connected ? text.connected : text.disconnected}
          </Tag> },
          { key: 'tls', label: text.ssl, children: <Tag color={tlsStatus === 'VALID' ? 'success' : tlsStatus === 'INVALID' ? 'error' : undefined}>
            {tlsStatus === 'VALID' ? text.tlsValid : tlsStatus === 'INVALID' ? text.tlsInvalid : text.unverified}
          </Tag> },
          { key: 'last', label: text.lastVerified, children: time(details.last_verified_at) ?? text.noDelivery },
          ...(typeof probeResult?.checks.storage_ready === 'boolean' ? [{
            key: 'storage', label: text.storage, children: readyTag(probeResult.checks.storage_ready),
          }] : []),
        ]} />
        <Space orientation="vertical">
          <Typography.Text type="secondary">{text.tlsHint}</Typography.Text>
          {details.https_configured && ['slack', 'telegram'].includes(details.provider) && <Typography.Text type="secondary">
            {details.provider === 'slack' ? text.slackDeliveryHint : text.telegramDeliveryHint}
          </Typography.Text>}
        </Space>
      </Card>
      {probeResult && <Alert showIcon type={probeResult.status === 'READY' ? 'success' : 'warning'}
        title={probeResult.status === 'READY' ? text.testReady : text.testBlocked} />}
      {tlsStatus === 'INVALID' && <Alert type="warning" showIcon title={text.tlsFailureHint} />}
      <Card size="small" title={text.events}>
        <Table<IngressEvent> size="small" rowKey="id" dataSource={details.recent_events} pagination={false}
          scroll={{ x: 'max-content' }} locale={{ emptyText: text.emptyEvents }} columns={[
            { title: text.timestamp, key: 'received', render: (_, row) => time(row.received_at) ?? text.noValue },
            { title: text.provider, key: 'provider', render: (_, row) => <bdi>{providerName(row.provider)}</bdi> },
            { title: text.eventType, key: 'type', render: (_, row) => has(text.eventTypes, row.event_type)
              ? text.eventTypes[row.event_type] : text.states.UNKNOWN },
            { title: text.status, key: 'status', render: (_, row) => <Tag
              color={row.status === 'COMPLETED' ? 'success' : row.status === 'FAILED' ? 'error' : undefined}>
              {stateLabel(row.status)}
            </Tag> },
            { title: text.processing, key: 'latency', render: (_, row) => row.processing_ms !== null
              ? text.elapsed(numberFormat.format(row.processing_ms)) : text.noValue },
          ]} />
      </Card>
      <Card size="small" title={text.failures}>
        <Space orientation="vertical" style={{ width: '100%' }}>
          {details.recent_failures.some(({ code }) => code === 'INVALID_PROOF')
            && <Alert type="warning" showIcon title={text.failureHint} />}
          <Table size="small" rowKey="key" dataSource={details.recent_failures.map((row, index) => ({
            ...row, key: `${row.occurred_at}:${row.code}:${index}`,
          }))}
            pagination={false} scroll={{ x: 'max-content' }} locale={{ emptyText: text.emptyFailures }} columns={[
              { title: text.timestamp, key: 'received', render: (_, row) => time(row.occurred_at) ?? text.noValue },
              { title: text.result, key: 'result', render: (_, row) => failureLabel(row.code) },
            ]} />
          {details.dropped_failures > 0 && <Typography.Text type="secondary">
            {text.droppedFailures(numberFormat.format(details.dropped_failures))}
          </Typography.Text>}
        </Space>
      </Card>
    </>}
  </Space>;
}
