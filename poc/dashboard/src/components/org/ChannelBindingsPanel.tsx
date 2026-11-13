import { useEffect, useRef, useState } from 'react';
import { Alert, Button, Checkbox, ConfigProvider, Modal, Segmented, Select, Space, Table, Tag } from 'antd';
import { SendOutlined, SlackOutlined } from '@ant-design/icons';
import axios from 'axios';
import { useAuth } from '../../context/AuthContext';
import { useTranslation } from '../../i18n';
import { useChannelBindingsText } from '../../i18n/channelBindings';
import { channelUses, createChannelBinding, getChannelCatalog, listChannelBindings, removeChannelBinding, replaceChannelUses } from '../../services/channelBindingsApi';
import type { ChannelBinding, ChannelCatalog, ChannelUses } from '../../services/channelBindingsApi';

const defaults: ChannelUses = { send_notifications: false, trigger_workflows: false, approve_decisions: false };
type Editor = { action: 'add' } | { action: 'edit' | 'remove'; row: ChannelBinding };
const providerIcon: Record<string, React.ReactNode> = { telegram: <SendOutlined />, slack: <SlackOutlined /> };

export default function ChannelBindingsPanel() {
  const { organization, user, activeDepartmentId } = useAuth();
  const { dir } = useTranslation();
  if (!organization || !user) return null;
  return <ConfigProvider direction={dir}>
    <ScopedPanel key={JSON.stringify([organization.id, user.id, user.role, activeDepartmentId])}
      department={activeDepartmentId || null} admin={user.role === 'ORG_ADMIN'} />
  </ConfigProvider>;
}

function ScopedPanel({ department, admin }: { department: string | null; admin: boolean }) {
  const t = useChannelBindingsText();
  const [scope, setScope] = useState<'organization' | 'department'>(department ? 'department' : 'organization');
  const target = scope === 'department' ? department : null;
  return <Space direction="vertical" size="middle" style={{ width: '100%' }}>
    {admin && department && <Segmented<'organization' | 'department'> value={scope} onChange={setScope} options={[
      { value: 'department', label: t.department }, { value: 'organization', label: t.organization },
    ]} />}
    {admin || target ? <Registry key={target ?? 'organization'} department={target} admin={admin} />
      : <Alert type="info" showIcon message={t.selectDepartment} />}
  </Space>;
}

function Registry({ department, admin }: { department: string | null; admin: boolean }) {
  const t = useChannelBindingsText();
  const [rows, setRows] = useState<ChannelBinding[]>([]);
  const [catalog, setCatalog] = useState<ChannelCatalog>();
  const [cursors, setCursors] = useState<string[]>([]);
  const [next, setNext] = useState<string | null>(null);
  const [refresh, setRefresh] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [connectorError, setConnectorError] = useState(false);
  const [failure, setFailure] = useState<'conflict' | 'saveError'>();
  const [editor, setEditor] = useState<Editor>();
  const [connectorId, setConnectorId] = useState<string>();
  const [channelId, setChannelId] = useState('');
  const [uses, setUses] = useState(defaults);
  const [saving, setSaving] = useState(false);
  const mutation = useRef<AbortController | undefined>(undefined);
  const after = cursors[cursors.length - 1];

  useEffect(() => () => mutation.current?.abort(), []);
  useEffect(() => {
    const request = new AbortController();
    setLoading(true);
    setRows([]);
    setNext(null);
    setLoadError(false);
    void listChannelBindings(department, after, request.signal).then(({ data }) => {
      if (request.signal.aborted) return;
      setRows(data.bindings);
      setNext(data.next_after);
    }).catch(() => { if (!request.signal.aborted) setLoadError(true); })
      .finally(() => { if (!request.signal.aborted) setLoading(false); });
    return () => request.abort();
  }, [department, after, refresh]);

  useEffect(() => {
    const request = new AbortController();
    setCatalog(undefined);
    setConnectorError(false);
    void getChannelCatalog(department, request.signal).then(({ data }) => {
      if (!request.signal.aborted) setCatalog(data);
    }).catch(() => { if (!request.signal.aborted) setConnectorError(true); });
    return () => request.abort();
  }, [department, refresh]);

  const open = (selection: Editor) => {
    setFailure(undefined);
    setConnectorId(undefined);
    setChannelId('');
    setUses(selection.action === 'add' ? defaults : selection.row.uses);
    setEditor(selection);
  };
  const connectors = catalog?.connectors ?? [];
  const available = connectors.filter(connector => connector.channel_ids.length > 0);
  const selected = available.find(connector => connector.id === connectorId);
  const validId = selected?.channel_ids.includes(channelId);
  const channelOptions = selected?.channel_ids.map(id => {
    const name = selected.channel_labels[id];
    return { value: id, label: name ? `${name} · ${id}` : id };
  });
  const providerName = (id: string) => catalog?.providers[id]?.label ?? id;
  const provider = editor?.action === 'add' ? selected?.provider : editor?.row.provider;
  const configurable = provider ? catalog?.providers[provider]?.configurable_uses ?? [] : [];

  const save = async () => {
    if (!admin || !editor || mutation.current || (editor.action === 'add' && (!selected || !validId))) return;
    const request = new AbortController();
    mutation.current = request;
    setSaving(true);
    try {
      if (editor.action === 'add' && selected) {
        await createChannelBinding(department, { connector_id: selected.id, provider: selected.provider, channel_id: channelId }, uses, request.signal);
      } else if (editor.action === 'edit') {
        await replaceChannelUses(editor.row, uses, request.signal);
      } else if (editor.action === 'remove') {
        await removeChannelBinding(editor.row, request.signal);
      }
    } catch (error) {
      if (request.signal.aborted) return;
      setFailure(axios.isAxiosError(error) && error.response?.status === 409 ? 'conflict' : 'saveError');
    } finally {
      if (!request.signal.aborted) {
        mutation.current = undefined;
        setSaving(false);
        setEditor(undefined);
        setCursors([]);
        setRefresh(value => value + 1);
      }
    }
  };

  return <Space direction="vertical" size="middle" style={{ width: '100%' }}>
    <Alert type="info" showIcon message={t.statusNote} description={admin ? undefined : t.readOnly} />
    {failure && <Alert type="warning" showIcon message={t[failure]} />}
    {loadError && <Alert type="error" showIcon message={t.loadError} />}
    {connectorError && <Alert type="warning" showIcon message={t.connectorsError} />}
    <Space wrap>
      {admin && <Button type="primary" disabled={!available.length || loading} onClick={() => open({ action: 'add' })}>{t.add}</Button>}
      <Button disabled={saving} onClick={() => { setFailure(undefined); setCursors([]); setRefresh(value => value + 1); }}>{t.refresh}</Button>
    </Space>
    {admin && catalog && !available.length && <Alert type="info" showIcon message={t.noConfiguredChannels} />}
    <Table<ChannelBinding> size="small" rowKey="id" dataSource={rows} loading={loading} pagination={false}
      locale={{ emptyText: loadError ? t.loadError : t.empty }} scroll={{ x: 'max-content' }} columns={[
        { title: t.provider, key: 'provider', render: (_, row) => <Tag icon={providerIcon[row.provider]}>{providerName(row.provider)}</Tag> },
        { title: t.channelHeading, key: 'channel', render: (_, row) => <Space wrap>
          {row.channel_name && <bdi>{row.channel_name}</bdi>}
          <bdi dir="ltr" style={row.channel_name ? { opacity: 0.65 } : undefined}>{row.channel_id}</bdi>
        </Space> },
        { title: t.status, key: 'status', render: (_, row) => {
          const status = connectors.find(item => item.id === row.connector_id)?.status;
          const label = status === 'CONNECTED' || status === 'CONNECTING' || status === 'DISCONNECTED' || status === 'ERROR' ? t[status] : t.unknown;
          return <Tag color={status === 'CONNECTED' ? 'success' : status === 'ERROR' ? 'error' : undefined}>{label}</Tag>;
        } },
        ...channelUses.map(use => ({
          title: t[use], key: use,
          render: (_: unknown, row: ChannelBinding) => <Checkbox aria-label={t[use]} checked={row.uses[use]} disabled />,
        })),
        ...(admin ? [{ key: 'actions', render: (_: unknown, row: ChannelBinding) => <Space>
          <Button size="small" disabled={!catalog?.providers[row.provider]} onClick={() => open({ action: 'edit', row })}>{t.edit}</Button>
          <Button size="small" danger onClick={() => open({ action: 'remove', row })}>{t.remove}</Button>
        </Space> }] : []),
      ]} />
    {(cursors.length > 0 || next) && <Space>
      <Button disabled={!cursors.length || loading} onClick={() => setCursors(items => items.slice(0, -1))}>{t.previous}</Button>
      <Button disabled={!next || loading} onClick={() => { if (next) setCursors(items => [...items, next]); }}>{t.more}</Button>
    </Space>}
    <Modal open={Boolean(editor)} title={editor?.action === 'remove' ? t.confirmRemove : editor?.action === 'edit' ? t.edit : t.add}
      okText={editor?.action === 'remove' ? t.remove : t.save} cancelText={t.cancel}
      confirmLoading={saving} onOk={() => void save()} onCancel={() => { if (!saving) setEditor(undefined); }}
      okButtonProps={{ danger: editor?.action === 'remove', disabled: editor?.action === 'add' && (!selected || !validId) }}>
      <Space direction="vertical" style={{ width: '100%' }}>
        {editor?.action === 'add' && <>
          <Select aria-label={t.connector} placeholder={t.connector} value={connectorId} onChange={value => {
            setConnectorId(value);
            setChannelId('');
            setUses(defaults);
          }} style={{ width: '100%' }} options={available.map(item => ({ value: item.id, label: `${providerName(item.provider)} · ${item.name}` }))} />
          <Select aria-label={t.channel} placeholder={t.channel} value={channelId || undefined} onChange={setChannelId}
            disabled={!selected} showSearch optionFilterProp="label" style={{ width: '100%' }}
            options={channelOptions} />
          {(!selected || !validId) && <span>{t.required}</span>}
        </>}
        {editor && editor.action !== 'add' && <bdi dir="ltr">{editor.row.channel_id}</bdi>}
        {editor?.action !== 'remove' && configurable.map(use => <Checkbox key={use}
          checked={uses[use]} onChange={event => {
            const checked = event.target.checked;
            setUses(value => ({ ...value, [use]: checked }));
          }}>{t[use]} {provider && !catalog?.providers[provider]?.runtime_supported_uses.includes(use) && <Tag>{t.notActive}</Tag>}</Checkbox>)}
      </Space>
    </Modal>
  </Space>;
}
