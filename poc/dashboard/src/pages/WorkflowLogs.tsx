import { useWorkflowRunText } from '../i18n/workflowRun';
import React, { useEffect, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { Alert, Button, Card, Col, Collapse, Empty, Input, Row, Select, Space, Spin, Tag, Typography } from 'antd';
import { ReloadOutlined, DownloadOutlined } from '@ant-design/icons';
import axios from 'axios';
import { getWorkflow, getWorkflowExecutions, getWorkflowExecution } from '../services/api';
import { PlatformWorkflow, WorkflowExecution } from '../types/mcp';
import { StepEventTimeline } from '../components/workflows/StepEventTimeline';

const { Text, Title } = Typography;
const active = (status: string) => ['QUEUED', 'RUNNING'].includes(status);
const statusColor = (status: string) => status === 'FAILED' ? 'error' : status === 'COMPLETED' ? 'success' : 'processing';
const preStyle: React.CSSProperties = { whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', maxHeight: 420, overflow: 'auto', fontSize: 12 };
const clamp: React.CSSProperties = { display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden', marginTop: 4 };
const formatTime = (value?: string) => (value ? new Date(value).toLocaleString() : '—');
const duration = (start?: string, end?: string) => {
  if (!start) return '';
  const ms = (end ? new Date(end).getTime() : Date.now()) - new Date(start).getTime();
  if (!Number.isFinite(ms) || ms < 0) return '';
  const seconds = Math.round(ms / 1000);
  return seconds < 60 ? `${seconds}s` : `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
};

export const WorkflowLogsPage: React.FC = () => {
  const runText = useWorkflowRunText();
  const { workflowId } = useParams<{ workflowId: string }>();
  const [params, setParams] = useSearchParams();
  const selectedId = params.get('execution');
  const [workflow, setWorkflow] = useState<PlatformWorkflow | null>(null);
  const [runs, setRuns] = useState<WorkflowExecution[]>([]);
  const [execution, setExecution] = useState<WorkflowExecution | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [refresh, setRefresh] = useState(0);
  const [mode, setMode] = useState('ALL');
  const [search, setSearch] = useState('');

  useEffect(() => {
    if (!workflowId) return;
    let disposed = false;
    setExecution(null);
    setLoading(true);
    const load = async () => {
      try {
        const [wf, history] = await Promise.all([getWorkflow(workflowId), getWorkflowExecutions(workflowId, 200)]);
        const id = selectedId || history.data[0]?.id;
        const detail = id ? (await getWorkflowExecution(id)).data : null;
        if (detail && detail.workflow_id !== workflowId) throw new Error('Execution does not belong to this workflow');
        if (!disposed) {
          setWorkflow(wf.data); setRuns(history.data); setExecution(detail); setError('');
        }
      } catch (cause: unknown) {
        if (!disposed) {
          const detail = axios.isAxiosError(cause) ? cause.response?.data?.detail : null;
          setError(typeof detail === 'string' ? detail : cause instanceof Error ? cause.message : 'Unable to load workflow logs');
        }
      } finally { if (!disposed) setLoading(false); }
    };
    void load();
    const timer = setInterval(load, 5000);
    return () => { disposed = true; clearInterval(timer); };
  }, [workflowId, selectedId, refresh]);

  const download = () => {
    if (!execution) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify(execution, null, 2)], { type: 'application/json' }));
    const anchor = document.createElement('a'); anchor.href = url; anchor.download = `${execution.id}.json`; anchor.click();
    URL.revokeObjectURL(url);
  };
  const visibleRuns = runs.filter(run => mode === 'ALL' || (mode === 'PLAYGROUND' ? run.trigger_type === 'PLAYGROUND' : run.trigger_type !== 'PLAYGROUND'));
  const steps = execution?.step_runs || [];

  return <div style={{ padding: 24 }}>
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Link to="/workflows">← Workflows</Link>
      <Space wrap style={{ justifyContent: 'space-between', width: '100%' }}>
        <div><Title level={3} style={{ margin: 0 }}>{workflow?.name || 'Workflow'} · Logs</Title>
          <Text type="secondary">Run history, step output and runtime diagnostics. Updates every 5 seconds.</Text></div>
        <Button icon={<ReloadOutlined />} onClick={() => setRefresh(value => value + 1)}>Refresh</Button>
      </Space>
      {error && <Alert type="error" showIcon message="Unable to load logs" description={error} />}
      {loading && !workflow ? <Spin /> : <Row gutter={[20, 20]}>
        <Col xs={24} lg={8}>
          <Card title={`Runs (${runs.length})`}>
            <Select value={mode} onChange={setMode} style={{ width: '100%', marginBottom: 16 }} options={[
              { value: 'ALL', label: 'All runs' }, { value: 'PLAYGROUND', label: 'Playground' }, { value: 'LIVE', label: 'Live runs' }
            ]} />
            {!visibleRuns.length && <Empty description="No runs yet. Launch a run from Workflows." />}
            <Space direction="vertical" style={{ width: '100%', maxHeight: '75vh', overflow: 'auto' }}>
              {visibleRuns.map(run => <Button key={run.id} block type={execution?.id === run.id ? 'primary' : 'default'}
                style={{ height: 'auto', padding: 12, textAlign: 'start', whiteSpace: 'normal' }} onClick={() => setParams({ execution: run.id })}>
                <div><Tag color={statusColor(run.status)}>{run.status}</Tag><Tag>{run.trigger_type}</Tag></div>
                <div style={{ fontFamily: 'monospace', fontSize: 11 }}>{run.id}</div>
                <div>{formatTime(run.created_at)}{run.completed_at && <Text type="secondary"> · {duration(run.started_at, run.completed_at)}</Text>}</div>
                {run.error_message && <Text type="danger" style={clamp}>{run.error_message}</Text>}
              </Button>)}
            </Space>
            {runs.length === 200 && <Text type="secondary">Showing the latest 200 runs.</Text>}
          </Card>
        </Col>
        <Col xs={24} lg={16}>
          {!execution ? <Empty description="Select a run to inspect its logs" /> : <Space direction="vertical" size="middle" style={{ width: '100%' }}>
            <Card title={execution.id} extra={<Button icon={<DownloadOutlined />} onClick={download}>Export JSON</Button>}>
              <Space wrap><Tag color={statusColor(execution.status)}>{execution.status}</Tag><Tag>{execution.trigger_type}</Tag>
                <Text>Cost: ${(execution.total_cost_usd || 0).toFixed(4)}</Text>
                <Text>Tokens: {execution.total_input_tokens} in / {execution.total_output_tokens} out</Text></Space>
              <div><Text type="secondary">Started: {execution.started_at ? formatTime(execution.started_at) : 'Pending'} · Finished: {formatTime(execution.completed_at)}
                {execution.started_at && ` · Duration: ${duration(execution.started_at, execution.completed_at)}`}</Text></div>
              {execution.notification_error && <Alert style={{ marginTop: 12 }} type="warning" showIcon
                message={runText.deliveryWarning} description={execution.notification_error} />}
              {execution.error_message && <Alert style={{ marginTop: 12 }} type="error" showIcon message="Run failed" description={<pre style={preStyle}>{execution.error_message}</pre>} />}
              <details style={{ marginTop: 12 }}><summary>Run input</summary><pre style={preStyle}>{execution.trigger_payload || '{}'}</pre></details>
            </Card>
            <Input.Search placeholder="Search step output and runtime events" value={search} onChange={event => setSearch(event.target.value)} allowClear />
            {!steps.length && <Alert type={execution.status === 'FAILED' ? 'warning' : 'info'} showIcon
              message={active(execution.status) ? 'Waiting for the first step' : 'No step logs were recorded'}
              description={execution.status === 'FAILED' ? 'This run failed before a step started, or predates step logging. See the run error above.' : undefined} />}
            {/* Only failed or still-running steps open by default; finished steps stay one line. */}
            <Collapse key={execution.id} defaultActiveKey={steps.filter(step => step.status === 'FAILED' || active(step.status)).map(step => step.id)} items={steps.filter(step => JSON.stringify(step).toLowerCase().includes(search.toLowerCase())).map(step => ({
              key: step.id,
              label: <Space wrap><Tag color={statusColor(step.status)}>{step.task_status || step.status}</Tag><strong>{step.step_key}</strong><Text type="secondary">{step.agent_id}</Text>
                {step.started_at && <Text type="secondary">{duration(step.started_at, step.completed_at)}</Text>}
                {step.cost_usd > 0 && <Text type="secondary">${step.cost_usd.toFixed(4)}</Text>}</Space>,
              children: <Space direction="vertical" style={{ width: '100%' }}>
                <Text type="secondary">Started: {formatTime(step.started_at)} · Finished: {formatTime(step.completed_at)}</Text>
                {step.error && <Alert type="error" showIcon message="Step failed" description={<pre style={preStyle}>{step.error}</pre>} />}
                <div><Text strong>Output</Text><pre style={preStyle}>{step.output_data || (active(step.status) ? 'Running…' : 'No output')}</pre></div>
                <details><summary>Step input</summary><pre style={preStyle}>{step.input_data}</pre></details>
                <details open={step.status === 'FAILED'}><summary>Runtime events ({step.events?.length || 0})</summary>
                  <StepEventTimeline events={step.events || []} /></details>
              </Space>
            }))} />
          </Space>}
        </Col>
      </Row>}
    </Space>
  </div>;
};

export default WorkflowLogsPage;
