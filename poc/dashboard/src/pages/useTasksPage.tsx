import { useState } from 'react';
import { Form, Button, Modal, Tag, message, Space, Tree, Tooltip } from 'antd';
import { DeleteOutlined, SyncOutlined, EyeOutlined, BranchesOutlined, ApartmentOutlined, CheckCircleOutlined, CloseCircleOutlined, ClockCircleOutlined } from '@ant-design/icons';
import { Task, TaskTreeNode } from '../types/task';
import { Agent } from '../types/agent';
import { createTask, getTask, updateTask, deleteTask, cancelTask, delegateTask, getTaskTree } from '../services/api';
import { useOfficeEvents } from '../hooks/useOfficeEvents';

export const useTasksPage = () => {
  const { tasks, agents, loading, refresh } = useOfficeEvents();
  const [visible, setVisible] = useState<boolean>(false);
  const [form] = Form.useForm();
  const [editingKey, setEditingKey] = useState<string>('');

  // Task Details Modal
  const [taskDetail, setTaskDetail] = useState<Task | null>(null);
  const [detailVisible, setDetailVisible] = useState<boolean>(false);

  // Delegation Modal
  const [delegatingTask, setDelegatingTask] = useState<Task | null>(null);
  const [delegateModalVisible, setDelegateModalVisible] = useState<boolean>(false);
  const [delegateForm] = Form.useForm();
  const [delegating, setDelegating] = useState<boolean>(false);

  // Task Tree Modal
  const [treeModalVisible, setTreeModalVisible] = useState<boolean>(false);
  const [treeData, setTreeData] = useState<TaskTreeNode | null>(null);
  const [loadingTree, setLoadingTree] = useState<boolean>(false);

  const handleCreate = () => {
    form.resetFields();
    setEditingKey('');
    setVisible(true);
  };

  const handleOk = async () => {
    try {
      const values = await form.validateFields();
      let parsedInputData: Record<string, any>;
      try {
        parsedInputData = typeof values.input_data === 'string' ? JSON.parse(values.input_data) : values.input_data;
      } catch {
        parsedInputData = { task: values.prompt || values.input_data };
      }

      const taskData = {
        agent_id: String(values.agent_id),
        prompt: values.prompt,
        project_id: values.project_id ? String(values.project_id) : null,
        skill_id: values.skill_id ? String(values.skill_id) : null,
        input_data: parsedInputData,
      };

      if (editingKey) {
        await updateTask(editingKey, taskData);
        message.success('Task updated successfully');
      } else {
        await createTask(taskData);
        message.success('Task dispatched successfully');
      }
      setVisible(false);
      refresh();
    } catch (err: any) {
      const detail = err.response?.data?.detail || 'Failed to save task';
      message.error(detail);
      console.error(err);
    }
  };

  // Delegation
  const handleOpenDelegate = (task: Task) => {
    setDelegatingTask(task);
    delegateForm.resetFields();
    delegateForm.setFieldsValue({
      timeout_seconds: 300,
    });
    setDelegateModalVisible(true);
  };

  const handleDelegateSubmit = async () => {
    if (!delegatingTask) return;
    try {
      const values = await delegateForm.validateFields();
      setDelegating(true);

      await delegateTask(delegatingTask.id, {
        target_agent_id: values.target_agent_id,
        subtask_prompt: values.subtask_prompt,
        timeout_seconds: values.timeout_seconds || 300,
      });

      message.success(`Subtask delegated to ${values.target_agent_id}!`);
      setDelegateModalVisible(false);
      refresh();
    } catch (err: any) {
      const detail = err.response?.data?.detail || 'Delegation failed';
      message.error(detail);
    } finally {
      setDelegating(false);
    }
  };

  // Task Tree
  const handleOpenTree = async (task: Task) => {
    try {
      setLoadingTree(true);
      setTreeModalVisible(true);
      const res = await getTaskTree(task.id);
      setTreeData(res.data);
    } catch (err: any) {
      message.error('Failed to load task execution tree');
      setTreeModalVisible(false);
    } finally {
      setLoadingTree(false);
    }
  };

  const convertTreeToNodes = (node: TaskTreeNode): any => {
    const statusColor =
      node.status === 'completed'
        ? '#10b981'
        : node.status === 'running'
        ? '#3b82f6'
        : node.status === 'failed'
        ? '#ef4444'
        : '#f59e0b';

    return {
      key: node.run_id,
      title: (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '4px 8px',
            background: '#1e293b',
            border: `1px solid ${statusColor}44`,
            borderRadius: '6px',
            minWidth: '320px',
          }}
        >
          {node.status === 'completed' ? (
            <CheckCircleOutlined style={{ color: '#10b981' }} />
          ) : node.status === 'running' ? (
            <SyncOutlined spin style={{ color: '#3b82f6' }} />
          ) : node.status === 'failed' ? (
            <CloseCircleOutlined style={{ color: '#ef4444' }} />
          ) : (
            <ClockCircleOutlined style={{ color: '#f59e0b' }} />
          )}

          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 600, fontSize: '12px', color: '#f8fafc' }}>
              🤖 {node.agent_id}
              <Tag color={node.status === 'completed' ? 'green' : node.status === 'running' ? 'blue' : 'default'} style={{ marginLeft: '6px', fontSize: '9px' }}>
                {node.status.toUpperCase()}
              </Tag>
            </div>
            <div style={{ fontSize: '11px', color: '#94a3b8' }}>
              {node.prompt ? (node.prompt.length > 50 ? `${node.prompt.slice(0, 50)}...` : node.prompt) : 'Subtask execution'}
            </div>
            {node.result && (
              <div style={{ fontSize: '10px', color: '#34d399', marginTop: '2px' }}>
                Result: {node.result.length > 60 ? `${node.result.slice(0, 60)}...` : node.result}
              </div>
            )}
          </div>
        </div>
      ),
      children: node.children ? node.children.map(convertTreeToNodes) : [],
    };
  };

  const columns = [
    {
      title: 'Task ID',
      dataIndex: 'id',
      key: 'id',
      render: (id: string, record: Task) => (
        <div>
          <span style={{ fontWeight: 600, color: '#f3f4f6', fontFamily: 'monospace', fontSize: '12px' }}>
            {id.length > 16 ? `${id.slice(0, 16)}...` : id}
          </span>
          {record.parent_task_id && (
            <div style={{ fontSize: '10px', color: '#94a3b8' }}>
              ↳ Subtask of: {record.parent_task_id.slice(0, 12)}...
            </div>
          )}
        </div>
      ),
    },
    {
      title: 'Assigned Agent',
      dataIndex: 'agent_id',
      key: 'agent_id',
      render: (val: string, record: Task) => {
        const agent = agents.find((a) => a.id === val);
        const role = agent ? (agent.role_type || 'WORKER').toUpperCase() : '';
        return (
          <div>
            <div style={{ fontWeight: 600, color: '#38bdf8', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <span>🤖 {agent ? agent.name : val}</span>
              {role && (
                <Tag color={role === 'MANAGER' ? 'gold' : role === 'ROOT_ORCHESTRATOR' ? 'purple' : 'blue'} style={{ fontSize: '9px', margin: 0 }}>
                  {role}
                </Tag>
              )}
            </div>
            {record.assigned_by && (
              <div style={{ fontSize: '10px', color: '#64748b' }}>
                Delegated by: {record.assigned_by}
              </div>
            )}
          </div>
        );
      },
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => {
        const color =
          status === 'completed'
            ? 'green'
            : status === 'running'
            ? 'blue'
            : status === 'failed'
            ? 'red'
            : 'default';
        return <Tag color={color}>{status.toUpperCase()}</Tag>;
      },
    },
    {
      title: 'Created At',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (date: string) => (
        <span style={{ fontSize: '11px', color: '#8b949e' }}>
          {date ? new Date(date).toLocaleTimeString() : 'N/A'}
        </span>
      ),
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_: any, record: Task) => {
        const assignedAgent = agents.find((a) => a.id === record.agent_id);
        const isManager =
          assignedAgent &&
          ((assignedAgent.role_type || '').toUpperCase() === 'MANAGER' ||
            (assignedAgent.role_type || '').toUpperCase() === 'ROOT_ORCHESTRATOR');

        return (
          <Space size="small">
            {/* Delegate Subtask Button (for Managers) */}
            {isManager && (
              <Tooltip title="Delegate subtask to subordinate">
                <Button
                  size="small"
                  type="primary"
                  icon={<BranchesOutlined />}
                  onClick={() => handleOpenDelegate(record)}
                  style={{ background: '#0284c7', borderColor: '#0284c7' }}
                >
                  Delegate
                </Button>
              </Tooltip>
            )}

            {/* View Execution Tree */}
            <Tooltip title="View subtask execution tree">
              <Button
                size="small"
                icon={<ApartmentOutlined />}
                onClick={() => handleOpenTree(record)}
              >
                Tree
              </Button>
            </Tooltip>

            {/* View Details / Logs */}
            <Button
              size="small"
              icon={<EyeOutlined />}
              onClick={() => {
                setTaskDetail(record);
                setDetailVisible(true);
                getTask(record.id)
                  .then((res) => {
                    if (res.data) {
                      setTaskDetail(res.data);
                    }
                  })
                  .catch((err) => {
                    console.warn('Live task detail refresh skipped:', err);
                  });
              }}
            >
              Logs
            </Button>

            {record.status === 'running' && (
              <Button
                size="small"
                danger
                icon={<SyncOutlined />}
                onClick={() => {
                  cancelTask(record.id)
                    .then(() => {
                      message.success('Task cancelled');
                      refresh();
                    })
                    .catch(() => message.error('Failed to cancel task'));
                }}
              >
                Cancel
              </Button>
            )}

            <Button
              size="small"
              danger
              icon={<DeleteOutlined />}
              title="Delete task"
              onClick={() => {
                deleteTask(record.id)
                  .then(() => {
                    message.success('Task deleted');
                    refresh();
                  })
                  .catch(() => message.error('Failed to delete task'));
              }}
            />
          </Space>
        );
      },
    },
  ];

  // Candidates for delegation target
  const getSubordinateWorkers = (managerAgentId?: string) => {
    if (!managerAgentId) return agents;
    const mgr = agents.find((a) => a.id === managerAgentId);
    if (!mgr) return agents;
    // Return subordinates reporting to this manager, or all workers if root
    const isRoot = (mgr.role_type || '').toUpperCase() === 'ROOT_ORCHESTRATOR';
    if (isRoot) return agents.filter((a) => a.id !== managerAgentId);
    return agents.filter((a) => a.parent_id === managerAgentId || a.id !== managerAgentId);
  };

  return {
    tasks,
    agents,
    loading,
    refresh,
    visible,
    setVisible,
    form,
    editingKey,
    setEditingKey,
    taskDetail,
    setTaskDetail,
    detailVisible,
    setDetailVisible,
    delegatingTask,
    setDelegatingTask,
    delegateModalVisible,
    setDelegateModalVisible,
    delegateForm,
    delegating,
    setDelegating,
    treeModalVisible,
    setTreeModalVisible,
    treeData,
    setTreeData,
    loadingTree,
    setLoadingTree,
    handleCreate,
    handleOk,
    handleOpenDelegate,
    handleDelegateSubmit,
    handleOpenTree,
    convertTreeToNodes,
    columns,
    getSubordinateWorkers,
  };
};
