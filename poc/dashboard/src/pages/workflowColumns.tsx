import { RowActionMenu } from './RowActionMenu';
import { Link } from 'react-router-dom';
import { Button, Tag, Space, Tooltip, Modal, Badge } from 'antd';
import { ApartmentOutlined, PlayCircleOutlined, DeleteOutlined, CodeOutlined, EyeOutlined, ThunderboltOutlined, ClockCircleOutlined, SlackOutlined, SendOutlined, BranchesOutlined, EditOutlined, HistoryOutlined, SettingOutlined } from '@ant-design/icons';
import { PlatformWorkflow } from '../types/mcp';
import type { Department } from '../types/auth';

import type { useWorkflowsPage } from './useWorkflowsPage';

export const createWorkflowColumns = (model: Pick<
  ReturnType<typeof useWorkflowsPage>,
  | 'connectors'
  | 'setEditingWorkflow'
  | 'setHistoryWorkflow'
  | 'setSettingsWorkflow'
  | 'settingsText'
  | 'setCreateModalOpen'
  | 'setCanvasModalOpen'
  | 'setSelectedWorkflow'
  | 'setViewDefModalOpen'
  | 'handleDelete'
  | 'openRunModal'
  | 'copyToClipboard'
  | 'getParsedWorkflowSteps'
>, access: { canManage: boolean; canOperate: boolean; isOrgAdmin: boolean }, departments: Department[]) => {
  const {
    setEditingWorkflow,
    setHistoryWorkflow,
    setSettingsWorkflow,
    settingsText,
    setCreateModalOpen,
    setCanvasModalOpen,
    setSelectedWorkflow,
    setViewDefModalOpen,
    handleDelete,
    openRunModal,
    copyToClipboard,
    getParsedWorkflowSteps,
  } = model;
  const departmentNames = new Map(departments.map(department => [
    department.id || department.department_id, department.name,
  ]));
  const channelLabel = (binding: NonNullable<PlatformWorkflow['channel_binding']>) => {
    const candidates = model.connectors.filter(connector =>
      connector.provider === binding.provider &&
      (!binding.connector_id || connector.id === binding.connector_id));
    // Legacy bindings without a connector ID must not borrow another connector's label.
    if (candidates.length !== 1) return binding.channel_id;
    const label: unknown = candidates[0].configuration?.channel_labels?.[binding.channel_id];
    return typeof label === 'string' && label.trim() ? label.trim() : binding.channel_id;
  };
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
    ...(access.isOrgAdmin ? [{
      title: 'Department',
      dataIndex: 'department_id',
      key: 'department_id',
      render: (dept: string) =>
        dept ? (
          <Tooltip title={dept}>
            <Tag color="cyan">{departmentNames.get(dept)?.trim() || dept}</Tag>
          </Tooltip>
        ) : (
          <Tag color="default">Global</Tag>
        ),
    }] : []),
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
            <Tooltip title={record.channel_binding.channel_id}>
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
                {channelLabel(record.channel_binding)}
              </Tag>
            </Tooltip>
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
      width: 150,
      render: (_: any, record: PlatformWorkflow) => (
        <Space size={6}>
          <Tooltip title="Execute Workflow">
            <Button
              type="primary"
              size="small"
              disabled={!access.canOperate} icon={<PlayCircleOutlined />}
              onClick={() => openRunModal(record)}
              style={{ background: '#238636', borderColor: '#238636' }}
            >
              Run
            </Button>
          </Tooltip>
          <RowActionMenu label={`Actions for workflow ${record.name}`} items={[
            { key: 'playground', label: 'Playground', disabled: !access.canOperate, onClick: () => openRunModal(record, true) },
            { key: 'edit', label: 'Edit', icon: <EditOutlined />, disabled: !access.canManage, onClick: () => {
              setEditingWorkflow(record); setCreateModalOpen(true);
            } },
            { key: 'history', label: 'History', icon: <HistoryOutlined />, onClick: () => setHistoryWorkflow(record) },
            { key: 'settings', label: settingsText.settingsAction, icon: <SettingOutlined />, onClick: () => setSettingsWorkflow(record) },
            { key: 'logs', label: <Link to={`/workflows/${record.id}/logs`}>Logs</Link>, icon: <EyeOutlined /> },
            { key: 'canvas', label: 'Canvas', icon: <ApartmentOutlined />, onClick: () => {
              setSelectedWorkflow(record); setCanvasModalOpen(true);
            } },
            { key: 'definition', label: 'YAML / JSON Definition', icon: <CodeOutlined />, onClick: () => {
              setSelectedWorkflow(record); setViewDefModalOpen(true);
            } },
            { type: 'divider' },
            { key: 'delete', label: 'Delete', icon: <DeleteOutlined />, danger: true, disabled: !access.canManage,
              onClick: () => Modal.confirm({
                title: 'Delete this workflow?',
                content: 'This will permanently delete this playbook and its configuration.',
                okText: 'Yes, Delete', cancelText: 'Cancel', okButtonProps: { danger: true },
                onOk: () => handleDelete(record.id),
              }) },
          ]} />
        </Space>
      ),
    },
  ];

  // Executions Table Columns
  return workflowColumns;
};
