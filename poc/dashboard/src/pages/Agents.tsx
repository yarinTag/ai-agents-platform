import React, { useEffect, useState } from 'react';
import {
  Table,
  Form,
  Input,
  Button,
  Modal,
  Tag,
  Select,
  InputNumber,
  message,
  Tooltip,
  Tabs,
  Space,
} from 'antd';
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  FolderOpenOutlined,
  GithubOutlined,
  LaptopOutlined,
  CrownOutlined,
  StarOutlined,
  UserOutlined,
  BranchesOutlined,
  BookOutlined,
  TeamOutlined,
  MessageOutlined,
} from '@ant-design/icons';
import { Agent, AgentRole } from '../types/agent';
import {
  getAgents,
  createAgent,
  updateAgent,
  deleteAgent,
  getSkills,
  getAvailableModels,
  DiscoveredModel,
  scanPlugins,
} from '../services/api';
import { CharacterSelector } from '../components/agents/CharacterSelector';
import { TemplateGallery } from '../components/agents/TemplateGallery';
import { HierarchyEditor } from '../components/agents/HierarchyEditor';
import { AgentMiniChatDrawer } from '../components/chat/AgentMiniChatDrawer';

const DEPARTMENTS = [
  'Engineering',
  'Architecture',
  'QA & Testing',
  'Research & Ops',
  'HQ',
];

export const AgentsPage: React.FC = () => {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [availableSkills, setAvailableSkills] = useState<any[]>([]);
  const [availableModels, setAvailableModels] = useState<DiscoveredModel[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [visible, setVisible] = useState<boolean>(false);
  const [form] = Form.useForm();
  const [editingKey, setEditingKey] = useState<string>('');
  const [activeTab, setActiveTab] = useState<string>('roster');
  const [chatAgent, setChatAgent] = useState<Agent | null>(null);
  const [chatVisible, setChatVisible] = useState<boolean>(false);

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

  const fetchSkillsAndModels = async () => {
    try {
      const [skillsRes, pluginsRes, modelsRes] = await Promise.all([
        getSkills().catch(() => ({ data: [] })),
        scanPlugins().catch(() => ({ data: { plugins: [] } })),
        getAvailableModels().catch(() => ({ data: [] })),
      ]);

      const formattedOptions: any[] = [];

      if (pluginsRes.data && pluginsRes.data.plugins) {
        pluginsRes.data.plugins.forEach((pkg: any) => {
          if (pkg.skills && pkg.skills.length > 0) {
            formattedOptions.push({
              label: `📦 ${pkg.display_name || pkg.name.toUpperCase()} (${pkg.skills.length})`,
              title: pkg.name,
              options: pkg.skills.map((s: any) => ({
                label: `⚡ ${s.name} (${s.id})`,
                value: s.id,
                title: s.description,
              })),
            });
          }
        });
      }

      if (skillsRes.data && skillsRes.data.length > 0) {
        formattedOptions.push({
          label: `💾 Custom / DB Skills (${skillsRes.data.length})`,
          title: 'custom',
          options: skillsRes.data.map((s: any) => ({
            label: `⚡ ${s.name} (${s.id})`,
            value: s.id,
            title: s.description || '',
          })),
        });
      }

      setAvailableSkills(formattedOptions);

      if (modelsRes.data) {
        setAvailableModels(modelsRes.data);
      }
    } catch {
      // Fallback
    }
  };

  useEffect(() => {
    fetchAgents();
    fetchSkillsAndModels();
  }, []);

  const handleCreate = () => {
    form.resetFields();
    form.setFieldsValue({
      role_type: 'WORKER',
      department: 'Engineering',
      model: 'default',
      max_tokens: 8000,
      temperature: 0.7,
      max_concurrent_children: 3,
      avatar: 'frontend_dev',
    });
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
    } catch (err: any) {
      const detail = err.response?.data?.detail || 'Failed to save agent';
      message.error(detail);
      console.error(err);
    }
  };

  const columns = [
    {
      title: 'Agent Name & Role',
      dataIndex: 'name',
      key: 'name',
      render: (name: string, record: Agent) => {
        const role = (record.role_type || 'WORKER').toUpperCase();
        return (
          <div>
            <div style={{ fontWeight: 600, color: '#f3f4f6', display: 'flex', alignItems: 'center', gap: '6px' }}>
              {role === 'ROOT_ORCHESTRATOR' ? (
                <CrownOutlined style={{ color: '#fbbf24' }} />
              ) : role === 'MANAGER' ? (
                <StarOutlined style={{ color: '#f59e0b' }} />
              ) : (
                <LaptopOutlined style={{ color: '#38bdf8' }} />
              )}
              <span>{name}</span>
              <Tag
                color={
                  role === 'ROOT_ORCHESTRATOR'
                    ? 'purple'
                    : role === 'MANAGER'
                    ? 'gold'
                    : role === 'SPECIALIST'
                    ? 'magenta'
                    : 'cyan'
                }
                style={{ fontSize: '10px', padding: '0 4px', margin: 0 }}
              >
                {role}
              </Tag>
            </div>
            <div style={{ fontSize: '11px', color: '#9ca3af' }}>{record.description || 'General Purpose Agent'}</div>
          </div>
        );
      },
    },
    {
      title: 'Supervisor (Parent)',
      dataIndex: 'parent_id',
      key: 'parent_id',
      render: (parentId?: string) => {
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
      render: (dept?: string) => (
        <Tag color={dept === 'Architecture' ? 'purple' : dept === 'QA & Testing' ? 'cyan' : dept === 'HQ' ? 'gold' : 'blue'}>
          {dept || 'Engineering'}
        </Tag>
      ),
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
              form.setFieldsValue({
                name: record.name,
                description: record.description,
                system_prompt: record.system_prompt,
                department: record.department || 'Engineering',
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
  const eligibleManagers = agents.filter((a) => {
    if (editingKey && a.id === editingKey) return false;
    const r = (a.role_type || '').toUpperCase();
    return r === 'MANAGER' || r === 'ROOT_ORCHESTRATOR';
  });

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <div>
          <h2 style={{ margin: 0, color: '#f3f4f6', fontSize: '22px', fontWeight: 700 }}>
            👥 Agent Management & Team Hierarchy
          </h2>
          <span style={{ color: '#9ca3af', fontSize: '13px' }}>
            Assemble multi-agent units, define reporting lines, and manage model parameters.
          </span>
        </div>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={handleCreate}
          style={{ background: '#10b981', borderColor: '#10b981', borderRadius: '8px' }}
        >
          Create Custom Agent
        </Button>
      </div>

      {/* Tabs */}
      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={[
          {
            key: 'roster',
            label: (
              <span>
                <TeamOutlined /> Active Roster ({agents.length})
              </span>
            ),
            children: (
              <Table
                dataSource={agents}
                columns={columns}
                rowKey="id"
                loading={loading}
                pagination={{ pageSize: 8 }}
                style={{ background: '#161b22', borderRadius: '12px', overflow: 'hidden' }}
              />
            ),
          },
          {
            key: 'hierarchy',
            label: (
              <span>
                <BranchesOutlined /> Hierarchy Tree
              </span>
            ),
            children: <HierarchyEditor onHierarchyUpdated={fetchAgents} />,
          },
          {
            key: 'templates',
            label: (
              <span>
                <BookOutlined /> Template Gallery
              </span>
            ),
            children: <TemplateGallery agents={agents} onAgentInstantiated={fetchAgents} />,
          },
        ]}
      />

      {/* Agent Create / Edit Modal */}
      <Modal
        title={editingKey ? 'Edit Agent Profile & Hierarchy' : 'Create Autonomous Agent'}
        open={visible}
        onOk={handleOk}
        onCancel={() => setVisible(false)}
        width={720}
        okText={editingKey ? 'Save Changes' : 'Deploy Agent'}
        destroyOnClose
      >
        <Form form={form} layout="vertical">
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
            <Form.Item
              name="name"
              label="Agent Name"
              rules={[{ required: true, message: 'Agent name is required' }]}
            >
              <Input placeholder="e.g. Lead Architect" />
            </Form.Item>

            <Form.Item name="department" label="Department">
              <Select>
                {DEPARTMENTS.map((d) => (
                  <Select.Option key={d} value={d}>
                    {d}
                  </Select.Option>
                ))}
              </Select>
            </Form.Item>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
            <Form.Item
              name="role_type"
              label="Role & Delegation Authority"
              rules={[{ required: true, message: 'Role is required' }]}
            >
              <Select>
                <Select.Option value="ROOT_ORCHESTRATOR">👑 ROOT_ORCHESTRATOR (Top Executive)</Select.Option>
                <Select.Option value="MANAGER">⭐ MANAGER (Can Supervise & Delegate)</Select.Option>
                <Select.Option value="WORKER">💻 WORKER (Task Executor)</Select.Option>
                <Select.Option value="SPECIALIST">🛡️ SPECIALIST (Domain Expert)</Select.Option>
              </Select>
            </Form.Item>

            <Form.Item
              noStyle
              shouldUpdate={(prev, curr) => prev.role_type !== curr.role_type}
            >
              {({ getFieldValue }) => {
                const role = getFieldValue('role_type');
                if (role === 'ROOT_ORCHESTRATOR') {
                  return (
                    <Form.Item label="Reports To">
                      <Input disabled value="None (Top Level Root)" />
                    </Form.Item>
                  );
                }
                return (
                  <Form.Item
                    name="parent_id"
                    label="Supervisor (Reports To)"
                    help="Manager supervising this agent"
                  >
                    <Select placeholder="Select Manager" allowClear>
                      {eligibleManagers.map((m) => (
                        <Select.Option key={m.id} value={m.id}>
                          ⭐ {m.name} ({m.role_type})
                        </Select.Option>
                      ))}
                    </Select>
                  </Form.Item>
                );
              }}
            </Form.Item>
          </div>

          <Form.Item
            noStyle
            shouldUpdate={(prev, curr) => prev.role_type !== curr.role_type}
          >
            {({ getFieldValue }) => {
              const role = getFieldValue('role_type');
              if (role === 'MANAGER' || role === 'ROOT_ORCHESTRATOR') {
                return (
                  <Form.Item
                    name="max_concurrent_children"
                    label="Max Concurrent Subtasks"
                    help="Limit on parallel delegated tasks this manager can run simultaneously"
                  >
                    <InputNumber min={1} max={20} style={{ width: '100%' }} />
                  </Form.Item>
                );
              }
              return null;
            }}
          </Form.Item>

          <Form.Item name="description" label="Short Role Description">
            <Input placeholder="Coordinates frontend implementation and design system compliance" />
          </Form.Item>

          <Form.Item
            name="system_prompt"
            label="System Instructions (Prompt)"
            rules={[{ required: true, message: 'System prompt is required' }]}
          >
            <Input.TextArea
              rows={4}
              placeholder="You are an autonomous AI Agent. Execute tasks with precision..."
            />
          </Form.Item>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
            <Form.Item name="model" label="AI Model">
              <Select>
                {availableModels.length > 0 ? (
                  availableModels.map((m) => (
                    <Select.Option key={m.id} value={m.id}>
                      {m.name} ({m.provider})
                    </Select.Option>
                  ))
                ) : (
                  <Select.Option value="default">Default Claude</Select.Option>
                )}
              </Select>
            </Form.Item>

            <Form.Item
              name="skills"
              label="Equipped Skills"
              help="Select skills from your local skills repository to equip this agent"
            >
              <Select
                mode="multiple"
                allowClear
                showSearch
                placeholder="Search and equip skills (e.g. api-design, systematic-debugger)"
                options={availableSkills}
                filterOption={(input, option) => {
                  const labelStr = typeof option?.label === 'string' ? option.label : String(option?.value || '');
                  return (
                    labelStr.toLowerCase().includes(input.toLowerCase()) ||
                    String(option?.value || '').toLowerCase().includes(input.toLowerCase()) ||
                    String(option?.title || '').toLowerCase().includes(input.toLowerCase())
                  );
                }}
              />
            </Form.Item>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
            <Form.Item name="repo_path" label="Local Repository Path">
              <Input placeholder="c:\projects\my-repo" />
            </Form.Item>
            <Form.Item name="github_url" label="GitHub URL">
              <Input placeholder="https://github.com/org/repo" />
            </Form.Item>
          </div>

          {/* Character / Avatar Selector */}
          <Form.Item name="avatar" label="Pixel Art Office Avatar">
            <CharacterSelector />
          </Form.Item>
        </Form>
      </Modal>

      {/* Agent Interactive Mini-Chat Drawer */}
      <AgentMiniChatDrawer
        agent={chatAgent}
        visible={chatVisible}
        onClose={() => setChatVisible(false)}
        onTaskDispatched={fetchAgents}
      />
    </div>
  );
};

export default AgentsPage;
