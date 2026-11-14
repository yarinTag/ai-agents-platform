import { PrAuditEvidence } from '../components/workflows/PrEvidence';
import { WorkflowApprovalPanel } from '../components/workflows/WorkflowApprovalPanel';
import { useWorkflowRunText } from '../i18n/workflowRun';
import { formatCost } from '../services/workflowCosts';
import { Link } from 'react-router-dom';
import { Tag, Space, Card, Input, Drawer, Alert } from 'antd';
import { EyeOutlined } from '@ant-design/icons';

import type { useWorkflowsPage } from './useWorkflowsPage';

export const WorkflowExecutionDrawer = (model: Pick<
  ReturnType<typeof useWorkflowsPage>,
  | 'workflows'
  | 'detailDrawerOpen'
  | 'setDetailDrawerOpen'
  | 'selectedExecution'
>) => {
  const runText = useWorkflowRunText();
  const { workflows, detailDrawerOpen, setDetailDrawerOpen, selectedExecution } = model;
  return (<>
      {/* Execution Inspection Drawer */}
      <Drawer
        title={
          <span style={{ color: '#f0f6fc', display: 'flex', alignItems: 'center', gap: 8 }}>
            <EyeOutlined style={{ color: '#58a6ff' }} />
            Execution Inspection: {selectedExecution?.id}
            {selectedExecution && <Link to={`/workflows/${selectedExecution.workflow_id}/logs?execution=${selectedExecution.id}`}>Full logs</Link>}
          </span>
        }
        placement="right"
        styles={{ wrapper: { width: 500 } }}
        open={detailDrawerOpen}
        onClose={() => setDetailDrawerOpen(false)}
      >
        {selectedExecution && (
          <Space direction="vertical" size={16} style={{ width: '100%' }}>
            <Card size="small" style={{ background: '#161b22', borderColor: '#30363d' }}>
              <Space direction="vertical" size={4} style={{ width: '100%' }}>
                <span style={{ color: '#8b949e', fontSize: 12 }}>STATUS:</span>
                <div>
                  <Tag
                    color={
                      selectedExecution.status === 'COMPLETED'
                        ? 'success'
                        : selectedExecution.status === 'RUNNING'
                        ? 'processing'
                        : selectedExecution.status === 'QUEUED'
                        ? 'warning'
                        : 'error'
                    }
                  >
                    {selectedExecution.status}
                  </Tag>
                  {selectedExecution.is_deduplicated && (
                    <Tag color="purple">⚡ DEDUPLICATED</Tag>
                  )}
                </div>
              </Space>
            </Card>

            <Card size="small" style={{ background: '#161b22', borderColor: '#30363d' }}>
              <Space direction="vertical" size={4} style={{ width: '100%' }}>
                <span style={{ color: '#8b949e', fontSize: 12 }}>METRICS:</span>
                <div style={{ color: '#c9d1d9', fontSize: 13 }}>
                  • Input Tokens: {selectedExecution.total_input_tokens?.toLocaleString()}
                </div>
                <div style={{ color: '#c9d1d9', fontSize: 13 }}>
                  • Output Tokens: {selectedExecution.total_output_tokens?.toLocaleString()}
                </div>
                <div style={{ color: '#58a6ff', fontSize: 13, fontWeight: 600 }}>
                  • Total Cost: {formatCost(selectedExecution.cost_summary, selectedExecution.total_cost_usd)}
                </div>
              </Space>
            </Card>

            {selectedExecution.sandbox_path && (
              <Card size="small" style={{ background: '#161b22', borderColor: '#30363d' }}>
                <span style={{ color: '#8b949e', fontSize: 12 }}>SANDBOX DIRECTORY:</span>
                <div style={{ color: '#c9d1d9', fontFamily: 'monospace', fontSize: 11, marginTop: 4 }}>
                  {selectedExecution.sandbox_path}
                </div>
              </Card>
            )}

            {selectedExecution.notification_error && <Alert type="warning" showIcon
              message={runText.deliveryWarning} description={selectedExecution.notification_error} />}
            {selectedExecution.error_message && (
              <Card size="small" style={{ background: '#220808', borderColor: '#8b0000' }}>
                <span style={{ color: '#ff7875', fontSize: 12 }}>ERROR DETAILS:</span>
                <pre
                  style={{
                    color: '#ff7875',
                    fontSize: 11,
                    fontFamily: 'monospace',
                    whiteSpace: 'pre-wrap',
                    marginTop: 4,
                  }}
                >
                  {selectedExecution.error_message}
                </pre>
              </Card>
            )}

            {selectedExecution.trigger_type === 'PLAYGROUND' && <Tag color="magenta">PLAYGROUND · TOOLS DISABLED</Tag>}
            <WorkflowApprovalPanel key={selectedExecution.id} executionId={selectedExecution.id} />
            {selectedExecution.step_runs?.map(step => (
              <Card key={step.id} size="small" title={`${step.step_key} · ${step.status}`}>
                <PrAuditEvidence entries={step.pr_evidence || []} />
                <div>Cost: {formatCost(step.cost_summary, step.cost_usd)}</div>
                {step.session_cost_summary && <div>Session total: {formatCost(step.session_cost_summary)}</div>}
                <details><summary>Step input</summary><pre style={{ whiteSpace: 'pre-wrap' }}>{step.input_data}</pre></details>
                <pre style={{ whiteSpace: 'pre-wrap', maxHeight: 300, overflow: 'auto' }}>{step.output_data}</pre>
              </Card>
            ))}
            <Card size="small" style={{ background: '#161b22', borderColor: '#30363d' }}>
              <span style={{ color: '#8b949e', fontSize: 12 }}>INPUT PAYLOAD:</span>
              <pre
                style={{
                  background: '#0d1117',
                  color: '#7ee787',
                  padding: 8,
                  borderRadius: 4,
                  fontSize: 11,
                  fontFamily: 'monospace',
                  maxHeight: 200,
                  overflow: 'auto',
                  marginTop: 4,
                }}
              >
                {selectedExecution.trigger_payload || '(Empty payload)'}
              </pre>
            </Card>
          </Space>
        )}
      </Drawer>

  </>);
};
