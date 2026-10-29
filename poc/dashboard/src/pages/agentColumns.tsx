import { Button, Tag, message, Tooltip, Space } from 'antd';
import { EditOutlined, DeleteOutlined, FolderOpenOutlined, GithubOutlined, LaptopOutlined, CrownOutlined, StarOutlined, MessageOutlined, ThunderboltOutlined } from '@ant-design/icons';
import { Agent } from '../types/agent';
import { deleteAgent } from '../services/api';

import type { useAgentsPage } from './useAgentsPage';

export const createAgentColumns = (model: Pick<
  ReturnType<typeof useAgentsPage>,
  | 'departments'
  | 'organization'
  | 'agents'
  | 'setVisible'
  | 'form'
  | 'setEditingKey'
  | 'setChatAgent'
  | 'setChatVisible'
  | 'fetchAgents'
>) => {
  const {
    departments,
    organization,
    agents,
    setVisible,
    form,
    setEditingKey,
    setChatAgent,
    setChatVisible,
    fetchAgents,
  } = model;
  const columns = [
    {
      title: 'Agent Name & Role',
      dataIndex: 'name',
      key: 'name',
      render: (name: string, record: Agent) => {
        const role = (record.role_type || 'WORKER').toUpperCase();
        const isWorkflowRunner =
          role === 'WORKFLOW_AUTOMATION' ||
          Boolean((record as any).is_workflow_agent) ||
          record.department === 'Workflow Automations';

        return (
          <div>
            <div style={{ fontWeight: 600, color: '#f3f4f6', display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
              {isWorkflowRunner ? (
                <ThunderboltOutlined style={{ color: '#c084fc' }} />
              ) : role === 'ROOT_ORCHESTRATOR' ? (
                <CrownOutlined style={{ color: '#fbbf24' }} />
              ) : role === 'MANAGER' ? (
                <StarOutlined style={{ color: '#f59e0b' }} />
              ) : (
                <LaptopOutlined style={{ color: '#38bdf8' }} />
              )}
              <span>{name}</span>
              <Tag
                color={
                  isWorkflowRunner
                    ? 'purple'
                    : role === 'ROOT_ORCHESTRATOR'
                    ? 'purple'
                    : role === 'MANAGER'
                    ? 'gold'
                    : role === 'SPECIALIST'
                    ? 'magenta'
                    : 'cyan'
                }
                style={{ fontSize: '10px', padding: '0 4px', margin: 0 }}
              >
                {isWorkflowRunner ? 'WORKFLOW RUNNER' : role}
              </Tag>
              {isWorkflowRunner && (
                <Tag
                  style={{
                    fontSize: '9px',
                    padding: '0 4px',
                    margin: 0,
                    background: '#1e1b4b',
                    color: '#c084fc',
                    border: '1px solid #4338ca',
                  }}
                >
                  Detached from Office Canvas
                </Tag>
              )}
            </div>
            <div style={{ fontSize: '11px', color: '#9ca3af' }}>{record.description || 'General Purpose Agent'}</div>
          </div>
        );
      },
    },
    {
      title: 'Supervisor (Parent) / Pipeline',
      dataIndex: 'parent_id',
      key: 'parent_id',
      render: (parentId: string | undefined, record: Agent) => {
        const isWorkflowRunner =
          record.role_type === 'WORKFLOW_AUTOMATION' ||
          Boolean((record as any).is_workflow_agent) ||
          record.department === 'Workflow Automations';

        if (isWorkflowRunner) {
          return (
            <Tag color="purple" style={{ fontSize: '11px' }}>
              ⚡ Workflow: {record.workflow_id || 'Pipeline'}
            </Tag>
          );
        }
        if (!parentId) return <span style={{ color: '#64748b', fontSize: '12px' }}>— (Root / Direct)</span>;
        const parentAgent = agents.find((a) => a.id === parentId);
        return (
          <Tag color="gold" style={{ fontSize: '11px' }}>
            ⭐ {parentAgent ? parentAgent.name : parentId}
          </Tag>
        );
      },
    },
    {
      title: 'Department',
      dataIndex: 'department',
      key: 'department',
      render: (dept?: string, record?: Agent) => {
        const linkedDept = departments.find((d) => d.id === record?.department_id);
        const d = linkedDept ? linkedDept.name : dept || 'Engineering';
        const colorMap: Record<string, string> = {
          Architecture: 'purple',
          'QA & Testing': 'cyan',
          HQ: 'gold',
          Engineering: 'blue',
          'Research & Ops': 'geekblue',
          Marketing: 'magenta',
          Sales: 'orange',
          Operations: 'volcano',
          Finance: 'indigo',
          'Workflow Automations': 'purple',
        };
        const color = colorMap[d] || 'geekblue';
        return (
          <Tooltip title={record?.department_id ? `Department ID: ${record.department_id}` : undefined}>
            <Tag color={color} style={{ fontSize: '11px', margin: 0 }}>
              📁 {d}
            </Tag>
          </Tooltip>
        );
      },
    },
    {
      title: 'Model',
      dataIndex: 'model',
      key: 'model',
      render: (model?: string) => (
        <Tag color="geekblue" style={{ fontSize: '11px' }}>
          {model || 'default'}
        </Tag>
      ),
    },
    {
      title: 'Equipped Skills',
      dataIndex: 'skills',
      key: 'skills',
      render: (skillsList?: string[]) => {
        if (!skillsList || skillsList.length === 0) {
          return <span style={{ color: '#6e7681', fontSize: '11px' }}>Core reasoning</span>;
        }
        return (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', maxWidth: '240px' }}>
            {skillsList.slice(0, 3).map((s) => (
              <Tag key={s} color="cyan" style={{ fontSize: '10px', padding: '0 4px', margin: 0 }}>
                ⚡ {s}
              </Tag>
            ))}
            {skillsList.length > 3 && (
              <Tooltip title={skillsList.slice(3).join(', ')}>
                <Tag color="default" style={{ fontSize: '10px', padding: '0 4px', margin: 0, cursor: 'pointer' }}>
                  +{skillsList.length - 3} more
                </Tag>
              </Tooltip>
            )}
          </div>
        );
      },
    },
    {
      title: 'Linked Repository',
      dataIndex: 'repo_path',
      key: 'repo_path',
      render: (repo?: string, record?: Agent) => (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '2px', fontSize: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <FolderOpenOutlined style={{ color: '#e3b341' }} />
            <Tooltip title={repo || 'No local repo configured'}>
              <span style={{ color: repo ? '#58a6ff' : '#6e7681', maxWidth: '160px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {repo ? repo.split(/[\\/]/).pop() || repo : 'Default Workspace'}
              </span>
            </Tooltip>
          </div>
          {record?.github_url && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '10px', color: '#8b949e' }}>
              <GithubOutlined /> {record.github_url}
            </div>
          )}
        </div>
      ),
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_: any, record: Agent) => (
        <Space size="small">
          <Button
            size="small"
            type="primary"
            icon={<MessageOutlined />}
            style={{ background: '#2563eb', borderColor: '#2563eb' }}
            onClick={() => {
              setChatAgent(record);
              setChatVisible(true);
            }}
          >
            Chat
          </Button>
          <Button
            size="small"
            icon={<EditOutlined />}
            onClick={() => {
              const matchedDept = departments.find(
                (d) => d.id === record.department_id || d.name === record.department
              );
              form.setFieldsValue({
                name: record.name,
                description: record.description,
                system_prompt: record.system_prompt,
                department_id: record.department_id || matchedDept?.id || null,
                department: record.department || matchedDept?.name || 'Engineering',
                organization_id: record.organization_id || organization?.id || null,
                role_type: record.role_type || 'WORKER',
                parent_id: record.parent_id || null,
                max_concurrent_children: record.max_concurrent_children || 3,
                repo_path: record.repo_path,
                github_url: record.github_url,
                skills: record.skills,
                model: record.model,
                effort: record.effort,
                max_tokens: record.max_tokens,
                temperature: record.temperature,
                avatar: record.avatar || 'frontend_dev',
              });
              setEditingKey(record.id);
              setVisible(true);
            }}
          >
            Edit
          </Button>
          <Button
            size="small"
            danger
            icon={<DeleteOutlined />}
            onClick={() => {
              deleteAgent(record.id)
                .then(() => {
                  message.success('Agent removed');
                  fetchAgents();
                })
                .catch((err) => {
                  const detail = err.response?.data?.detail || 'Failed to delete agent';
                  message.error(detail);
                });
            }}
          >
            Delete
          </Button>
        </Space>
      ),
    },
  ];

  // Eligible supervisors for parent_id selection
  return columns;
};
