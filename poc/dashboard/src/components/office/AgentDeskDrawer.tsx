import React, { useState } from 'react';
import {
  Drawer,
  Tag,
  Button,
  Input,
  Select,
  Form,
  Tabs,
  Typography,
  Divider,
  message,
} from 'antd';
import {
  PlayCircleOutlined,
  FolderOpenOutlined,
  GithubOutlined,
  CodeOutlined,
  ThunderboltOutlined,
  SyncOutlined,
  AppstoreOutlined,
  CopyOutlined,
} from '@ant-design/icons';
import { Agent } from '../../types/agent';
import { Task } from '../../types/task';
import { createTask, updateAgent } from '../../services/api';
import { AI_MODELS } from '../../constants/models';

const { Paragraph } = Typography;

interface AgentDeskDrawerProps {
  agent: Agent | null;
  tasks: Task[];
  visible: boolean;
  onClose: () => void;
  onTaskCreated: () => void;
}

export const AgentDeskDrawer: React.FC<AgentDeskDrawerProps> = ({
  agent,
  tasks,
  visible,
  onClose,
  onTaskCreated,
}) => {
  const [form] = Form.useForm();
  const [repoForm] = Form.useForm();
  const [running, setRunning] = useState(false);
  const [savingRepo, setSavingRepo] = useState(false);

  if (!agent) return null;

  const agentTasks = tasks.filter((t) => String(t.agent_id) === String(agent.id));
  const activeTask = agentTasks.find((t) => t.status === 'running' || t.status === 'queued');

  const handleLaunchTask = async () => {
    try {
      const values = await form.validateFields();
      setRunning(true);
      let parsedInput: Record<string, any> = {};
      try {
        parsedInput = values.input_data ? JSON.parse(values.input_data) : { prompt: values.prompt };
      } catch {
        parsedInput = { prompt: values.prompt || values.input_data };
      }

      await createTask({
        agent_id: agent.id,
        project_id: null,
        skill_id: null,
        input_data: parsedInput,
      });

      message.success(`Task dispatched to ${agent.name}!`);
      form.resetFields();
      onTaskCreated();
    } catch (err) {
      message.error('Failed to launch task');
      console.error(err);
    } finally {
      setRunning(false);
    }
  };

  const handleSaveRepo = async () => {
    try {
      const values = await repoForm.validateFields();
      setSavingRepo(true);
      await updateAgent(agent.id, {
        repo_path: values.repo_path,
        github_url: values.github_url,
        model: values.model,
        department: values.department,
      });
      message.success('Workstation configuration updated!');
      agent.repo_path = values.repo_path;
      agent.github_url = values.github_url;
      agent.model = values.model;
      agent.department = values.department;
      onTaskCreated();
    } catch (err) {
      message.error('Failed to update workstation configuration');
      console.error(err);
    } finally {
      setSavingRepo(false);
    }
  };

  return (
    <Drawer
      title={
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span style={{ fontSize: '22px' }}>💻</span>
            <div>
              <div style={{ fontWeight: 600, color: '#f3f4f6', fontSize: '16px' }}>{agent.name} Workstation</div>
              <div style={{ fontSize: '11px', color: '#9ca3af' }}>{agent.department || 'Engineering'} Desk</div>
            </div>
          </div>
          <Tag color={activeTask ? 'green' : 'blue'}>
            {activeTask ? 'EXECUTING TASK' : 'READY & IDLE'}
          </Tag>
        </div>
      }
      placement="right"
      width={560}
      onClose={onClose}
      open={visible}
      styles={{
        header: { background: '#0d1117', borderBottom: '1px solid #30363d' },
        body: { background: '#0d1117', color: '#e6edf3', padding: '16px 20px' },
      }}
    >
      <Tabs
        defaultActiveKey="run"
        items={[
          {
            key: 'run',
            label: (
              <span>
                <ThunderboltOutlined /> Command Console
              </span>
            ),
            children: (
              <div>
                {/* Active Task Banner if running */}
                {activeTask && (
                  <div
                    style={{
                      background: 'rgba(82, 196, 26, 0.1)',
                      border: '1px solid #52c41a',
                      borderRadius: '8px',
                      padding: '12px',
                      marginBottom: '16px',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 600, color: '#52c41a' }}>
                      <SyncOutlined spin /> Currently Running Task #{activeTask.id}
                    </div>
                    <div style={{ fontSize: '12px', color: '#d1d5db', marginTop: '6px' }}>
                      {JSON.stringify(activeTask.input_data)}
                    </div>
                  </div>
                )}

                {/* Quick Task Dispatch Form */}
                <div style={{ background: '#161b22', padding: '16px', borderRadius: '10px', border: '1px solid #30363d', marginBottom: '20px' }}>
                  <h4 style={{ margin: '0 0 12px 0', color: '#f3f4f6' }}>Dispatch Task to Agent</h4>
                  <Form form={form} layout="vertical">
                    <Form.Item
                      name="prompt"
                      label={<span style={{ color: '#9ca3af' }}>Instruction / Prompt</span>}
                      rules={[{ required: true, message: 'Please enter a task prompt' }]}
                    >
                      <Input.TextArea
                        rows={3}
                        placeholder="e.g., Scan repository for bugs, run test suite, or generate API documentation"
                        style={{ background: '#0d1117', color: '#fff', borderColor: '#30363d' }}
                      />
                    </Form.Item>

                    <Form.Item
                      name="input_data"
                      label={<span style={{ color: '#9ca3af' }}>Advanced JSON Payload (Optional)</span>}
                    >
                      <Input.TextArea
                        rows={2}
                        placeholder='{"mode": "thorough", "context": "api"}'
                        style={{ background: '#0d1117', color: '#fff', borderColor: '#30363d', fontFamily: 'monospace' }}
                      />
                    </Form.Item>

                    <Button
                      type="primary"
                      icon={<PlayCircleOutlined />}
                      loading={running}
                      onClick={handleLaunchTask}
                      block
                      style={{ background: '#238636', borderColor: '#238636' }}
                    >
                      Execute Task on Desk
                    </Button>
                  </Form>
                </div>

                {/* Live Output & History */}
                <div>
                  <h4 style={{ color: '#f3f4f6', margin: '0 0 10px 0', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <CodeOutlined /> Agent Task History & Output
                  </h4>
                  {agentTasks.length === 0 ? (
                    <div style={{ color: '#6e7681', textAlign: 'center', padding: '24px 0' }}>
                      No tasks dispatched to this agent yet.
                    </div>
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                      {agentTasks.slice(0, 5).map((task) => (
                        <div
                          key={task.id}
                          style={{
                            background: '#161b22',
                            padding: '10px 12px',
                            borderRadius: '8px',
                            border: '1px solid #30363d',
                          }}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
                            <span style={{ fontSize: '12px', fontWeight: 600, color: '#f3f4f6' }}>
                              Task #{task.id}
                            </span>
                            <Tag color={task.status === 'completed' ? 'green' : task.status === 'running' ? 'blue' : 'default'}>
                              {task.status.toUpperCase()}
                            </Tag>
                          </div>
                          <div style={{ fontSize: '11px', color: '#8b949e', marginBottom: '4px' }}>
                            Input: {typeof task.input_data === 'string' ? task.input_data : JSON.stringify(task.input_data)}
                          </div>
                          {task.output_data && (
                            <div
                              style={{
                                background: '#0d1117',
                                padding: '6px 8px',
                                borderRadius: '4px',
                                fontSize: '11px',
                                fontFamily: 'monospace',
                                color: '#58a6ff',
                                maxHeight: '100px',
                                overflowY: 'auto',
                              }}
                            >
                              {typeof task.output_data === 'string' ? task.output_data : JSON.stringify(task.output_data, null, 2)}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ),
          },
          {
            key: 'repo',
            label: (
              <span>
                <FolderOpenOutlined /> Linked Repository
              </span>
            ),
            children: (
              <div>
                <Paragraph style={{ color: '#8b949e', fontSize: '13px' }}>
                  Connect this agent to a specific local directory or GitHub repository on your machine. The agent will execute tasks against this codebase.
                </Paragraph>

                <Form
                  form={repoForm}
                  layout="vertical"
                  initialValues={{
                    repo_path: agent.repo_path || 'C:\\Users\\taguo\\OneDrive\\Desktop\\Projects\\test',
                    github_url: agent.github_url || '',
                    model: agent.model || 'default',
                    department: agent.department || 'Engineering',
                  }}
                >
                  <Form.Item
                    name="model"
                    label={<span style={{ color: '#9ca3af' }}>AI Model (FCC Overridden)</span>}
                  >
                    <Select
                      showSearch
                      options={AI_MODELS}
                      optionFilterProp="label"
                      placeholder="Select Model (Default, Sonnet, Opus, Haiku, Fable)"
                    />
                  </Form.Item>

                  <Form.Item
                    name="department"
                    label={<span style={{ color: '#9ca3af' }}>Department Wing</span>}
                  >
                    <Select>
                      <Select.Option value="Executive HQ">Executive HQ (Center)</Select.Option>
                      <Select.Option value="Engineering">Engineering Wing</Select.Option>
                      <Select.Option value="Architecture">Architecture Wing</Select.Option>
                      <Select.Option value="QA & Testing">QA & Testing Wing</Select.Option>
                      <Select.Option value="Research & Ops">Research & Ops Wing</Select.Option>
                    </Select>
                  </Form.Item>

                  <Form.Item
                    name="repo_path"
                    label={<span style={{ color: '#9ca3af' }}>Local Repository Path (on PC)</span>}
                  >
                    <Input
                      prefix={<FolderOpenOutlined style={{ color: '#e3b341' }} />}
                      placeholder="e.g. C:\Users\taguo\OneDrive\Desktop\Projects\test"
                      style={{ background: '#161b22', color: '#fff', borderColor: '#30363d' }}
                    />
                  </Form.Item>

                  <Form.Item
                    name="github_url"
                    label={<span style={{ color: '#9ca3af' }}>GitHub Repository URL (Optional)</span>}
                  >
                    <Input
                      prefix={<GithubOutlined style={{ color: '#fff' }} />}
                      placeholder="https://github.com/org/repo"
                      style={{ background: '#161b22', color: '#fff', borderColor: '#30363d' }}
                    />
                  </Form.Item>

                  <Button
                    type="primary"
                    loading={savingRepo}
                    onClick={handleSaveRepo}
                    block
                    style={{ background: '#1f6feb', borderColor: '#1f6feb' }}
                  >
                    Save Workstation & Repo Configuration
                  </Button>
                </Form>

                <Divider style={{ borderColor: '#30363d' }} />

                {/* Quick Paths presets */}
                <div>
                  <span style={{ fontSize: '12px', color: '#8b949e' }}>Quick Select Available Projects:</span>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '8px' }}>
                    {[
                      'C:\\Users\\taguo\\OneDrive\\Desktop\\Projects\\test',
                      'C:\\Users\\taguo\\OneDrive\\Desktop\\Projects\\p-skills',
                      'C:\\Users\\taguo\\Desktop\\ai-agents-platform',
                    ].map((path) => (
                      <div
                        key={path}
                        onClick={() => {
                          repoForm.setFieldsValue({ repo_path: path });
                        }}
                        style={{
                          background: '#161b22',
                          padding: '8px 12px',
                          borderRadius: '6px',
                          border: '1px solid #30363d',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          fontSize: '12px',
                        }}
                      >
                        <span style={{ color: '#58a6ff' }}>{path}</span>
                        <CopyOutlined style={{ color: '#8b949e' }} />
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            ),
          },
          {
            key: 'skills',
            label: (
              <span>
                <AppstoreOutlined /> Equipped Skills
              </span>
            ),
            children: (
              <div>
                <Paragraph style={{ color: '#8b949e', fontSize: '13px' }}>
                  Skills equipped by this agent from the system plugins ecosystem:
                </Paragraph>

                {agent.skills && agent.skills.length > 0 ? (
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                    {agent.skills.map((skill) => (
                      <Tag
                        key={skill}
                        color="cyan"
                        style={{ padding: '4px 10px', fontSize: '12px', borderRadius: '12px' }}
                      >
                        ⚡ {skill}
                      </Tag>
                    ))}
                  </div>
                ) : (
                  <div style={{ color: '#6e7681', padding: '16px 0' }}>
                    No specific skills equipped. Using core capabilities.
                  </div>
                )}

                <Divider style={{ borderColor: '#30363d' }} />

                <div style={{ fontSize: '12px', color: '#8b949e' }}>
                  <strong>System Prompt:</strong>
                  <div
                    style={{
                      background: '#161b22',
                      padding: '10px',
                      borderRadius: '6px',
                      color: '#c9d1d9',
                      marginTop: '6px',
                      maxHeight: '180px',
                      overflowY: 'auto',
                      whiteSpace: 'pre-wrap',
                      fontFamily: 'monospace',
                    }}
                  >
                    {agent.system_prompt || 'Standard Agent Instructions'}
                  </div>
                </div>
              </div>
            ),
          },
        ]}
      />
    </Drawer>
  );
};
