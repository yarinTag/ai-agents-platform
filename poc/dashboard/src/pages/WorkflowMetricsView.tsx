import { useWorkflowMetricsText } from '../i18n/workflowMetrics';
import { useEffect, useState } from 'react';
import { Alert, Card, Empty, Select, Space, Table } from 'antd';
import { Link } from 'react-router-dom';
import { usePermissions } from '../hooks/usePermissions';
import { getWorkflowReliability, type WorkflowReliability } from '../services/workflowsApi';

export function WorkflowMetricsView() {
  const text = useWorkflowMetricsText();
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
  return <Card title={text.title} extra={<Select aria-label={text.window}
    value={window} onChange={value => setWindow(value as WorkflowReliability['window'])}
    options={[{ value: '24h', label: text.hours }, { value: '7d', label: text.week }, { value: '30d', label: text.month }]} />}>
    {failed && <Alert type="error" showIcon message={text.failed} />}
    {result && <p>{text.totals} {workflowCount} · {text.withFailures} {workflowsWithFailures}</p>}
    {!!trend.length && <div style={{ marginBottom: 20 }} aria-label={text.trend}>
      <p><span style={{ color: '#34d399' }}>{text.completed}</span> · <span style={{ color: '#f87171' }}>{text.failures}</span> · UTC</p>
      {trend.map(row => <div key={row.bucket} style={{ display: 'grid', gridTemplateColumns: '155px 1fr', gap: 10, marginBottom: 4 }}>
        <span>{row.bucket}</span>
        <div style={{ display: 'flex', alignItems: 'center' }} title={`${text.completed} ${row.completed}, ${text.failures} ${row.failed}`}>
          <span style={{ background: '#34d399', height: 12, width: `${row.completed / largestBucket * 100}%` }} />
          <span style={{ background: '#f87171', height: 12, width: `${row.failed / largestBucket * 100}%` }} />
          <span style={{ marginInlineStart: 8, whiteSpace: 'nowrap' }}>{row.completed} / {row.failed}</span>
        </div>
      </div>)}
    </div>}
    {!failed && <Table dataSource={result?.workflows ?? []} rowKey="workflow_id"
      loading={!result} scroll={{ x: 850 }} pagination={{ pageSize: 8 }}
      locale={{ emptyText: <Empty description={text.empty} /> }}
      columns={[
        { title: text.workflow, dataIndex: 'name' },
        { title: text.failedRuns, dataIndex: 'failed' },
        { title: text.failureRate, render: (_, row) => `${(row.failure_rate * 100).toFixed(1)}%` },
        { title: text.successRate, render: (_, row) => `${(row.success_rate * 100).toFixed(1)}%` },
        { title: text.duration, render: (_, row) => row.average_duration_seconds == null ? '—' : `${row.average_duration_seconds}s` },
        { title: text.cost, render: (_, row) => row.average_cost_usd == null ? '—' : `$${row.average_cost_usd.toFixed(4)}` },
        { title: text.diagnostics, render: (_, row) => <Space direction="vertical">
          {Object.entries(row.failure_counts).map(([category, count]) =>
            <span key={category}>{text.categories[category as keyof typeof text.categories] || category} ({count})</span>)}
          {row.suggestions.map(suggestion => <span key={suggestion.category}>{text.suggestions[suggestion.category as keyof typeof text.suggestions] || suggestion.message}</span>)}
          {row.last_failed_execution_id && <Link to={`/workflows/${encodeURIComponent(row.workflow_id)}/logs?execution=${encodeURIComponent(row.last_failed_execution_id)}`}>
            {text.logs}
          </Link>}
          {canManage && row.failed > 0 && <Link to={`/workflows?edit=${encodeURIComponent(row.workflow_id)}`}>
            {text.edit}
          </Link>}
        </Space> },
      ]} />}
  </Card>;
}
