import { PrEvidence } from './PrEvidence';
import { usePrGovernanceText } from '../../i18n/prGovernance';
import { useEffect, useRef, useState } from 'react';
import { Alert, Button, Card, Empty, Spin, Popconfirm, Space, Tag, Typography } from 'antd';
import axios from 'axios';
import { usePermissions } from '../../hooks/usePermissions';
import { useWorkflowApprovalText } from '../../i18n/workflowApproval';
import { useTranslation } from '../../i18n';
import { decideWorkflowApproval, getWorkflowApproval, type WorkflowApproval } from '../../services/workflowApprovals';

export function WorkflowApprovalPanel({ executionId, approvalId, refresh, emptyMessage, onDecision }: { executionId: string; approvalId?: string; refresh?: number; emptyMessage?: string; onDecision?: () => void }) {
  const prText = usePrGovernanceText();
  const generation = useRef(0);
  const requestId = useRef(0);
  const decisionActive = useRef(false);
  const [attemptedId, setAttemptedId] = useState<string>();
  const text = useWorkflowApprovalText();
  const { locale } = useTranslation();
  const { canManage } = usePermissions();
  const [approval, setApproval] = useState<WorkflowApproval | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    const scope = ++generation.current;
    let cancelled = false;
    setLoading(true); setApproval(null); setError(''); setBusy(false);
    decisionActive.current = false;
    let fetching = false;
    const load = async () => {
      if (decisionActive.current || fetching) return;
      fetching = true;
      const request = ++requestId.current;
      try {
        const { data } = await getWorkflowApproval(executionId, approvalId);
        if (!cancelled && scope === generation.current && request === requestId.current) { setApproval(data); setError(''); }
      } catch { if (!cancelled && scope === generation.current && request === requestId.current) setError(text.failed); }
      finally {
        fetching = false;
        if (!cancelled && scope === generation.current && request === requestId.current) setLoading(false);
      }
    };
    void load();
    const timer = approvalId ? undefined : window.setInterval(() => void load(), 3000);
    return () => {
      cancelled = true;
      if (timer !== undefined) window.clearInterval(timer);
      ++generation.current;
    };
  }, [executionId, approvalId, refresh, text.failed]);
  const decide = async (approve: boolean, displayedId: string) => {
    if (decisionActive.current || attemptedId === displayedId || approval?.id !== displayedId) return;
    decisionActive.current = true;
    setAttemptedId(displayedId);
    const scope = generation.current;
    ++requestId.current;
    setBusy(true); setError('');
    try {
      await decideWorkflowApproval(executionId, displayedId, approve);
      if (scope !== generation.current) return;
      ++requestId.current;
      setApproval(previous => previous ? { ...previous, status: 'RESOLVING' } : null);
      onDecision?.();
    } catch (cause) {
      if (scope !== generation.current) return;
      const response = axios.isAxiosError(cause) ? cause.response : undefined;
      if (response && [400, 401, 403, 404, 409, 422].includes(response.status)) {
        setAttemptedId(undefined);
      }
      const detail = response?.data?.detail;
      setError(typeof detail === 'string' ? detail : text.failed);
    } finally { if (scope === generation.current) { decisionActive.current = false; setBusy(false); } }
  };
  if (!approval) return error ? <Alert type="error" message={error} /> : loading ? <Spin />
    : emptyMessage ? <Empty description={emptyMessage} /> : null;
  const deadline = new Date(approval.expires_at).getTime();
  const expired = !Number.isFinite(deadline) || deadline <= Date.now();
  const total = 1 + approval.position + approval.remaining_count;
  const attempted = attemptedId === approval.id;
  const actionable = approval.status === 'PENDING' && !expired && canManage && !busy && !attempted;
  return <Card title={<Space>{text.title}<Tag>{prText.statuses[approval.status] || approval.status}</Tag></Space>}>
    <Space direction="vertical" style={{ width: '100%' }}>
      <Typography.Paragraph>{approval.merge_after_approval ? text.mergeHelp : text.help}</Typography.Paragraph>
      {total > 1 && <Typography.Text>{text.progress(approval.position + 1, total)}</Typography.Text>}
      <Typography.Text type="secondary">{text.expires}: <bdi>{new Date(approval.expires_at).toLocaleString(locale)}</bdi></Typography.Text>
      {approval.resolved_by && <Typography.Text>{prText.actor}: <bdi dir="ltr">{approval.resolved_by}</bdi></Typography.Text>}
      {approval.subjects.map((subject, index) => <PrEvidence key={`${subject.repository}:${subject.pull_number}:${index}`} value={subject} />)}
      {expired && approval.status === 'PENDING' && <Alert type="warning" message={prText.expired} />}
      {!canManage && approval.status === 'PENDING' && <Alert type="info" message={prText.readOnly} />}
      <details><summary>{text.report}</summary><pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{approval.report}</pre></details>
      {approval.receipts.map((receipt, index) => <PrEvidence key={receipt.audit_id || `${receipt.repository}:${receipt.pull_number}:${index}`} value={receipt} />)}
      {approval.merge_after_approval && !approval.receipts.length && <Typography.Paragraph type="secondary">{prText.noReceipt}</Typography.Paragraph>}
      {attempted && approval.status === 'PENDING' && <Alert type="warning" message={prText.reconcile} />}
      {approval.status === 'RESOLVING' && <Alert type="info" message={text.resolving} />}
      {(error || approval.error) && <Alert type="error" message={error || approval.error} description={approval.status === 'RESOLVING' || approval.receipts.some(r => ['STARTED', 'UNKNOWN'].includes(r.status)) ? prText.reconcile : prText.evidenceRecovery} />}
      <Space>
        <Popconfirm key={approval.id + ':approve'} title={text.confirm} okText={text.confirmAction} cancelText={text.cancel} onConfirm={() => void decide(true, approval.id)} disabled={!actionable}>
          <Button type="primary" loading={busy} disabled={!actionable}>{approval.merge_after_approval ? text.approveMerge : text.approve}</Button>
        </Popconfirm>
        <Popconfirm key={approval.id + ':reject'} title={text.confirm} okText={text.confirmAction} cancelText={text.cancel} onConfirm={() => void decide(false, approval.id)} disabled={!actionable}>
          <Button danger disabled={!actionable}>{text.reject}</Button>
        </Popconfirm>
      </Space>
    </Space>
  </Card>;
}
