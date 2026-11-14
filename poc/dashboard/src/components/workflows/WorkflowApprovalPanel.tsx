import { PrEvidence } from './PrEvidence';
import { usePrGovernanceText } from '../../i18n/prGovernance';
import { useEffect, useRef, useState } from 'react';
import { Alert, Button, Card, Popconfirm, Space, Tag, Typography } from 'antd';
import axios from 'axios';
import { usePermissions } from '../../hooks/usePermissions';
import { useWorkflowApprovalText } from '../../i18n/workflowApproval';
import { decideWorkflowApproval, getWorkflowApproval, type WorkflowApproval } from '../../services/workflowApprovals';

export function WorkflowApprovalPanel({ executionId, refresh }: { executionId: string; refresh?: number }) {
  const prText = usePrGovernanceText();
  const generation = useRef(0);
  const requestId = useRef(0);
  const decisionActive = useRef(false);
  const decisionSent = useRef(false);
  const [attempted, setAttempted] = useState(false);
  const text = useWorkflowApprovalText();
  const { canManage } = usePermissions();
  const [approval, setApproval] = useState<WorkflowApproval | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    const scope = ++generation.current;
    let cancelled = false;
    setApproval(null); setError(''); setBusy(false); setAttempted(false);
    decisionActive.current = false; decisionSent.current = false;
    const load = async () => {
      if (decisionActive.current) return;
      const request = ++requestId.current;
      try {
        const { data } = await getWorkflowApproval(executionId);
        if (!cancelled && scope === generation.current && request === requestId.current) { setApproval(data); setError(''); }
      } catch { if (!cancelled && scope === generation.current && request === requestId.current) setError(text.failed); }
    };
    void load();
    return () => { cancelled = true; ++generation.current; };
  }, [executionId, refresh, text.failed]);
  const decide = async (approve: boolean) => {
    if (decisionSent.current) return;
    decisionSent.current = true; decisionActive.current = true; setAttempted(true);
    const scope = generation.current;
    ++requestId.current;
    setBusy(true); setError('');
    try {
      await decideWorkflowApproval(executionId, approve);
      if (scope !== generation.current) return;
      ++requestId.current;
      setApproval(previous => previous ? { ...previous, status: 'RESOLVING' } : null);
    } catch (cause) {
      if (scope !== generation.current) return;
      const detail = axios.isAxiosError(cause) ? cause.response?.data?.detail : null;
      setError(typeof detail === 'string' ? detail : text.failed);
    } finally { if (scope === generation.current) { decisionActive.current = false; setBusy(false); } }
  };
  if (!approval) return error ? <Alert type="error" message={error} /> : null;
  const deadline = new Date(approval.expires_at).getTime();
  const expired = !Number.isFinite(deadline) || deadline <= Date.now();
  const actionable = approval.status === 'PENDING' && !expired && canManage && !busy && !attempted;
  return <Card title={<Space>{text.title}<Tag>{prText.statuses[approval.status] || approval.status}</Tag></Space>}>
    <Space direction="vertical" style={{ width: '100%' }}>
      <Typography.Paragraph>{approval.merge_after_approval ? text.mergeHelp : text.help}</Typography.Paragraph>
      <Typography.Text type="secondary">{text.expires}: {new Date(approval.expires_at).toLocaleString()}</Typography.Text>
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
