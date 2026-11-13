import { useEffect, useRef, useState } from 'react';
import { Alert, Button, Card, ConfigProvider, Modal, Select, Space, Table, Tag, Typography } from 'antd';
import axios from 'axios';
import { useAuth } from '../../context/AuthContext';
import { usePermissions } from '../../hooks/usePermissions';
import { useTranslation } from '../../i18n';
import { useExternalIdentitiesText } from '../../i18n/externalIdentities';
import {
  confirmIdentityChallenge, getIdentityChallenge, getIdentityConnectors, getManagedIdentityLinks,
  getPersonalIdentityLinks, issueIdentityChallenge, revokeManagedIdentity, unlinkPersonalIdentity,
} from '../../services/externalIdentitiesApi';
import type {
  IdentityChallenge, IdentityConnector, IdentityLink, ManagedIdentityLink,
} from '../../services/externalIdentitiesApi';

type Failure = 'expired' | 'rate' | 'conflict' | 'unavailable' | 'failed';
type ActiveChallenge = IdentityChallenge & { connector: string; subject?: string };
const fullWidth = { width: '100%' };
const providerName = (provider: string) => provider === 'telegram' ? 'Telegram' : provider === 'slack' ? 'Slack' : provider;
const failureOf = (error: unknown): Failure => {
  if (!axios.isAxiosError(error)) return 'failed';
  const status = error.response?.status;
  const code = error.response?.data?.detail?.code;
  if (status === 429) return 'rate';
  if (status === 410 || code === 'CHALLENGE_REPLAY' || code === 'PROVIDER_ROTATED') return 'expired';
  if (code === 'IDENTITY_CONFLICT') return 'conflict';
  if (status === 403 || status === 404) return 'unavailable';
  return 'failed';
};

export default function ExternalIdentitiesPanel() {
  const { organization, user, activeDepartmentId } = useAuth();
  const { canManage } = usePermissions();
  const { dir } = useTranslation();
  if (!user || !organization) return null;
  const key = JSON.stringify([organization.id, user.id, user.role, activeDepartmentId, canManage]);
  return <ConfigProvider direction={dir}>
    <ScopedIdentities key={key} department={canManage ? activeDepartmentId : null} />
  </ConfigProvider>;
}

function ScopedIdentities({ department }: { department: string | null }) {
  const [revision, setRevision] = useState(0);
  const refresh = () => setRevision(value => value + 1);
  return <Space direction="vertical" size="middle" style={fullWidth}>
    <PersonalIdentities revision={revision} refresh={refresh} />
    {department && <ManagedIdentities department={department} revision={revision} refresh={refresh} />}
  </Space>;
}

function useMutation() {
  const active = useRef<AbortController | undefined>(undefined);
  const [busy, setBusy] = useState(false);
  useEffect(() => () => active.current?.abort(), []);
  const run = async (action: (signal: AbortSignal) => Promise<void>, onError: (error: unknown) => void) => {
    if (active.current) return;
    const request = new AbortController();
    active.current = request;
    setBusy(true);
    try {
      await action(request.signal);
    } catch (error) {
      if (!request.signal.aborted) onError(error);
    } finally {
      if (!request.signal.aborted) {
        active.current = undefined;
        setBusy(false);
      }
    }
  };
  return { busy, run };
}

function PersonalIdentities({ revision, refresh }: { revision: number; refresh: () => void }) {
  const t = useExternalIdentitiesText();
  const [links, setLinks] = useState<IdentityLink[]>([]);
  const [connectors, setConnectors] = useState<IdentityConnector[]>([]);
  const [connector, setConnector] = useState<string>();
  const [challenge, setChallenge] = useState<ActiveChallenge>();
  const [remove, setRemove] = useState<IdentityLink>();
  const [failure, setFailure] = useState<Failure>();
  const [catalogFailed, setCatalogFailed] = useState(false);
  const [loading, setLoading] = useState(true);
  const { busy, run } = useMutation();

  useEffect(() => {
    const request = new AbortController();
    setLoading(true);
    setCatalogFailed(false);
    void Promise.allSettled([getPersonalIdentityLinks(request.signal), getIdentityConnectors(request.signal)])
      .then(([accounts, available]) => {
        if (request.signal.aborted) return;
        if (accounts.status === 'fulfilled') setLinks(accounts.value.data);
        else {
          setLinks([]);
          setFailure(failureOf(accounts.reason));
        }
        if (available.status === 'fulfilled') {
          const options = available.value.data;
          setConnectors(options);
          setConnector(current => options.some(item => item.id === current) ? current : undefined);
        } else {
          setConnectors([]);
          setConnector(undefined);
          setCatalogFailed(true);
        }
      })
      .finally(() => { if (!request.signal.aborted) setLoading(false); });
    return () => request.abort();
  }, [revision]);

  const id = challenge?.id;
  const expires = challenge?.expires_at;
  const verified = Boolean(challenge?.subject);
  useEffect(() => {
    if (!id || !expires) return;
    const request = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    const expire = () => {
      request.abort();
      setChallenge(current => current?.id === id ? undefined : current);
      setFailure('expired');
    };
    const poll = async () => {
      try {
        const { data } = await getIdentityChallenge(id, request.signal);
        if (request.signal.aborted) return;
        if (data.subject) {
          const subject = data.subject;
          setChallenge(current => current?.id === id ? { ...current, subject, code: '' } : current);
          return;
        }
      } catch (error) {
        if (request.signal.aborted) return;
        const reason = failureOf(error);
        if (reason === 'expired' || reason === 'unavailable') {
          if (reason === 'expired') expire();
          else {
            setChallenge(current => current?.id === id ? undefined : current);
            setFailure(reason);
          }
          return;
        }
      }
      if (!request.signal.aborted) timer = setTimeout(() => void poll(), 2500);
    };
    const deadline = setTimeout(expire, Math.max(0, expires * 1000 - Date.now()));
    if (!verified) timer = setTimeout(() => void poll(), 1000);
    return () => { request.abort(); clearTimeout(timer); clearTimeout(deadline); };
  }, [id, expires, verified]);

  const onError = (error: unknown) => setFailure(failureOf(error));
  return <Card title={t.personal} extra={<Button onClick={() => { setFailure(undefined); refresh(); }} disabled={loading || busy}>{t.refresh}</Button>}>
    <Space direction="vertical" size="middle" style={fullWidth}>
      {failure && <Alert type="error" showIcon message={t[failure]} />}
      {catalogFailed && <Alert type="warning" showIcon message={t.catalogFailed} />}
      <Table<IdentityLink> rowKey="id" dataSource={links} loading={loading} pagination={false}
        scroll={{ x: 'max-content' }} locale={{ emptyText: loading ? t.loading : t.empty }} columns={[
          { title: t.provider, key: 'provider', render: (_, row) => providerName(row.provider) },
          { title: t.connector, key: 'connector', render: (_, row) => <bdi>{connectors.find(item => item.id === row.connector_id)?.name ?? row.connector_id}</bdi> },
          { title: t.subject, key: 'subject', render: (_, row) => <bdi dir="ltr">{row.subject}</bdi> },
          { key: 'verified', render: () => <Tag color="success">{t.verified}</Tag> },
          { key: 'unlink', render: (_, row) => <Button danger size="small" aria-label={t.unlink + ' ' + row.subject}
            disabled={busy} onClick={() => setRemove(row)}>{t.unlink}</Button> },
        ]} />
      <Space wrap>
        <Select aria-label={t.connector} placeholder={t.select} value={connector} onChange={setConnector}
          style={{ minWidth: 230 }} disabled={busy || Boolean(challenge)} loading={loading}
          options={connectors.map(item => ({ value: item.id, label: providerName(item.provider) + ' · ' + item.name }))} />
        <Button type="primary" loading={busy && !challenge && !remove} disabled={!connector || Boolean(challenge) || loading}
          onClick={() => {
            if (!connector) return;
            setFailure(undefined);
            void run(async signal => {
              const { data } = await issueIdentityChallenge(connector, signal);
              if (!signal.aborted) setChallenge({ ...data, connector });
            }, onError);
          }}>{t.start}</Button>
      </Space>
      {!loading && !catalogFailed && !connectors.length && <Typography.Text type="secondary">{t.noConnectors}</Typography.Text>}
      {challenge && <ChallengeCard challenge={challenge} busy={busy} cancel={() => setChallenge(undefined)}
        confirm={() => {
          if (!challenge.subject) return;
          const subject = challenge.subject;
          setFailure(undefined);
          void run(async signal => {
            await confirmIdentityChallenge(challenge.id, subject, signal);
            if (signal.aborted) return;
            setChallenge(undefined);
            refresh();
          }, error => {
            if (failureOf(error) === 'expired' || failureOf(error) === 'unavailable') setChallenge(undefined);
            onError(error);
          });
        }} />}
    </Space>
    <Modal open={Boolean(remove)} title={t.unlinkPrompt} okText={t.unlink} cancelText={t.cancel} confirmLoading={busy}
      okButtonProps={{ danger: true }} onCancel={() => { if (!busy) setRemove(undefined); }} onOk={() => {
        if (!remove) return;
        setFailure(undefined);
        void run(async signal => {
          await unlinkPersonalIdentity(remove.id, signal);
          if (signal.aborted) return;
          setLinks(rows => rows.filter(row => row.id !== remove.id));
          setRemove(undefined);
          setChallenge(current => current?.connector === remove.connector_id ? undefined : current);
          refresh();
        }, error => { setRemove(undefined); onError(error); refresh(); });
      }}><bdi dir="ltr">{remove?.subject}</bdi></Modal>
  </Card>;
}

function ChallengeCard({ challenge, busy, cancel, confirm }: {
  challenge: ActiveChallenge; busy: boolean; cancel: () => void; confirm: () => void;
}) {
  const t = useExternalIdentitiesText();
  const { dir } = useTranslation();
  const [copyState, setCopyState] = useState<'copied' | 'copyError'>();
  const command = (challenge.provider === 'telegram' ? '/start ' : '/platform-link ') + challenge.code;
  const expiration = new Date(challenge.expires_at * 1000).toLocaleTimeString(dir === 'rtl' ? 'he' : 'en');
  return <Card size="small">
    <Space direction="vertical" style={fullWidth}>
      {challenge.subject ? <>
        <Alert type="info" showIcon message={t.ready} description={<bdi dir="ltr">{challenge.subject}</bdi>} />
        <Button type="primary" loading={busy} onClick={confirm}>{t.confirm}</Button>
      </> : <>
        <Typography.Text>{challenge.provider === 'telegram' ? t.telegram : t.slack}</Typography.Text>
        <Space wrap>
          <Typography.Text code><bdi dir="ltr">{command}</bdi></Typography.Text>
          <Button onClick={() => {
            void (async () => {
              try { await navigator.clipboard.writeText(command); setCopyState('copied'); }
              catch { setCopyState('copyError'); }
            })();
          }}>{t.copy}</Button>
        </Space>
        {copyState && <Typography.Text role="status">{t[copyState]}</Typography.Text>}
        <Typography.Text role="status">{t.waiting} <bdi>{expiration}</bdi></Typography.Text>
      </>}
      <Button disabled={busy} onClick={cancel}>{t.cancel}</Button>
    </Space>
  </Card>;
}

function ManagedIdentities({ department, revision, refresh }: { department: string; revision: number; refresh: () => void }) {
  const t = useExternalIdentitiesText();
  const [rows, setRows] = useState<ManagedIdentityLink[]>([]);
  const [cursors, setCursors] = useState<string[]>([]);
  const [next, setNext] = useState<string | null>(null);
  const [selected, setSelected] = useState<ManagedIdentityLink>();
  const [failure, setFailure] = useState<Failure>();
  const [loading, setLoading] = useState(true);
  const { busy, run } = useMutation();
  const after = cursors[cursors.length - 1];
  useEffect(() => {
    const request = new AbortController();
    setLoading(true);
    setRows([]);
    setNext(null);
    void getManagedIdentityLinks(department, after, request.signal).then(({ data }) => {
      if (!request.signal.aborted) {
        setRows(data.links);
        setNext(data.next_after);
      }
    }).catch(error => { if (!request.signal.aborted) setFailure(failureOf(error)); })
      .finally(() => { if (!request.signal.aborted) setLoading(false); });
    return () => request.abort();
  }, [department, after, revision]);

  return <Card title={t.management}>
    <Space direction="vertical" size="middle" style={fullWidth}>
      {failure && <Alert type="error" showIcon message={t[failure]} />}
      <Table<ManagedIdentityLink> rowKey="id" dataSource={rows} loading={loading} pagination={false}
        scroll={{ x: 'max-content' }} locale={{ emptyText: loading ? t.loading : t.empty }} columns={[
          { title: t.member, key: 'member', render: (_, row) => <bdi>{row.member_name}</bdi> },
          { title: t.provider, key: 'provider', render: (_, row) => providerName(row.provider) },
          { title: t.connector, key: 'connector', render: (_, row) => <bdi dir="ltr">{row.connector_id}</bdi> },
          { title: t.subject, key: 'subject', render: (_, row) => <bdi dir="ltr">{row.subject}</bdi> },
          { key: 'revoke', render: (_, row) => row.can_revoke
            ? <Button danger size="small" aria-label={t.revoke + ' ' + row.member_name}
              disabled={busy} onClick={() => setSelected(row)}>{t.revoke}</Button>
            : <Typography.Text type="secondary">{t.adminOnly}</Typography.Text> },
        ]} />
      <Space wrap>
        <Button disabled={loading || busy} onClick={() => { setCursors([]); setFailure(undefined); refresh(); }}>{t.refresh}</Button>
        <Button disabled={!after || loading || busy} onClick={() => { setFailure(undefined); setCursors(items => items.slice(0, -1)); }}>{t.previous}</Button>
        <Button disabled={!next || loading || busy} onClick={() => { if (next) { setFailure(undefined); setCursors(items => [...items, next]); } }}>{t.next}</Button>
      </Space>
    </Space>
    <Modal open={Boolean(selected)} title={t.revokePrompt} okText={t.revoke} cancelText={t.cancel} confirmLoading={busy}
      okButtonProps={{ danger: true }} onCancel={() => { if (!busy) setSelected(undefined); }} onOk={() => {
        if (!selected) return;
        setFailure(undefined);
        void run(async signal => {
          await revokeManagedIdentity(department, selected.id, signal);
          if (signal.aborted) return;
          setRows(items => items.filter(row => row.id !== selected.id));
          setSelected(undefined);
          setCursors([]);
          refresh();
        }, error => { setSelected(undefined); setFailure(failureOf(error)); refresh(); });
      }}><bdi>{selected?.member_name}</bdi> · <bdi dir="ltr">{selected?.subject}</bdi></Modal>
  </Card>;
}
