import React, { useEffect, useState } from 'react';
import {
  Table,
  Form,
  Input,
  Button,
  Modal,
  Tag,
  message,
} from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined, SyncOutlined, EyeOutlined } from '@ant-design/icons';
import { Task } from '../types/task';
import { getTasks, createTask, getTask, updateTask, deleteTask, cancelTask } from '../services/api';

export const TasksPage: React.FC = () => {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [visible, setVisible] = useState<boolean>(false);
  const [form] = Form.useForm();
  const [editingKey, setEditingKey] = useState<string>('');
  const [taskDetail, setTaskDetail] = useState<Task | null>(null);
  const [detailVisible, setDetailVisible] = useState<boolean>(false);

  const fetchTasks = async () => {
    try {
      setLoading(true);
      const response = await getTasks();
      setTasks(response.data || []);
    } catch (err) {
      console.error(err);
      message.error('Failed to load tasks queue');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTasks();
  }, []);

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
        message.error('Invalid JSON format in Input Data');
        return;
      }

      const taskData = {
        agent_id: String(values.agent_id),
        project_id: values.project_id ? String(values.project_id) : null,
        skill_id: values.skill_id ? String(values.skill_id) : null,
        input_data: parsedInputData,
      };

      if (editingKey) {
        await updateTask(editingKey, taskData);
        message.success('Task updated successfully');
      } else {
        await createTask(taskData);
        message.success('Task created successfully');
      }
      setVisible(false);
      fetchTasks();
    } catch (err) {
      message.error('Failed to save task');
      console.error(err);
    }
  };

  const columns = [
    {
      title: 'Agent ID',
      dataIndex: 'agent_id',
      key: 'agent_id',
      render: (val: string) => <span style={{ fontWeight: 600, color: '#f3f4f6' }}>🤖 {val}</span>,
    },
    {
      title: 'Project ID',
      dataIndex: 'project_id',
      key: 'project_id',
      render: (val?: string) => val ?? <span style={{ color: '#6e7681' }}>Global</span>,
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => {
        const color = status === 'completed' ? 'green' : status === 'running' ? 'blue' : status === 'failed' ? 'red' : 'default';
        return <Tag color={color}>{status.toUpperCase()}</Tag>;
      },
    },
    {
      title: 'Created At',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (date: string) => <span style={{ fontSize: '11px', color: '#8b949e' }}>{date ? new Date(date).toLocaleString() : 'N/A'}</span>,
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_: any, record: Task) => (
        <div style={{ display: 'flex', gap: '6px' }}>
          <Button
            size="small"
            icon={<EditOutlined />}
            disabled={record.status === 'running' || record.status === 'completed'}
            onClick={() => {
              getTask(record.id)
                .then((res) => {
                  const data = res.data;
                  form.setFieldsValue({
                    agent_id: data.agent_id,
                    project_id: data.project_id || undefined,
                    skill_id: data.skill_id || undefined,
                    input_data: typeof data.input_data === 'object' ? JSON.stringify(data.input_data, null, 2) : data.input_data,
                  });
                  setEditingKey(record.id);
                  setVisible(true);
                })
                .catch((err) => {
                  message.error('Failed to load task');
                  console.error(err);
                });
            }}
          >
            Edit
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
                    fetchTasks();
                  })
                  .catch((err) => {
                    message.error('Failed to cancel task');
                    console.error(err);
                  });
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
                  fetchTasks();
                })
                .catch((err) => {
                  message.error('Failed to delete task');
                  console.error(err);
                });
            }}
          >
            Delete
          </Button>

          <Button
            size="small"
            icon={<EyeOutlined />}
            onClick={() => {
              getTask(record.id)
                .then((res) => {
                  setTaskDetail(res.data);
                  setDetailVisible(true);
                })
                .catch((err) => {
                  message.error('Failed to load task details');
                  console.error(err);
                });
            }}
          >
            View
          </Button>
        </div>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <div>
          <h2 style={{ margin: 0, color: '#f3f4f6', fontSize: '22px', fontWeight: 700 }}>
            📋 Task Queue & Executions
          </h2>
          <span style={{ color: '#9ca3af', fontSize: '13px' }}>
            Inspect in-flight operations, input payloads, and deliverable outputs
          </span>
        </div>

        <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate} style={{ background: '#238636', borderColor: '#238636' }}>
          Dispatch Task
        </Button>
      </div>

      <Table
        loading={loading}
        rowKey="id"
        columns={columns}
        dataSource={tasks}
        pagination={{ pageSize: 10 }}
      />

      <Modal
        title={editingKey ? 'Edit Task' : 'Dispatch New Task'}
        open={visible}
        onOk={handleOk}
        onCancel={() => setVisible(false)}
      >
        <Form form={form} layout="vertical">
          <Form.Item label="Agent ID" name="agent_id" rules={[{ required: true, message: 'Please input agent ID!' }]}>
            <Input placeholder="e.g. backend-lead or 1" />
          </Form.Item>
          <Form.Item label="Project ID (Optional)" name="project_id">
            <Input placeholder="e.g. smarttrader" />
          </Form.Item>
          <Form.Item
            label="Input Data (JSON)"
            name="input_data"
            rules={[
              { required: true, message: 'JSON input required!' },
              {
                validator: (_, value) => {
                  if (!value) return Promise.resolve();
                  try {
                    JSON.parse(value);
                    return Promise.resolve();
                  } catch {
                    return Promise.reject(new Error('Please enter valid JSON!'));
                  }
                },
              },
            ]}
          >
            <Input.TextArea rows={4} placeholder='{"prompt": "Run tests on repository"}' />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="Task Execution Details"
        open={detailVisible}
        onCancel={() => setDetailVisible(false)}
        footer={[
          <Button key="close" onClick={() => setDetailVisible(false)}>
            Close
          </Button>,
        ]}
      >
        {taskDetail && (
          <div>
            <p><strong>Task ID:</strong> #{taskDetail.id}</p>
            <p><strong>Agent:</strong> {taskDetail.agent_id}</p>
            <p><strong>Status:</strong> <Tag color={taskDetail.status === 'completed' ? 'green' : 'blue'}>{taskDetail.status}</Tag></p>
            <div><strong>Input Data:</strong></div>
            <pre style={{ background: '#161b22', padding: '10px', borderRadius: '6px', color: '#c9d1d9' }}>
              {typeof taskDetail.input_data === 'string' ? taskDetail.input_data : JSON.stringify(taskDetail.input_data, null, 2)}
            </pre>
            <div><strong>Output Data:</strong></div>
            <pre style={{ background: '#161b22', padding: '10px', borderRadius: '6px', color: '#58a6ff' }}>
              {taskDetail.output_data ? JSON.stringify(taskDetail.output_data, null, 2) : 'No output produced yet'}
            </pre>
          </div>
        )}
      </Modal>
    </div>
  );
};

export default TasksPage;
