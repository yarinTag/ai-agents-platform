import { useEffect, useRef, useState } from 'react';
import { Alert, Button, ConfigProvider, Descriptions, Drawer, Modal, Space, Table, Typography } from 'antd';
import { Link } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { useTranslation } from '../../i18n';
import { useDagApprovalsText } from '../../i18n/dagApprovals';
import { decideDagApproval, listDagApprovals, type DagApproval } from '../../services/dagApprovalsApi';

export function DagApprovalsInbox({ onClose }: { onClose: () => void }) {
  const t = useDagApprovalsText();
  const { dir } = useTranslation();
  const { activeDepartmentId, organization, user } = useAuth();
  return <ConfigProvider direction={dir}>
    <Drawer open size="large" title={t.title} onClose={onClose}>
      {activeDepartmentId && organization && user
        ? <Inbox key={JSON.stringify([organization.id, user.id, user.role, activeDepartmentId])} department={activeDepartmentId} />
        : <Alert type="info" title={t.selectDepartment} />}
    </Drawer>
  </ConfigProvider>;
}

function Inbox({ department }: { department: string }) {
  const t = useDagApprovalsText();
  const { locale } = useTranslation();
  const [rows, setRows] = useState<DagApproval[]>([]);
  const [cursors, setCursors] = useState<string[]>([]);
  const [next, setNext] = useState<string | null>(null);
  const [reload, setReload] = useState(0);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<'loadError' | 'decisionError' | 'recorded'>();
  const [selected, setSelected] = useState<DagApproval>();
  const mutation = useRef<AbortController | undefined>(undefined);
  const after = cursors[cursors.length - 1];
  useEffect(() => () => mutation.current?.abort(), []);
  useEffect(() => {
    const request = new AbortController();
    setLoading(true); setRows([]); setNext(null); setSelected(undefined);
    void listDagApprovals(department, after, request.signal).then(({ data }) => {
      if (!request.signal.aborted) { setRows(data.items); setNext(data.next_after); }
    }).catch(() => { if (!request.signal.aborted) setNotice('loadError'); })
      .finally(() => { if (!request.signal.aborted) setLoading(false); });
    return () => request.abort();
  }, [department, after, reload]);

  const decide = async (approve: boolean) => {
    if (!selected?.can_decide || mutation.current) return;
    const request = new AbortController();
    mutation.current = request;
    setBusy(true); setNotice(undefined);
    try {
      const response = await decideDagApproval(department, selected.id, approve, request.signal);
      if (!request.signal.aborted) setNotice(response.data.status === 'TIMED_OUT' ? 'decisionError' : 'recorded');
    } catch {
      if (!request.signal.aborted) setNotice('decisionError');
    } finally {
      if (!request.signal.aborted) {
        mutation.current = undefined;
        setBusy(false); setSelected(undefined); setReload(value => value + 1);
      }
    }
  };
  const date = (seconds: number) => new Date(seconds * 1000).toLocaleString(locale);
  return <Space orientation="vertical" style={{ width: '100%' }}>
    {notice && <Alert type={notice === 'recorded' ? 'success' : 'error'} title={t[notice]} showIcon />}
    <Button disabled={busy || loading} onClick={() => { setNotice(undefined); setCursors([]); setReload(value => value + 1); }}>{t.refresh}</Button>
    <Table<DagApproval> rowKey="id" dataSource={rows} pagination={false} loading={loading}
      scroll={{ x: 'max-content' }} locale={{ emptyText: t.empty }} columns={[
        { title: t.workflow, dataIndex: 'workflow_name' },
        { title: t.step, render: (_, item) => <bdi>{item.step_key}</bdi> },
        { title: t.expires, render: (_, item) => <bdi>{date(item.expires_at)}</bdi> },
        { title: t.votes, render: (_, item) => <bdi>{item.approvals}/{item.quorum}</bdi> },
        { key: 'review', render: (_, item) => <Button onClick={() => setSelected(item)}>{t.review}</Button> },
      ]} />
    {(after || next) && <Space>
      <Button disabled={busy || loading || !after} onClick={() => setCursors(items => items.slice(0, -1))}>{t.previous}</Button>
      <Button disabled={busy || loading || !next} onClick={() => { if (next) setCursors(items => [...items, next]); }}>{t.next}</Button>
    </Space>}
    {selected && <Modal open title={t.review} onCancel={() => { if (!busy) setSelected(undefined); }}
      footer={<Space wrap>
        <Button disabled={busy} onClick={() => setSelected(undefined)}>{t.close}</Button>
        {selected.can_decide && <>
          <Button danger disabled={busy} onClick={() => void decide(false)}>{t.reject}</Button>
          <Button type="primary" loading={busy} onClick={() => void decide(true)}>{t.approve}</Button>
        </>}
      </Space>}>
      <Descriptions column={1} items={[
        { key: 'workflow', label: t.workflow, children: selected.workflow_name },
        { key: 'step', label: t.step, children: <bdi>{selected.step_key}</bdi> },
        { key: 'expires', label: t.expires, children: <bdi>{date(selected.expires_at)}</bdi> },
        { key: 'roles', label: t.roles, children: <bdi>{selected.approver_roles.join(', ')}</bdi> },
        { key: 'cost', label: t.cost, children: new Intl.NumberFormat(locale, {
          style: 'currency', currency: 'USD', maximumFractionDigits: 6,
        }).format(selected.cost_usd) },
      ]} />
      {selected.outputs.map(output => <section key={output.step_key}>
        <Typography.Text strong><bdi>{output.step_key}</bdi>{output.truncated ? ` · ${t.truncated}` : ''}</Typography.Text>
        <pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }} dir="auto">{output.excerpt}</pre>
      </section>)}
      {selected.omitted_outputs > 0 && <p>{t.omitted}: {selected.omitted_outputs}</p>}
      <Link to={`/workflows/${encodeURIComponent(selected.workflow_id)}/logs?execution=${encodeURIComponent(selected.execution_id)}`}>{t.logs}</Link>
    </Modal>}
  </Space>;
}
