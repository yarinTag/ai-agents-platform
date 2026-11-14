import { PrAuditEvidence } from '../components/workflows/PrEvidence';
import { useWorkflowRunText } from '../i18n/workflowRun';
import { formatCost } from '../services/workflowCosts';
import React, { useEffect, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { Alert, Button, Card, Col, Collapse, Empty, Input, Row, Segmented, Space, Spin, Tag, Typography } from 'antd';
import {
  ReloadOutlined,
  DownloadOutlined,
  ArrowLeftOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  SyncOutlined,
  ClockCircleOutlined,
  CodeOutlined,
  RobotOutlined,
} from '@ant-design/icons';
import axios from 'axios';
import { getWorkflow, getWorkflowExecutions, getWorkflowExecution } from '../services/api';
import { PlatformWorkflow, WorkflowExecution } from '../types/mcp';
import { DagApprovalsInbox } from '../components/workflows/DagApprovalsInbox';
import { useDagApprovalsText } from '../i18n/dagApprovals';
import { StepEventTimeline } from '../components/workflows/StepEventTimeline';

const { Text, Title } = Typography;
const active = (status: string) => ['QUEUED', 'RUNNING'].includes(status);
const statusColor = (status: string) =>
  status === 'FAILED' ? 'error' : status === 'COMPLETED' ? 'success' : status === 'QUEUED' ? 'warning' : 'processing';
const statusIcon = (status: string) => {
  if (status === 'COMPLETED') return <CheckCircleOutlined />;
  if (status === 'FAILED') return <CloseCircleOutlined />;
  if (status === 'RUNNING') return <SyncOutlined spin />;
  if (status === 'QUEUED') return <ClockCircleOutlined />;
  return undefined;
};
const triggerColor = (trigger: string) => {
  if (trigger === 'PLAYGROUND') return 'magenta';
  if (trigger === 'MANUAL') return 'blue';
  if (trigger === 'WEBHOOK') return 'cyan';
  if (trigger === 'CRON') return 'purple';
  return 'default';
};
const preStyle: React.CSSProperties = {
  whiteSpace: 'pre-wrap',
  overflowWrap: 'anywhere',
  maxHeight: 420,
  overflow: 'auto',
  fontSize: 12,
  fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
  background: '#0d1117',
  border: '1px solid #21262d',
  borderRadius: 6,
  padding: '10px 12px',
  margin: '6px 0 0',
  color: '#e6edf3',
};
const clamp: React.CSSProperties = {
  display: '-webkit-box',
  WebkitLineClamp: 2,
  WebkitBoxOrient: 'vertical',
  overflow: 'hidden',
  fontSize: 11,
  lineHeight: '15px',
  color: '#ff7875',
  background: 'rgba(248, 81, 73, 0.08)',
  border: '1px solid rgba(248, 81, 73, 0.25)',
  borderRadius: 6,
  padding: '4px 8px',
  marginTop: 2,
};
const metaBoxStyle: React.CSSProperties = {
  background: '#0d1117',
  border: '1px solid #21262d',
  borderRadius: 6,
  padding: '8px 12px',
};
const detailsStyle: React.CSSProperties = {
  background: '#0d1117',
  border: '1px solid #21262d',
  borderRadius: 6,
  padding: '8px 12px',
};
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
  const approvalText = useDagApprovalsText();
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
  const [approvalRunId, setApprovalRunId] = useState<string | null>(null);

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
    return () => { disposed = true; };
  }, [workflowId, selectedId, refresh]);

  const download = () => {
    if (!execution) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify(execution, null, 2)], { type: 'application/json' }));
    const anchor = document.createElement('a'); anchor.href = url; anchor.download = `${execution.id}.json`; anchor.click();
    URL.revokeObjectURL(url);
  };
  const visibleRuns = runs.filter(run => mode === 'ALL' || (mode === 'PLAYGROUND' ? run.trigger_type === 'PLAYGROUND' : run.trigger_type !== 'PLAYGROUND'));
  const steps = execution?.step_runs || [];

  return (
    <div style={{ padding: 24, minHeight: '100vh', background: '#0a0d12' }}>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12 }}>
          <div>
            <Link to="/workflows" style={{ display: 'inline-flex', alignItems: 'center', gap: 6, color: '#8b949e', fontSize: 13, marginBottom: 6 }}>
              <ArrowLeftOutlined /> Back to Workflows
            </Link>
            <Title level={3} style={{ margin: 0, color: '#f0f6fc', display: 'flex', alignItems: 'center', gap: 10 }}>
              <CodeOutlined style={{ color: '#10b981' }} />
              <span>{workflow?.name || 'Workflow'}</span>
              <Text type="secondary" style={{ fontSize: 16, fontWeight: 400 }}>· Execution Logs</Text>
            </Title>
            <Text type="secondary" style={{ fontSize: 13 }}>
              Run history, step output, and runtime diagnostics. Auto-refreshes every 5 seconds.
            </Text>
          </div>
          <Button icon={<ReloadOutlined spin={loading} />} onClick={() => setRefresh(value => value + 1)}>
            Refresh
          </Button>
        </div>

        {execution && <DagApprovalsInbox open={execution.id === approvalRunId} execution={{
          id: execution.id, department_id: execution.department_id,
        }} onClose={() => setApprovalRunId(null)} />}

        {error && <Alert type="error" showIcon message="Unable to load logs" description={error} />}

        {loading && !workflow ? (
          <div style={{ padding: 64, textAlign: 'center' }}><Spin size="large" /></div>
        ) : (
          <Row gutter={[20, 20]}>
            <Col xs={24} lg={8}>
              <Card
                title={
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span>Runs History</span>
                    <Tag style={{ marginInlineEnd: 0 }}>{visibleRuns.length} / {runs.length}</Tag>
                  </div>
                }
                styles={{ body: { padding: 14 } }}
                style={{ background: '#161b22', borderColor: '#30363d' }}
              >
                <Segmented
                  block
                  value={mode}
                  onChange={value => setMode(String(value))}
                  style={{ marginBottom: 14, background: '#0d1117', padding: 3 }}
                  options={[
                    { value: 'ALL', label: 'All Runs' },
                    { value: 'LIVE', label: 'Live' },
                    { value: 'PLAYGROUND', label: 'Playground' },
                  ]}
                />

                {!visibleRuns.length && (
                  <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No runs match the current filter." />
                )}

                <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxHeight: '72vh', overflowY: 'auto', paddingRight: 2 }}>
                  {visibleRuns.map(run => {
                    const isSelected = execution?.id === run.id;
                    const runDuration = duration(run.started_at, run.completed_at);
                    return (
                      <div
                        key={run.id}
                        role="button"
                        tabIndex={0}
                        onClick={() => setParams({ execution: run.id })}
                        onKeyDown={event => {
                          if (event.key === 'Enter' || event.key === ' ') {
                            event.preventDefault();
                            setParams({ execution: run.id });
                          }
                        }}
                        style={{
                          display: 'flex',
                          flexDirection: 'column',
                          gap: 6,
                          padding: '11px 13px',
                          borderRadius: 8,
                          cursor: 'pointer',
                          transition: 'all 0.15s ease',
                          background: isSelected ? 'rgba(16, 185, 129, 0.1)' : '#0d1117',
                          border: isSelected ? '1px solid #10b981' : '1px solid #21262d',
                          boxShadow: isSelected ? 'inset 3px 0 0 #10b981' : 'none',
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                          <Space size={4} wrap>
                            <Tag icon={statusIcon(run.status)} color={statusColor(run.status)} style={{ marginInlineEnd: 0, fontWeight: 600 }}>
                              {run.status}
                            </Tag>
                            <Tag color={triggerColor(run.trigger_type)} style={{ marginInlineEnd: 0 }}>
                              {run.trigger_type}
                            </Tag>
                            {run.is_deduplicated && (
                              <Tag color="purple" style={{ marginInlineEnd: 0, fontSize: 10 }}>⚡ CACHED</Tag>
                            )}
                          </Space>
                          <Space size={6}>
                            {runDuration && (
                              <Text type="secondary" style={{ fontSize: 11, fontFamily: 'monospace' }}>
                                {runDuration}
                              </Text>
                            )}
                            {(
                              <Text style={{ fontSize: 11, fontFamily: 'monospace', color: '#58a6ff' }}>
                                {formatCost(run.cost_summary, run.total_cost_usd)}
                              </Text>
                            )}
                          </Space>
                        </div>

                        <div
                          style={{
                            fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
                            fontSize: 12,
                            fontWeight: 600,
                            color: isSelected ? '#34d399' : '#c9d1d9',
                            wordBreak: 'break-all',
                          }}
                        >
                          {run.id}
                        </div>

                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 11, color: '#8b949e' }}>
                          <span>{formatTime(run.created_at)}</span>
                          {(run.total_input_tokens + run.total_output_tokens) > 0 && (
                            <span>{(run.total_input_tokens + run.total_output_tokens).toLocaleString()} tok</span>
                          )}
                        </div>

                        {run.error_message && <div style={clamp}>{run.error_message}</div>}
                      </div>
                    );
                  })}
                </div>

                {runs.length === 200 && (
                  <Text type="secondary" style={{ display: 'block', marginTop: 10, fontSize: 11, textAlign: 'center' }}>
                    Showing the latest 200 runs.
                  </Text>
                )}
              </Card>
            </Col>

            <Col xs={24} lg={16}>
              {!execution ? (
                <Card style={{ background: '#161b22', borderColor: '#30363d', textAlign: 'center', padding: 32 }}>
                  <Empty description="Select a run from the left panel to inspect its logs" />
                </Card>
              ) : (
                <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                  <Card
                    style={{ background: '#161b22', borderColor: '#30363d' }}
                    title={
                      <Space wrap size={8}>
                        <Tag icon={statusIcon(execution.status)} color={statusColor(execution.status)} style={{ marginInlineEnd: 0, fontWeight: 600 }}>
                          {execution.status}
                        </Tag>
                        <Tag color={triggerColor(execution.trigger_type)} style={{ marginInlineEnd: 0 }}>
                          {execution.trigger_type}
                        </Tag>
                        <span style={{ fontFamily: 'monospace', fontSize: 14, color: '#f0f6fc' }}>{execution.id}</span>
                      </Space>
                    }
                    extra={<Space wrap size={6}>
                      {execution.trigger_type !== 'PLAYGROUND' && <Button size="small" onClick={() => setApprovalRunId(execution.id)}>
                        {approvalText.runApprovals}
                      </Button>}
                      <Button size="small" icon={<DownloadOutlined />} onClick={download}>Export JSON</Button>
                    </Space>}
                  >
                    <Row gutter={[12, 12]}>
                      <Col xs={12} sm={6}>
                        <div style={metaBoxStyle}>
                          <div style={{ fontSize: 11, color: '#8b949e' }}>STARTED</div>
                          <div style={{ fontSize: 12, color: '#e6edf3', fontWeight: 500, marginTop: 2 }}>
                            {execution.started_at ? formatTime(execution.started_at) : 'Pending'}
                          </div>
                        </div>
                      </Col>
                      <Col xs={12} sm={6}>
                        <div style={metaBoxStyle}>
                          <div style={{ fontSize: 11, color: '#8b949e' }}>FINISHED</div>
                          <div style={{ fontSize: 12, color: '#e6edf3', fontWeight: 500, marginTop: 2 }}>
                            {formatTime(execution.completed_at)}
                          </div>
                        </div>
                      </Col>
                      <Col xs={12} sm={6}>
                        <div style={metaBoxStyle}>
                          <div style={{ fontSize: 11, color: '#8b949e' }}>DURATION & COST</div>
                          <div style={{ fontSize: 12, color: '#58a6ff', fontWeight: 600, marginTop: 2, fontFamily: 'monospace' }}>
                            {duration(execution.started_at, execution.completed_at) || '—'} · {formatCost(execution.cost_summary, execution.total_cost_usd)}
                          </div>
                        </div>
                      </Col>
                      <Col xs={12} sm={6}>
                        <div style={metaBoxStyle}>
                          <div style={{ fontSize: 11, color: '#8b949e' }}>TOKENS (IN / OUT)</div>
                          <div style={{ fontSize: 12, color: '#e6edf3', fontWeight: 500, marginTop: 2, fontFamily: 'monospace' }}>
                            {(execution.total_input_tokens || 0).toLocaleString()} / {(execution.total_output_tokens || 0).toLocaleString()}
                          </div>
                        </div>
                      </Col>
                    </Row>

                    {execution.notification_error && (
                      <Alert
                        style={{ marginTop: 12 }}
                        type="warning"
                        showIcon
                        message={runText.deliveryWarning}
                        description={execution.notification_error}
                      />
                    )}
                    {execution.error_message && (
                      <Alert
                        style={{ marginTop: 12 }}
                        type="error"
                        showIcon
                        message="Run failed"
                        description={<pre style={preStyle}>{execution.error_message}</pre>}
                      />
                    )}
                    <details style={{ ...detailsStyle, marginTop: 12 }}>
                      <summary style={{ cursor: 'pointer', fontSize: 12, color: '#8b949e', fontWeight: 600 }}>
                        Run Input Payload
                      </summary>
                      <pre style={preStyle}>{execution.trigger_payload || '{}'}</pre>
                    </details>
                  </Card>

                  <Input.Search
                    placeholder="Search step output, input, and runtime events…"
                    value={search}
                    onChange={event => setSearch(event.target.value)}
                    allowClear
                  />

                  {!steps.length && (
                    <Alert
                      type={execution.status === 'FAILED' ? 'warning' : 'info'}
                      showIcon
                      message={active(execution.status) ? 'Waiting for the first step' : 'No step logs were recorded'}
                      description={
                        execution.status === 'FAILED'
                          ? 'This run failed before a step started, or predates step logging. See the run error above.'
                          : undefined
                      }
                    />
                  )}

                  {/* Only failed or still-running steps open by default; finished steps stay one line. */}
                  <Collapse
                    key={execution.id}
                    style={{ background: '#161b22', borderColor: '#30363d' }}
                    defaultActiveKey={steps.filter(step => step.status === 'FAILED' || active(step.status)).map(step => step.id)}
                    items={steps
                      .filter(step => JSON.stringify(step).toLowerCase().includes(search.toLowerCase()))
                      .map(step => ({
                        key: step.id,
                        label: (
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8, width: '100%' }}>
                            <Space wrap size={8}>
                              <Tag icon={statusIcon(step.status)} color={statusColor(step.status)} style={{ marginInlineEnd: 0, fontWeight: 600 }}>
                                {step.task_status || step.status}
                              </Tag>
                              <strong style={{ color: '#f0f6fc', fontSize: 13 }}>{step.step_key}</strong>
                              {(step.events || []).some(event => event.type === 'reasoning_summary' && event.status === 'available') && (
                                <Tag color="geekblue">Reasoning ({(step.events || []).filter(event => event.type === 'reasoning_summary' && event.status === 'available').length})</Tag>
                              )}
                              <Tag icon={<RobotOutlined />} style={{ marginInlineEnd: 0, fontFamily: 'monospace', fontSize: 11 }}>
                                {step.agent_id}
                              </Tag>
                            </Space>
                            <Space size={10}>
                              {step.started_at && (
                                <Text type="secondary" style={{ fontSize: 12, fontFamily: 'monospace' }}>
                                  {duration(step.started_at, step.completed_at)}
                                </Text>
                              )}
                              {(
                                <Text style={{ fontSize: 12, fontFamily: 'monospace', color: '#58a6ff' }}>
                                  {formatCost(step.cost_summary, step.cost_usd)}
                                </Text>
                              )}
                            </Space>
                          </div>
                        ),
                        children: (
                          <Space direction="vertical" size={12} style={{ width: '100%' }}>
                            <Text type="secondary" style={{ fontSize: 12 }}>
                              Started: {formatTime(step.started_at)} · Finished: {formatTime(step.completed_at)}
                            </Text>
                            <PrAuditEvidence entries={step.pr_evidence || []} />
                            {step.session_cost_summary && <Text style={{ fontSize: 12 }}>Session total: {formatCost(step.session_cost_summary)}</Text>}
                            {step.error && (
                              <Alert
                                type="error"
                                showIcon
                                message="Step failed"
                                description={<pre style={preStyle}>{step.error}</pre>}
                              />
                            )}
                            <div>
                              <Text strong style={{ fontSize: 12, color: '#8b949e', textTransform: 'uppercase', letterSpacing: 0.4 }}>
                                Step Output
                              </Text>
                              <pre style={preStyle}>
                                {step.output_data || (active(step.status) ? 'Running…' : 'No output')}
                              </pre>
                            </div>
                            <details style={detailsStyle}>
                              <summary style={{ cursor: 'pointer', fontSize: 12, color: '#8b949e', fontWeight: 600 }}>
                                Step Input
                              </summary>
                              <pre style={preStyle}>{step.input_data || '—'}</pre>
                            </details>
                            <details open={step.status === 'FAILED' || (step.events || []).some(event => event.type === 'reasoning_summary')} style={detailsStyle}>
                              <summary style={{ cursor: 'pointer', fontSize: 12, color: '#8b949e', fontWeight: 600 }}>
                                Runtime Events ({step.events?.length || 0})
                              </summary>
                              <div style={{ marginTop: 8 }}>
                                <StepEventTimeline events={step.events || []} />
                              </div>
                            </details>
                          </Space>
                        ),
                      }))}
                  />
                </Space>
              )}
            </Col>
          </Row>
        )}
      </Space>
    </div>
  );
};

export default WorkflowLogsPage;
