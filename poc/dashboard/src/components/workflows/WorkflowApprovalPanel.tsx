import { useEffect, useState } from 'react';
import { Alert, Button, Card, Popconfirm, Space, Tag, Typography } from 'antd';
import axios from 'axios';
import { usePermissions } from '../../hooks/usePermissions';
import { useWorkflowApprovalText } from '../../i18n/workflowApproval';
import { decideWorkflowApproval, getWorkflowApproval, type WorkflowApproval } from '../../services/workflowApprovals';

export function WorkflowApprovalPanel({ executionId }: { executionId: string }) {
  const text = useWorkflowApprovalText();
  const { canManage } = usePermissions();
  const [approval, setApproval] = useState<WorkflowApproval | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let cancelled = false;
    setApproval(null); setError('');
    const load = async () => {
      try {
        const { data } = await getWorkflowApproval(executionId);
        if (!cancelled) { setApproval(data); setError(''); }
      } catch { if (!cancelled) setError(text.failed); }
    };
    void load();
    const timer = setInterval(load, 5000);
    return () => { cancelled = true; clearInterval(timer); };
  }, [executionId, text.failed]);
  const decide = async (approve: boolean) => {
    setBusy(true); setError('');
    try {
      await decideWorkflowApproval(executionId, approve);
      setApproval(previous => previous ? { ...previous, status: 'RESOLVING' } : null);
    } catch (cause) {
      const detail = axios.isAxiosError(cause) ? cause.response?.data?.detail : null;
      setError(typeof detail === 'string' ? detail : text.failed);
    } finally { setBusy(false); }
  };
  if (!approval) return error ? <Alert type="error" message={error} /> : null;
  const expired = new Date(approval.expires_at).getTime() <= Date.now();
  const actionable = approval.status === 'PENDING' && !expired && canManage && !busy;
  return <Card title={<Space>{text.title}<Tag>{approval.status}</Tag></Space>}>
    <Space direction="vertical" style={{ width: '100%' }}>
      <Typography.Paragraph>{approval.merge_after_approval ? text.mergeHelp : text.help}</Typography.Paragraph>
      <Typography.Text type="secondary">{text.expires}: {new Date(approval.expires_at).toLocaleString()}</Typography.Text>
      {approval.subjects.map(subject => <div key={`${subject.repository}:${subject.pull_number}`}>
        <a href={subject.url} target="_blank" rel="noreferrer">{subject.repository} #{subject.pull_number}</a>{' '}
        <Typography.Text code>{subject.head_sha}</Typography.Text>
      </div>)}
      <details><summary>{text.report}</summary><pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{approval.report}</pre></details>
      {approval.receipts.map(receipt => <div key={`${receipt.repository}:${receipt.pull_number}`}>
        {receipt.repository} #{receipt.pull_number}: {receipt.status} {receipt.merge_commit_sha || ''}
      </div>)}
      {approval.status === 'RESOLVING' && <Alert type="info" message={text.resolving} />}
      {(error || approval.error) && <Alert type="error" message={error || approval.error} />}
      <Space>
        <Popconfirm title={text.confirm} onConfirm={() => void decide(true)} disabled={!actionable}>
          <Button type="primary" loading={busy} disabled={!actionable}>{approval.merge_after_approval ? text.approveMerge : text.approve}</Button>
        </Popconfirm>
        <Popconfirm title={text.confirm} onConfirm={() => void decide(false)} disabled={!actionable}>
          <Button danger disabled={!actionable}>{text.reject}</Button>
        </Popconfirm>
      </Space>
    </Space>
  </Card>;
}
