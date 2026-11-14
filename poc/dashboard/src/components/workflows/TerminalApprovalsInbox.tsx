import { useEffect, useState } from 'react';
import { Alert, Button, Modal, Space, Table, Tag } from 'antd';
import { Link } from 'react-router-dom';
import { useTranslation } from '../../i18n';
import { useDagApprovalsText } from '../../i18n/dagApprovals';
import { listTerminalApprovals, type ApprovalView, type TerminalApprovalSummary } from '../../services/dagApprovalsApi';
import { WorkflowApprovalPanel } from './WorkflowApprovalPanel';

export function TerminalApprovalsInbox({ department, view, executionId }: { department: string; view: ApprovalView; executionId?: string }) {
  const t = useDagApprovalsText();
  const { locale } = useTranslation();
  const [rows, setRows] = useState<TerminalApprovalSummary[]>([]);
  const [cursors, setCursors] = useState<string[]>([]);
  const [next, setNext] = useState<string | null>(null);
  const [refresh, setRefresh] = useState(0);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [selected, setSelected] = useState<TerminalApprovalSummary>();
  const after = cursors[cursors.length - 1];

  useEffect(() => {
    const request = new AbortController();
    setLoading(true); setFailed(false);
    void listTerminalApprovals(department, after, request.signal, view, executionId).then(({ data }) => {
      if (!request.signal.aborted) { setRows(data.items); setNext(data.next_after); }
    }).catch(() => {
      if (!request.signal.aborted) setFailed(true);
    }).finally(() => {
      if (!request.signal.aborted) setLoading(false);
    });
    return () => request.abort();
  }, [department, after, view, refresh, executionId]);

  return <Space orientation="vertical" style={{ width: '100%' }}>
    {failed && <Alert type="error" title={t.loadError} showIcon />}
    <Button disabled={loading} onClick={() => { setCursors([]); setRefresh(value => value + 1); }}>{t.refresh}</Button>
    <Table<TerminalApprovalSummary> rowKey="id" dataSource={rows} pagination={false} loading={loading}
      scroll={{ x: 'max-content' }} locale={{ emptyText: view === 'history' ? t.emptyHistory : t.empty }} columns={[
        { title: t.workflow, dataIndex: 'workflow_name' },
        { title: t.status, render: (_, item) => <Tag>{item.status}</Tag> },
        { title: view === 'history' ? t.decidedAt : t.expires, render: (_, item) => {
          const value = view === 'history' ? item.resolved_at : item.expires_at;
          return <bdi>{value ? new Date(value).toLocaleString(locale) : '—'}</bdi>;
        } },
        { key: 'review', render: (_, item) => <Button onClick={() => { setSelected(item); setDetailsOpen(true); }}>{t.review}</Button> },
      ]} />
    {(after || next) && <Space>
      <Button disabled={loading || !after} onClick={() => setCursors(items => items.slice(0, -1))}>{t.previous}</Button>
      <Button disabled={loading || !next} onClick={() => { if (next) setCursors(items => [...items, next]); }}>{t.next}</Button>
    </Space>}
    {selected && <Modal open={detailsOpen} width={760} title={t.review} footer={null}
      onCancel={() => setDetailsOpen(false)} afterClose={() => setSelected(undefined)}>
      <Space orientation="vertical" style={{ width: '100%' }}>
        <WorkflowApprovalPanel key={selected.execution_id} executionId={selected.execution_id}
          refresh={0} emptyMessage={t.emptyTerminal} onDecision={() => setRefresh(value => value + 1)} />
        {!executionId && <Link to={`/workflows/${encodeURIComponent(selected.workflow_id)}/logs?execution=${encodeURIComponent(selected.execution_id)}`}>
          {t.logs}
        </Link>}
      </Space>
    </Modal>}
  </Space>;
}
