import { Button, Tag, Space } from 'antd';
import { EyeOutlined, CheckCircleOutlined, CloseCircleOutlined, ClockCircleOutlined, SyncOutlined } from '@ant-design/icons';
import { WorkflowExecution } from '../types/mcp';

import type { useWorkflowsPage } from './useWorkflowsPage';

export const createWorkflowExecutionColumns = (model: Pick<
  ReturnType<typeof useWorkflowsPage>,
  | 'workflows'
  | 'setDetailDrawerOpen'
  | 'setSelectedExecution'
>) => {
  const {
    workflows,
    setDetailDrawerOpen,
    setSelectedExecution,
  } = model;
  const executionColumns = [
    {
      title: 'Execution ID',
      dataIndex: 'id',
      key: 'id',
      render: (id: string, record: WorkflowExecution) => (
        <Space direction="vertical" size={2}>
          <span style={{ fontFamily: 'monospace', color: '#58a6ff', fontWeight: 600 }}>
            {id}
          </span>
          {record.is_deduplicated && (
            <Tag color="purple" style={{ fontSize: 10, lineHeight: '14px' }}>
              ⚡ DEDUPLICATED / CACHED
            </Tag>
          )}
        </Space>
      ),
    },
    {
      title: 'Workflow',
      dataIndex: 'workflow_id',
      key: 'workflow_id',
      render: (wfId: string) => {
        const wf = workflows.find((w) => w.id === wfId);
        return (
          <div>
            <strong style={{ color: '#f0f6fc' }}>{wf?.name || wfId}</strong>
            <div style={{ color: '#8b949e', fontSize: 11 }}>{wfId}</div>
          </div>
        );
      },
    },
    {
      title: 'Trigger',
      dataIndex: 'trigger_type',
      key: 'trigger_type',
      render: (trigger: string) => {
        let color = 'default';
        if (trigger === 'PLAYGROUND') color = 'magenta';
        if (trigger === 'MANUAL') color = 'blue';
        if (trigger === 'WEBHOOK') color = 'cyan';
        if (trigger === 'CRON') color = 'purple';
        return <Tag color={color}>{trigger}</Tag>;
      },
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => {
        if (status === 'COMPLETED') {
          return <Tag icon={<CheckCircleOutlined />} color="success">COMPLETED</Tag>;
        }
        if (status === 'RUNNING') {
          return <Tag icon={<SyncOutlined spin />} color="processing">RUNNING</Tag>;
        }
        if (status === 'QUEUED') {
          return <Tag icon={<ClockCircleOutlined />} color="warning">QUEUED</Tag>;
        }
        if (status === 'FAILED') {
          return <Tag icon={<CloseCircleOutlined />} color="error">FAILED</Tag>;
        }
        return <Tag color="default">{status}</Tag>;
      },
    },
    {
      title: 'Tokens & Cost',
      key: 'tokens',
      render: (_: any, record: WorkflowExecution) => (
        <div>
          <span style={{ color: '#c9d1d9', fontSize: 12 }}>
            {(record.total_input_tokens + record.total_output_tokens).toLocaleString()} tokens
          </span>
          <div style={{ color: '#58a6ff', fontSize: 11 }}>
            ${record.total_cost_usd?.toFixed(4) || '0.0000'}
          </div>
        </div>
      ),
    },
    {
      title: 'Created At',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (d: string) => (
        <span style={{ color: '#8b949e', fontSize: 12 }}>
          {d ? new Date(d).toLocaleString() : '-'}
        </span>
      ),
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_: any, record: WorkflowExecution) => (
        <Button
          size="small"
          icon={<EyeOutlined />}
          onClick={() => {
            setSelectedExecution(record);
            setDetailDrawerOpen(true);
          }}
        >
          Inspect
        </Button>
      ),
    },
  ];

  return executionColumns;
};
