import { useEffect, useState } from 'react';
import { Alert, Card, Empty, Select, Space, Table } from 'antd';
import { Link } from 'react-router-dom';
import { usePermissions } from '../hooks/usePermissions';
import { getWorkflowReliability, type WorkflowReliability } from '../services/workflowsApi';

export function WorkflowMetricsView() {
  const [window, setWindow] = useState<WorkflowReliability['window']>('7d');
  const [result, setResult] = useState<WorkflowReliability>();
  const [failed, setFailed] = useState(false);
  const { canManage } = usePermissions();

  useEffect(() => {
    const request = new AbortController();
    setResult(undefined);
    setFailed(false);
    getWorkflowReliability(window, request.signal).then(({ data }) => {
      if (!request.signal.aborted) setResult(data);
    }).catch(() => {
      if (!request.signal.aborted) setFailed(true);
    });
    return () => request.abort();
  }, [window]);

  const trend = result?.trend ?? [];
  const largestBucket = Math.max(1, ...trend.map(row => row.completed + row.failed));
  const workflowCount = result?.workflows.length ?? 0;
  const workflowsWithFailures = result?.workflows.filter(row => row.failed > 0).length ?? 0;
  return <Card title="Workflow reliability" extra={<Select aria-label="Reliability time window"
    value={window} onChange={value => setWindow(value as WorkflowReliability['window'])}
    options={[{ value: '24h', label: '24 hours' }, { value: '7d', label: '7 days' }, { value: '30d', label: '30 days' }]} />}>
    {failed && <Alert type="error" showIcon message="Workflow reliability could not be loaded." />}
    {result && <p>{workflowCount} workflows with completed or failed runs · {workflowsWithFailures} with failures</p>}
    {!!trend.length && <div style={{ marginBottom: 20 }} aria-label="Workflow success and failure trend">
      <p>Completed (green) · Failed (red) · Server time</p>
      {trend.map(row => <div key={row.bucket} style={{ display: 'grid', gridTemplateColumns: '155px 1fr', gap: 10, marginBottom: 4 }}>
        <span>{row.bucket}</span>
        <div style={{ display: 'flex', alignItems: 'center' }} title={`${row.completed} completed, ${row.failed} failed`}>
          <span style={{ background: '#34d399', height: 12, width: `${row.completed / largestBucket * 100}%` }} />
          <span style={{ background: '#f87171', height: 12, width: `${row.failed / largestBucket * 100}%` }} />
          <span style={{ marginInlineStart: 8, whiteSpace: 'nowrap' }}>{row.completed} / {row.failed}</span>
        </div>
      </div>)}
    </div>}
    {!failed && <Table dataSource={result?.workflows ?? []} rowKey="workflow_id"
      loading={!result} scroll={{ x: 850 }} pagination={{ pageSize: 8 }}
      locale={{ emptyText: <Empty description="No completed or failed workflow runs in this window." /> }}
      columns={[
        { title: 'Workflow', dataIndex: 'name' },
        { title: 'Failed runs', dataIndex: 'failed' },
        { title: 'Failure rate', render: (_, row) => `${(row.failure_rate * 100).toFixed(1)}%` },
        { title: 'Success rate', render: (_, row) => `${(row.success_rate * 100).toFixed(1)}%` },
        { title: 'Avg. duration', render: (_, row) => row.average_duration_seconds == null ? '—' : `${row.average_duration_seconds}s` },
        { title: 'Avg. cost', render: (_, row) => row.average_cost_usd == null ? '—' : `$${row.average_cost_usd.toFixed(4)}` },
        { title: 'Failure diagnostics', render: (_, row) => <Space direction="vertical">
          {Object.entries(row.failure_counts).map(([category, count]) =>
            <span key={category}>{category.replace(/_/g, ' ')} ({count})</span>)}
          {row.suggestions.map(suggestion => <span key={suggestion.category}>{suggestion.message}</span>)}
          {row.last_failed_execution_id && <Link to={`/workflows/${encodeURIComponent(row.workflow_id)}/logs?execution=${encodeURIComponent(row.last_failed_execution_id)}`}>
            Inspect last failed run
          </Link>}
          {canManage && row.failed > 0 && <Link to={`/workflows?edit=${encodeURIComponent(row.workflow_id)}`}>
            Edit workflow
          </Link>}
        </Space> },
      ]} />}
  </Card>;
}
