import { useEffect, useRef, useState } from 'react';
import { Alert, Button, Card, ConfigProvider, Descriptions, Drawer, Modal, Space, Table, Tabs, Tag, Typography } from 'antd';
import { Link } from 'react-router-dom';
import { TerminalApprovalsInbox } from './TerminalApprovalsInbox';
import { WorkflowApprovalPanel } from './WorkflowApprovalPanel';
import { useAuth } from '../../context/AuthContext';
import { useTranslation } from '../../i18n';
import { useDagApprovalsText } from '../../i18n/dagApprovals';
import { decideDagApproval, listDagApprovals, type ApprovalView, type DagApproval } from '../../services/dagApprovalsApi';

export function DagApprovalsInbox({ open = true, onClose, execution }: {
  open?: boolean; onClose: () => void; execution?: { id: string; department_id?: string | null };
}) {
  const t = useDagApprovalsText();
  const { dir } = useTranslation();
  const { activeDepartmentId, organization, user } = useAuth();
  if (!organization || !user) return null;
  const department = execution ? execution.department_id : activeDepartmentId;
  return <ConfigProvider direction={dir}>
    <Drawer open={open} size="large" title={execution ? t.runApprovals : t.title} onClose={onClose}>
      <ApprovalLists key={JSON.stringify([organization.id, user.id, user.role, department, execution?.id])}
        department={department} execution={execution} />
    </Drawer>
  </ConfigProvider>;
}

function ApprovalLists({ department, execution }: {
  department?: string | null; execution?: { id: string };
}) {
  const t = useDagApprovalsText();
  const [view, setView] = useState<ApprovalView>('pending');
  const [deciding, setDeciding] = useState(false);
  const terminal = execution && <WorkflowApprovalPanel executionId={execution.id} refresh={0}
    emptyMessage={t.emptyTerminal} />;
  if (!department) return terminal || <Alert type="info" title={t.selectDepartment} />;
  const checkpoints = <Inbox key={view} department={department} executionId={execution?.id}
    view={view} onDecisionBusy={setDeciding} />;
  const views = <Tabs activeKey={view} onChange={key => {
    if (!deciding && (key === 'pending' || key === 'history')) setView(key);
  }} items={[{ key: 'pending', label: t.pending }, { key: 'history', label: t.history }]} />;
  return <Space orientation="vertical" size="middle" style={{ width: '100%' }}>
    {views}
    <Card size="small" title={t.checkpoints}>{checkpoints}</Card>
    <Card size="small" title={t.terminal}><TerminalApprovalsInbox key={view} department={department} view={view} executionId={execution?.id} /></Card>
  </Space>;
}

const statusColors = { PENDING: 'gold', APPROVED: 'green', REJECTED: 'red', TIMED_OUT: 'default' };

function Inbox({ department, executionId, view, onDecisionBusy }: {
  department: string; executionId?: string; view: ApprovalView; onDecisionBusy: (busy: boolean) => void;
}) {
  const t = useDagApprovalsText();
  const { locale } = useTranslation();
  const [rows, setRows] = useState<DagApproval[]>([]);
  const [cursors, setCursors] = useState<string[]>([]);
  const [next, setNext] = useState<string | null>(null);
  const [reload, setReload] = useState(0);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<'loadError' | 'decisionError' | 'recorded'>();
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [selected, setSelected] = useState<DagApproval>();
  const mutation = useRef<AbortController | undefined>(undefined);
  const after = cursors[cursors.length - 1];
  useEffect(() => () => mutation.current?.abort(), []);
  useEffect(() => {
    const request = new AbortController();
    setLoading(true);
    setNotice(previous => previous === 'loadError' ? undefined : previous);
    void listDagApprovals(department, after, request.signal, view, executionId).then(({ data }) => {
      if (!request.signal.aborted) { setRows(data.items); setNext(data.next_after); }
    }).catch(() => { if (!request.signal.aborted) setNotice('loadError'); })
      .finally(() => { if (!request.signal.aborted) setLoading(false); });
    return () => request.abort();
  }, [department, after, reload, view, executionId]);

  const decide = async (approve: boolean) => {
    if (!selected?.can_decide || mutation.current) return;
    const request = new AbortController();
    mutation.current = request;
    setBusy(true); onDecisionBusy(true); setNotice(undefined);
    try {
      const response = await decideDagApproval(department, selected.id, approve, request.signal);
      if (!request.signal.aborted) setNotice(response.data.status === 'TIMED_OUT' ? 'decisionError' : 'recorded');
    } catch {
      if (!request.signal.aborted) setNotice('decisionError');
    } finally {
      if (!request.signal.aborted) {
        mutation.current = undefined;
        setBusy(false); onDecisionBusy(false); setDetailsOpen(false); setReload(value => value + 1);
      }
    }
  };
  const date = (seconds: number) => new Date(seconds * 1000).toLocaleString(locale);
  return <Space orientation="vertical" style={{ width: '100%' }}>
    {notice && <Alert type={notice === 'recorded' ? 'success' : 'error'} title={t[notice]} showIcon />}
    <Button disabled={busy || loading} onClick={() => { setNotice(undefined); setCursors([]); setReload(value => value + 1); }}>{t.refresh}</Button>
    <Table<DagApproval> rowKey="id" dataSource={rows} pagination={false} loading={loading}
      scroll={{ x: 'max-content' }} locale={{ emptyText: view === 'history' ? t.emptyHistory : t.empty }} columns={[
        { title: t.workflow, dataIndex: 'workflow_name' },
        { title: t.step, render: (_, item) => <bdi>{item.step_key}</bdi> },
        { title: t.status, render: (_, item) => <Tag color={statusColors[item.status]}>{t[item.status]}</Tag> },
        { title: view === 'history' ? t.decidedAt : t.expires, render: (_, item) => {
          const value = view === 'history' ? item.decided_at : item.expires_at;
          return <bdi>{value != null ? date(value) : '—'}</bdi>;
        } },
        { title: t.votes, render: (_, item) => <bdi>{item.approvals}/{item.quorum}</bdi> },
        { key: 'review', render: (_, item) => <Button onClick={() => { setSelected(item); setDetailsOpen(true); }}>{t.review}</Button> },
      ]} />
    {(after || next) && <Space>
      <Button disabled={busy || loading || !after} onClick={() => setCursors(items => items.slice(0, -1))}>{t.previous}</Button>
      <Button disabled={busy || loading || !next} onClick={() => { if (next) setCursors(items => [...items, next]); }}>{t.next}</Button>
    </Space>}
    {selected && <Modal open={detailsOpen} title={t.review} afterClose={() => setSelected(undefined)}
      onCancel={() => { if (!busy) setDetailsOpen(false); }}
      footer={<Space wrap>
        <Button disabled={busy} onClick={() => setDetailsOpen(false)}>{t.close}</Button>
        {selected.can_decide && <>
          <Button danger disabled={busy} onClick={() => void decide(false)}>{t.reject}</Button>
          <Button type="primary" loading={busy} onClick={() => void decide(true)}>{t.approve}</Button>
        </>}
      </Space>}>
      <Descriptions column={1} items={[
        { key: 'workflow', label: t.workflow, children: selected.workflow_name },
        { key: 'step', label: t.step, children: <bdi>{selected.step_key}</bdi> },
        { key: 'status', label: t.status, children: <Tag color={statusColors[selected.status]}>{t[selected.status]}</Tag> },
        { key: 'decision', label: t.decidedAt, children: selected.decided_at != null ? <bdi>{date(selected.decided_at)}</bdi> : '—' },
        { key: 'personal', label: t.myVote, children: selected.my_vote ? t[selected.my_vote] : '—' },
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
      {!executionId && <Link to={`/workflows/${encodeURIComponent(selected.workflow_id)}/logs?execution=${encodeURIComponent(selected.execution_id)}`}>{t.logs}</Link>}
    </Modal>}
  </Space>;
}
