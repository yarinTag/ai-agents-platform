import type { WorkflowHubText } from '../i18n/workflowHub';
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
>, access: { canManage: boolean; canOperate: boolean; isOrgAdmin: boolean }, departments: Department[], text: WorkflowHubText) => {
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
      title: text.name,
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
      title: text.department,
      dataIndex: 'department_id',
      key: 'department_id',
      render: (dept: string) =>
        dept ? (
          <Tooltip title={dept}>
            <Tag color="cyan">{departmentNames.get(dept)?.trim() || dept}</Tag>
          </Tooltip>
        ) : (
          <Tag color="default">{text.global}</Tag>
        ),
    }] : []),
    {
      title: text.triggers,
      key: 'triggers',
      render: (_: any, record: PlatformWorkflow) => (
        <Space direction="vertical" size={2}>
          {record.cron_expression && (
            <Tooltip title={`${text.cron}: ${record.cron_expression}`}>
              <Tag icon={<ClockCircleOutlined />} color="purple">
                {record.cron_expression}
              </Tag>
            </Tooltip>
          )}
          {record.webhook_enabled && record.webhook_token && (
            <Tooltip title={text.webhookHelp}>
              <Tag
                icon={<ThunderboltOutlined />}
                color="blue"
                style={{ cursor: 'pointer' }}
                onClick={() => copyToClipboard(record.webhook_token || '', text.webhookToken)}
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
            <Tag color="default">{text.manual}</Tag>
          )}
        </Space>
      ),
    },
    {
      title: text.steps,
      key: 'steps',
      render: (_: any, record: PlatformWorkflow) => {
        const steps = getParsedWorkflowSteps(record);
        return (
          <Tooltip title={`${steps.length} ${text.stages}`}>
            <Tag icon={<BranchesOutlined />} color="geekblue">
              {steps.length} {text.steps}
            </Tag>
          </Tooltip>
        );
      },
    },
    {
      title: text.status,
      dataIndex: 'is_active',
      key: 'is_active',
      render: (active: boolean) =>
        active ? (
          <Badge status="success" text={<span style={{ color: '#52c41a' }}>{text.active}</span>} />
        ) : (
          <Badge status="default" text={<span style={{ color: '#8b949e' }}>{text.inactive}</span>} />
        ),
    },
    {
      title: text.actions,
      key: 'actions',
      width: 150,
      render: (_: any, record: PlatformWorkflow) => (
        <Space size={6}>
          <Tooltip title={text.execute}>
            <Button
              type="primary"
              size="small"
              disabled={!access.canOperate} icon={<PlayCircleOutlined />}
              onClick={() => openRunModal(record)}
              style={{ background: '#238636', borderColor: '#238636' }}
            >
              {text.run}
            </Button>
          </Tooltip>
          <RowActionMenu label={`${text.actionsFor} ${record.name}`} items={[
            { key: 'playground', label: text.playground, disabled: !access.canOperate, onClick: () => openRunModal(record, true) },
            { key: 'edit', label: text.edit, icon: <EditOutlined />, disabled: !access.canManage, onClick: () => {
              setEditingWorkflow(record); setCreateModalOpen(true);
            } },
            { key: 'history', label: text.history, icon: <HistoryOutlined />, onClick: () => setHistoryWorkflow(record) },
            { key: 'settings', label: settingsText.settingsAction, icon: <SettingOutlined />, onClick: () => setSettingsWorkflow(record) },
            { key: 'logs', label: <Link to={`/workflows/${record.id}/logs`}>{text.logs}</Link>, icon: <EyeOutlined /> },
            { key: 'canvas', label: text.canvasAction, icon: <ApartmentOutlined />, onClick: () => {
              setSelectedWorkflow(record); setCanvasModalOpen(true);
            } },
            { key: 'definition', label: text.definitionAction, icon: <CodeOutlined />, onClick: () => {
              setSelectedWorkflow(record); setViewDefModalOpen(true);
            } },
            { type: 'divider' },
            { key: 'delete', label: text.delete, icon: <DeleteOutlined />, danger: true, disabled: !access.canManage,
              onClick: () => Modal.confirm({
                title: text.deletePrompt,
                content: text.deleteHelp,
                okText: text.deleteConfirm, cancelText: text.cancel, okButtonProps: { danger: true },
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
