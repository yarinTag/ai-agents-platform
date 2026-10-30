import { Link } from 'react-router-dom';
import { Table, Button, Tag, Space, Tooltip, Popconfirm, Badge } from 'antd';
import { ApartmentOutlined, PlayCircleOutlined, DeleteOutlined, CodeOutlined, EyeOutlined, ThunderboltOutlined, ClockCircleOutlined, SlackOutlined, SendOutlined, BranchesOutlined, EditOutlined, HistoryOutlined } from '@ant-design/icons';
import { PlatformWorkflow } from '../types/mcp';

import type { useWorkflowsPage } from './useWorkflowsPage';

export const createWorkflowColumns = (model: Pick<
  ReturnType<typeof useWorkflowsPage>,
  | 'workflows'
  | 'setEditingWorkflow'
  | 'setHistoryWorkflow'
  | 'setCreateModalOpen'
  | 'setCanvasModalOpen'
  | 'setSelectedWorkflow'
  | 'setViewDefModalOpen'
  | 'handleDelete'
  | 'openRunModal'
  | 'copyToClipboard'
  | 'getParsedWorkflowSteps'
>) => {
  const {
    workflows,
    setEditingWorkflow,
    setHistoryWorkflow,
    setCreateModalOpen,
    setCanvasModalOpen,
    setSelectedWorkflow,
    setViewDefModalOpen,
    handleDelete,
    openRunModal,
    copyToClipboard,
    getParsedWorkflowSteps,
  } = model;
  const workflowColumns = [
    {
      title: 'Workflow Name',
      key: 'name',
      render: (_: any, record: PlatformWorkflow) => (
        <div>
          <Space orientation="horizontal" size={6}>
            <ApartmentOutlined style={{ color: '#8b5cf6', fontSize: 16 }} />
            <strong style={{ color: '#f0f6fc', fontSize: 14 }}>{record.name}</strong>
          </Space>
          <div style={{ color: '#8b949e', fontSize: 12, marginTop: 2 }}>
            {record.description || record.id}
          </div>
        </div>
      ),
    },
    {
      title: 'Department',
      dataIndex: 'department_id',
      key: 'department_id',
      render: (dept: string) =>
        dept ? (
          <Tag color="cyan" style={{ fontFamily: 'monospace', fontSize: 11 }}>
            {dept}
          </Tag>
        ) : (
          <Tag color="default">Global</Tag>
        ),
    },
    {
      title: 'Triggers & Bindings',
      key: 'triggers',
      render: (_: any, record: PlatformWorkflow) => (
        <Space direction="vertical" size={2}>
          {record.cron_expression && (
            <Tooltip title={`Cron schedule: ${record.cron_expression}`}>
              <Tag icon={<ClockCircleOutlined />} color="purple">
                {record.cron_expression}
              </Tag>
            </Tooltip>
          )}
          {record.webhook_enabled && record.webhook_token && (
            <Tooltip title="Webhook enabled. Click to copy webhook token.">
              <Tag
                icon={<ThunderboltOutlined />}
                color="blue"
                style={{ cursor: 'pointer' }}
                onClick={() => copyToClipboard(record.webhook_token || '', 'Webhook Token')}
              >
                Webhook: {record.webhook_token.slice(0, 8)}...
              </Tag>
            </Tooltip>
          )}
          {record.channel_binding && (
            <Tag
              icon={
                record.channel_binding.provider === 'telegram' ? (
                  <SendOutlined />
                ) : (
                  <SlackOutlined />
                )
              }
              color={record.channel_binding.provider === 'telegram' ? 'blue' : 'green'}
            >
              {record.channel_binding.channel_id}
            </Tag>
          )}
          {!record.cron_expression && !record.webhook_enabled && !record.channel_binding && (
            <Tag color="default">Manual Trigger Only</Tag>
          )}
        </Space>
      ),
    },
    {
      title: 'Steps',
      key: 'steps',
      render: (_: any, record: PlatformWorkflow) => {
        const steps = getParsedWorkflowSteps(record);
        return (
          <Tooltip title={`${steps.length} DAG execution stages`}>
            <Tag icon={<BranchesOutlined />} color="geekblue">
              {steps.length} Steps
            </Tag>
          </Tooltip>
        );
      },
    },
    {
      title: 'Status',
      dataIndex: 'is_active',
      key: 'is_active',
      render: (active: boolean) =>
        active ? (
          <Badge status="success" text={<span style={{ color: '#52c41a' }}>Active</span>} />
        ) : (
          <Badge status="default" text={<span style={{ color: '#8b949e' }}>Inactive</span>} />
        ),
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_: any, record: PlatformWorkflow) => (
        <Space size={6} wrap>
          <Button size="small" icon={<EditOutlined />} onClick={() => {
            setEditingWorkflow(record); setCreateModalOpen(true);
          }}>Edit</Button>
          <Button size="small" icon={<HistoryOutlined />} onClick={() => setHistoryWorkflow(record)}>History</Button>
          <Tooltip title="Execute Workflow">
            <Button
              type="primary"
              size="small"
              icon={<PlayCircleOutlined />}
              onClick={() => openRunModal(record)}
              style={{ background: '#238636', borderColor: '#238636' }}
            >
              Run
            </Button>
          </Tooltip>
          <Button size="small" onClick={() => openRunModal(record, true)}>
            Playground
          </Button>
          <Link to={`/workflows/${record.id}/logs`}><Button size="small" icon={<EyeOutlined />}>Logs</Button></Link>
          <Tooltip title="View Visual DAG Execution Graph">
            <Button
              size="small"
              icon={<ApartmentOutlined />}
              onClick={() => {
                setSelectedWorkflow(record);
                setCanvasModalOpen(true);
              }}
            />
          </Tooltip>
          <Tooltip title="View Playbook Definition (YAML/JSON)">
            <Button
              size="small"
              icon={<CodeOutlined />}
              onClick={() => {
                setSelectedWorkflow(record);
                setViewDefModalOpen(true);
              }}
            />
          </Tooltip>
          <Popconfirm
            title="Delete this workflow?"
            description="This will permanently delete this playbook and its configuration."
            onConfirm={() => handleDelete(record.id)}
            okText="Yes, Delete"
            cancelText="Cancel"
            okButtonProps={{ danger: true }}
          >
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  // Executions Table Columns
  return workflowColumns;
};
