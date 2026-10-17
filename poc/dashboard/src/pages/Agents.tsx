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
  ThunderboltOutlined,
} from '@ant-design/icons';
import { Agent, AgentRole } from '../types/agent';
import { useAuth } from '../context/AuthContext';
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
import FolderPickerModal from '../components/common/FolderPickerModal';
import { ModelSelector } from '../components/robotic';

export const AgentsPage: React.FC = () => {
  const { departments, activeDepartmentId, organization } = useAuth();
  const [agents, setAgents] = useState<Agent[]>([]);
  const [availableSkills, setAvailableSkills] = useState<any[]>([]);
  const [availableModels, setAvailableModels] = useState<DiscoveredModel[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [visible, setVisible] = useState<boolean>(false);
  const [folderPickerVisible, setFolderPickerVisible] = useState<boolean>(false);
  const [form] = Form.useForm();
  const [editingKey, setEditingKey] = useState<string>('');
  const [activeTab, setActiveTab] = useState<string>('roster');
  const [chatAgent, setChatAgent] = useState<Agent | null>(null);
  const [chatVisible, setChatVisible] = useState<boolean>(false);
  const [customDepartments, setCustomDepartments] = useState<string[]>([]);
  const [deptSearchText, setDeptSearchText] = useState<string>('');
  const [newCustomDept, setNewCustomDept] = useState<string>('');

  const dynamicDepartments = React.useMemo(() => {
    const set = new Set<string>([...customDepartments]);
    agents.forEach((a) => {
      if (a.department?.trim()) set.add(a.department.trim());
    });
    const opts = Array.from(set).map((d) => ({ value: d, label: d }));

    const searchTrimmed = deptSearchText.trim();
    if (searchTrimmed && !set.has(searchTrimmed)) {
      opts.unshift({
        value: searchTrimmed,
        label: `➕ Create department "${searchTrimmed}"`,
      });
    }
    return opts;
  }, [agents, customDepartments, deptSearchText]);

  const departmentOptions = React.useMemo(() => {
    if (departments && departments.length > 0) {
      return departments.map((d) => ({
        value: d.id,
        label: `📁 ${d.name}`,
        name: d.name,
      }));
    }
    return dynamicDepartments;
  }, [departments, dynamicDepartments]);

  const handleAddCustomDept = (nameToAdd?: string) => {
    const val = (nameToAdd || newCustomDept).trim();
    if (!val) return;
    if (!customDepartments.includes(val)) {
      setCustomDepartments((prev) => [...prev, val]);
    }
    form.setFieldsValue({ department: val });
    setNewCustomDept('');
    setDeptSearchText('');
  };

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
    const activeDept = departments.find((d) => d.id === activeDepartmentId) || departments[0];
    const initialDeptId = activeDept?.id || null;
    const initialDeptName = activeDept?.name || customDepartments[0] || (agents[0]?.department) || 'Engineering';

    form.setFieldsValue({
      role_type: 'WORKER',
      department_id: initialDeptId,
      department: initialDeptName,
      organization_id: organization?.id || null,
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
      if (Array.isArray(values.department)) {
        values.department = values.department[0] || '';
      }
      if (typeof values.department === 'string') {
        values.department = values.department.trim();
      }

      // Link both department_id and department
      const selectedDeptId =
        values.department_id ||
        departments.find((d) => d.name === values.department)?.id ||
        activeDepartmentId;

      const matchedDept = departments.find(
        (d) => d.id === selectedDeptId || d.id === values.department || d.name === values.department
      );

      if (matchedDept) {
        values.department_id = matchedDept.id;
        values.department = matchedDept.name;
      } else if (selectedDeptId) {
        values.department_id = selectedDeptId;
      }

      if (organization?.id && !values.organization_id) {
        values.organization_id = organization.id;
      }

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

  const officeFloorAgents = React.useMemo(() => {
    return agents.filter(
      (a) =>
        a.role_type !== 'WORKFLOW_AUTOMATION' &&
        !(a as any).is_workflow_agent &&
        a.department !== 'Workflow Automations'
    );
  }, [agents]);

  const workflowAgents = React.useMemo(() => {
    return agents.filter(
      (a) =>
        a.role_type === 'WORKFLOW_AUTOMATION' ||
        Boolean((a as any).is_workflow_agent) ||
        a.department === 'Workflow Automations'
    );
  }, [agents]);

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
                <TeamOutlined /> 🏢 Office Floor Team ({officeFloorAgents.length})
              </span>
            ),
            children: (
              <Table
                dataSource={officeFloorAgents}
                columns={columns}
                rowKey="id"
                loading={loading}
                pagination={{ pageSize: 8 }}
                scroll={{ x: 1000 }}
                style={{ background: '#161b22', borderRadius: '12px' }}
              />
            ),
          },
          {
            key: 'workflows',
            label: (
              <span>
                <ThunderboltOutlined /> ⚡ Workflow Automations ({workflowAgents.length})
              </span>
            ),
            children: (
              <div>
                <div
                  style={{
                    background: 'linear-gradient(90deg, rgba(88, 28, 135, 0.25) 0%, rgba(30, 27, 75, 0.45) 100%)',
                    border: '1px solid #7c3aed',
                    borderRadius: '10px',
                    padding: '14px 18px',
                    marginBottom: '16px',
                    color: '#e9d5ff',
                    fontSize: '13px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '14px',
                  }}
                >
                  <span style={{ fontSize: '24px' }}>⚡</span>
                  <div>
                    <div style={{ fontWeight: 700, color: '#f3e8ff', fontSize: '14px', marginBottom: '2px' }}>
                      Decoupled Workflow Automation Agents
                    </div>
                    <div style={{ fontSize: '12px', color: '#c084fc', lineHeight: 1.5 }}>
                      These agents are automatically provisioned when workflows are created to maintain scheduled executions (cron) or listen to selected channel events (Telegram/Slack). They run in the cloud background and are <strong>completely detached from the 2D Pixel Office Canvas</strong>, keeping physical workstations reserved for human-collaborative team agents.
                    </div>
                  </div>
                </div>
                <Table
                  dataSource={workflowAgents}
                  columns={columns}
                  rowKey="id"
                  loading={loading}
                  pagination={{ pageSize: 8 }}
                  scroll={{ x: 1000 }}
                  style={{ background: '#161b22', borderRadius: '12px' }}
                />
              </div>
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

            <Form.Item
              name="department_id"
              label="Department"
              help="Assign agent to an enterprise department for budget and tool governance"
            >
              <Select
                showSearch
                allowClear
                placeholder="Select enterprise department"
                options={departmentOptions}
                onChange={(val) => {
                  const matched = departments.find((d) => d.id === val || d.name === val);
                  if (matched) {
                    form.setFieldsValue({
                      department_id: matched.id,
                      department: matched.name,
                    });
                  } else if (val) {
                    form.setFieldsValue({
                      department: val,
                    });
                  }
                }}
              />
            </Form.Item>
            <Form.Item name="department" hidden>
              <Input />
            </Form.Item>
            <Form.Item name="organization_id" hidden>
              <Input />
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
              <ModelSelector placeholder="Select AI Model..." />
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
              <Input
                placeholder="/path/to/my-repo"
                addonAfter={
                  <Button
                    type="link"
                    size="small"
                    icon={<FolderOpenOutlined />}
                    onClick={() => setFolderPickerVisible(true)}
                    style={{ padding: '0 6px', color: '#38bdf8' }}
                  >
                    Browse...
                  </Button>
                }
              />
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

      <FolderPickerModal
        open={folderPickerVisible}
        onClose={() => setFolderPickerVisible(false)}
        onSelect={(path) => form.setFieldsValue({ repo_path: path })}
        title="📁 Select Agent Local Repository Folder"
      />

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
