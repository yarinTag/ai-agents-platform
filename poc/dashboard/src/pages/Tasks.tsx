import React, { useEffect, useState } from 'react';
import {
  Table,
  Form,
  Input,
  Button,
  Modal,
  Tag,
  message,
  Select,
  InputNumber,
  Space,
  Tree,
  Card,
  Tooltip,
} from 'antd';
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  SyncOutlined,
  EyeOutlined,
  BranchesOutlined,
  ApartmentOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ClockCircleOutlined,
} from '@ant-design/icons';
import { Task, TaskTreeNode } from '../types/task';
import { Agent } from '../types/agent';
import {
  getTasks,
  createTask,
  getTask,
  updateTask,
  deleteTask,
  cancelTask,
  getAgents,
  delegateTask,
  getTaskTree,
} from '../services/api';
import { useOfficeEvents } from '../hooks/useOfficeEvents';

export const TasksPage: React.FC = () => {
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

            {/* View Details */}
            <Button
              size="small"
              icon={<EyeOutlined />}
              onClick={() => {
                getTask(record.id)
                  .then((res) => {
                    setTaskDetail(res.data);
                    setDetailVisible(true);
                  })
                  .catch(() => message.error('Failed to load task details'));
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
              disabled={record.status === 'running'}
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

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <div>
          <h2 style={{ margin: 0, color: '#f3f4f6', fontSize: '22px', fontWeight: 700 }}>
            📋 Task Orchestration & Execution Queue
          </h2>
          <span style={{ color: '#9ca3af', fontSize: '13px' }}>
            Live asynchronous executions, structured subtask delegation, and result lineage.
          </span>
        </div>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={handleCreate}
          style={{ background: '#10b981', borderColor: '#10b981', borderRadius: '8px' }}
        >
          Dispatch New Task
        </Button>
      </div>

      <Table
        dataSource={tasks}
        columns={columns}
        rowKey="id"
        loading={loading}
        pagination={{ pageSize: 10 }}
        style={{ background: '#161b22', borderRadius: '12px', overflow: 'hidden' }}
      />

      {/* Dispatch New Task Modal */}
      <Modal
        title={editingKey ? 'Edit Task' : 'Dispatch Autonomous Task'}
        open={visible}
        onOk={handleOk}
        onCancel={() => setVisible(false)}
        okText="Dispatch"
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="agent_id"
            label="Assigned Agent"
            rules={[{ required: true, message: 'Please select an agent' }]}
          >
            <Select placeholder="Select executor">
              {agents.map((a) => (
                <Select.Option key={a.id} value={a.id}>
                  🤖 {a.name} ({a.role_type || 'WORKER'} - {a.department || 'General'})
                </Select.Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item
            name="prompt"
            label="Task Prompt / Objective"
            rules={[{ required: true, message: 'Task prompt is required' }]}
          >
            <Input.TextArea rows={4} placeholder="Analyze codebase and create report..." />
          </Form.Item>
        </Form>
      </Modal>

      {/* Delegate Subtask Modal */}
      <Modal
        title={`Delegate Subtask from ${delegatingTask?.agent_id}`}
        open={delegateModalVisible}
        onOk={handleDelegateSubmit}
        onCancel={() => setDelegateModalVisible(false)}
        confirmLoading={delegating}
        okText="Delegate Subtask"
      >
        <Form form={delegateForm} layout="vertical">
          <Form.Item
            name="target_agent_id"
            label="Target Subordinate Agent"
            rules={[{ required: true, message: 'Please select a subordinate agent' }]}
          >
            <Select placeholder="Select subordinate worker">
              {getSubordinateWorkers(delegatingTask?.agent_id).map((a) => (
                <Select.Option key={a.id} value={a.id}>
                  💻 {a.name} ({a.role_type} - {a.department})
                </Select.Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item
            name="subtask_prompt"
            label="Subtask Instructions"
            rules={[{ required: true, message: 'Subtask instructions are required' }]}
          >
            <Input.TextArea rows={3} placeholder="Implement database migration or run test suite..." />
          </Form.Item>

          <Form.Item name="timeout_seconds" label="Timeout (Seconds)">
            <InputNumber min={10} max={3600} style={{ width: '100%' }} />
          </Form.Item>
        </Form>
      </Modal>

      {/* Task Execution Tree Modal */}
      <Modal
        title="Execution Lineage Tree"
        open={treeModalVisible}
        onOk={() => setTreeModalVisible(false)}
        onCancel={() => setTreeModalVisible(false)}
        footer={[
          <Button key="close" onClick={() => setTreeModalVisible(false)}>
            Close
          </Button>,
        ]}
        width={600}
      >
        {loadingTree ? (
          <div style={{ textAlign: 'center', padding: '40px 0' }}>
            <SyncOutlined spin style={{ fontSize: '24px', color: '#38bdf8' }} />
          </div>
        ) : treeData ? (
          <Card style={{ background: '#0f172a', border: '1px solid #334155', borderRadius: '10px' }}>
            <Tree
              showLine
              defaultExpandAll
              treeData={[convertTreeToNodes(treeData)]}
              style={{ background: 'transparent', color: '#f8fafc' }}
            />
          </Card>
        ) : (
          <div>No subtasks found for this execution.</div>
        )}
      </Modal>

      {/* Task Details / Logs Modal */}
      <Modal
        title={`Task Run: ${taskDetail?.id}`}
        open={detailVisible}
        onOk={() => setDetailVisible(false)}
        onCancel={() => setDetailVisible(false)}
        width={650}
        footer={[
          <Button key="ok" type="primary" onClick={() => setDetailVisible(false)}>
            Done
          </Button>,
        ]}
      >
        {taskDetail && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div>
              <strong>Prompt:</strong>
              <div style={{ background: '#1e293b', padding: '8px', borderRadius: '6px', marginTop: '4px', fontSize: '12px' }}>
                {taskDetail.prompt || 'N/A'}
              </div>
            </div>

            {taskDetail.result && (
              <div>
                <strong>Result:</strong>
                <pre style={{ background: '#0f172a', padding: '10px', borderRadius: '6px', marginTop: '4px', maxHeight: '200px', overflowY: 'auto', fontSize: '11px', color: '#34d399' }}>
                  {taskDetail.result}
                </pre>
              </div>
            )}

            {taskDetail.error && (
              <div>
                <strong>Error:</strong>
                <pre style={{ background: '#450a0a', padding: '10px', borderRadius: '6px', marginTop: '4px', maxHeight: '150px', overflowY: 'auto', fontSize: '11px', color: '#f87171' }}>
                  {taskDetail.error}
                </pre>
              </div>
            )}
          </div>
        )}
      </Modal>
    </div>
  );
};

export default TasksPage;
