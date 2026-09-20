import React, { useEffect, useState } from 'react';
import {
  Table,
  Form,
  Input,
  Button,
  Modal,
  Tag,
  Select,
  message,
  Tooltip,
} from 'antd';
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  FolderOpenOutlined,
  GithubOutlined,
  LaptopOutlined,
} from '@ant-design/icons';
import { Agent } from '../types/agent';
import { getAgents, createAgent, updateAgent, deleteAgent, getSkills } from '../services/api';
import { AI_MODELS } from '../constants/models';

const DEPARTMENTS = [
  'Engineering',
  'Architecture',
  'QA & Testing',
  'Research & Ops',
];

export const AgentsPage: React.FC = () => {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [availableSkills, setAvailableSkills] = useState<{ label: string; value: string }[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [visible, setVisible] = useState<boolean>(false);
  const [form] = Form.useForm();
  const [editingKey, setEditingKey] = useState<string>('');

  const fetchAgents = async () => {
    try {
      setLoading(true);
      const res = await getAgents();
      setAgents(res.data || []);
    } catch (err) {
      console.error(err);
      message.error('Failed to load agents roster');
    } finally {
      setLoading(false);
    }
  };

  const fetchSkillsList = async () => {
    try {
      const res = await getSkills();
      if (res.data) {
        setAvailableSkills(res.data.map((s) => ({ label: s.name, value: s.id })));
      }
    } catch {
      // Fallback
    }
  };

  useEffect(() => {
    fetchAgents();
    fetchSkillsList();
  }, []);

  const handleCreate = () => {
    form.resetFields();
    setEditingKey('');
    setVisible(true);
  };

  const handleOk = async () => {
    try {
      const values = await form.validateFields();
      if (editingKey) {
        await updateAgent(editingKey, values);
        message.success('Agent updated successfully');
      } else {
        await createAgent(values);
        message.success('Agent created successfully');
      }
      setVisible(false);
      fetchAgents();
    } catch (err) {
      message.error('Failed to save agent');
      console.error(err);
    }
  };

  const columns = [
    {
      title: 'Agent Name & Role',
      dataIndex: 'name',
      key: 'name',
      render: (name: string, record: Agent) => (
        <div>
          <div style={{ fontWeight: 600, color: '#f3f4f6', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <LaptopOutlined /> {name}
          </div>
          <div style={{ fontSize: '11px', color: '#9ca3af' }}>{record.description || 'General Purpose Agent'}</div>
        </div>
      ),
    },
    {
      title: 'Department',
      dataIndex: 'department',
      key: 'department',
      render: (dept?: string) => (
        <Tag color={dept === 'Architecture' ? 'purple' : dept === 'QA & Testing' ? 'cyan' : 'blue'}>
          {dept || 'Engineering'}
        </Tag>
      ),
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
              <span style={{ color: repo ? '#58a6ff' : '#6e7681', maxWidth: '180px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
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
      title: 'Equipped Skills',
      dataIndex: 'skills',
      key: 'skills',
      render: (skills: string[] = []) => (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
          {skills.length === 0 ? (
            <span style={{ color: '#6e7681', fontSize: '11px' }}>Core Builtins</span>
          ) : (
            skills.map((s) => (
              <Tag key={s} color="geekblue" style={{ fontSize: '10px' }}>
                {s}
              </Tag>
            ))
          )}
        </div>
      ),
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_: any, record: Agent) => (
        <div style={{ display: 'flex', gap: '8px' }}>
          <Button
            size="small"
            icon={<EditOutlined />}
            onClick={() => {
              form.setFieldsValue({
                name: record.name,
                description: record.description,
                system_prompt: record.system_prompt,
                department: record.department || 'Engineering',
                repo_path: record.repo_path,
                github_url: record.github_url,
                skills: record.skills,
                model: record.model,
                effort: record.effort,
                max_tokens: record.max_tokens,
                temperature: record.temperature,
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
                  message.error('Failed to delete agent');
                  console.error(err);
                });
            }}
          >
            Delete
          </Button>
        </div>
      ),
    },
  ];

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <div>
          <h2 style={{ margin: 0, color: '#f3f4f6', fontSize: '22px', fontWeight: 700 }}>
            🤖 Agents Roster & Configuration
          </h2>
          <span style={{ color: '#9ca3af', fontSize: '13px' }}>
            Manage virtual team members, local repo links, departments and skill allocations
          </span>
        </div>

        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={handleCreate}
          style={{ background: '#238636', borderColor: '#238636' }}
        >
          Hire New Agent
        </Button>
      </div>

      <Table
        loading={loading}
        rowKey="id"
        columns={columns}
        dataSource={agents}
        pagination={{ pageSize: 10 }}
      />

      {/* Agent Modal */}
      <Modal
        title={editingKey ? 'Configure Agent' : 'Hire New Agent'}
        open={visible}
        onOk={handleOk}
        onCancel={() => setVisible(false)}
        width={620}
      >
        <Form
          form={form}
          layout="vertical"
          initialValues={{
            department: 'Engineering',
            model: 'default',
            effort: 'medium',
            temperature: 0.7,
            max_tokens: 4000,
            repo_path: 'C:\\Users\\taguo\\OneDrive\\Desktop\\Projects\\test',
          }}
        >
          <Form.Item label="Agent Name" name="name" rules={[{ required: true, message: 'Please input agent name!' }]}>
            <Input placeholder="e.g. Backend Lead Agent" />
          </Form.Item>

          <Form.Item label="Department / Role" name="department">
            <Select>
              {DEPARTMENTS.map((dept) => (
                <Select.Option key={dept} value={dept}>
                  {dept}
                </Select.Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item label="Description" name="description">
            <Input placeholder="Primary responsibility and specialty" />
          </Form.Item>

          <Form.Item
            label="Linked Local Repository Path (on PC)"
            name="repo_path"
            tooltip="Path to local codebase where this agent executes commands and edits code"
          >
            <Input prefix={<FolderOpenOutlined style={{ color: '#e3b341' }} />} placeholder="C:\Users\taguo\OneDrive\Desktop\Projects\test" />
          </Form.Item>

          <Form.Item label="GitHub Repository URL (Optional)" name="github_url">
            <Input prefix={<GithubOutlined />} placeholder="https://github.com/ajsahni/agents-office" />
          </Form.Item>

          <Form.Item
            label="AI Model (FCC Overridden)"
            name="model"
            rules={[{ required: true, message: 'Please select an AI model!' }]}
            tooltip="Select the underlying Free Claude Code model alias for this agent"
          >
            <Select
              showSearch
              placeholder="Select model (Default, Sonnet, Opus, Haiku, Fable)"
              options={AI_MODELS}
              optionFilterProp="label"
            />
          </Form.Item>

          <Form.Item
            label="Reasoning Effort / Budget"
            name="effort"
          >
            <Select>
              <Select.Option value="low">Low (Fast responses)</Select.Option>
              <Select.Option value="medium">Medium (Balanced)</Select.Option>
              <Select.Option value="high">High (Deep reasoning & verification)</Select.Option>
            </Select>
          </Form.Item>

          <Form.Item label="System Prompt" name="system_prompt" rules={[{ required: true, message: 'System prompt required!' }]}>
            <Input.TextArea rows={4} placeholder="You are an autonomous AI software engineer..." />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default AgentsPage;
