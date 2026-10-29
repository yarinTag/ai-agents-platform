import type { AgentDeskDrawerProps } from './agentDeskTypes';
import React from 'react';
import { Drawer, Tag, Button, Input, Select, Form, Tabs, Typography, Divider } from 'antd';
import { PlayCircleOutlined, FolderOpenOutlined, GithubOutlined, CodeOutlined, ThunderboltOutlined, SyncOutlined, AppstoreOutlined, CopyOutlined } from '@ant-design/icons';

import { ModelSelector } from '../robotic';

const { Paragraph } = Typography;

import { useAgentDesk } from './useAgentDesk';

export const AgentDeskDrawer: React.FC<AgentDeskDrawerProps> = (props) => {
  const {
    agent, visible, onClose,
    departments, form, repoForm, running, savingRepo,
    availableSkills, departmentOptions, agentTasks, activeTask, handleLaunchTask,
    handleSaveRepo,
  } = useAgentDesk(props);
  if (!agent) return null;
  return (
    <Drawer
      title={
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span style={{ fontSize: '22px' }}>💻</span>
            <div>
              <div style={{ fontWeight: 600, color: '#f3f4f6', fontSize: '16px' }}>{agent.name} Workstation</div>
              <div style={{ fontSize: '11px', color: '#9ca3af' }}>{agent.department || 'Engineering'} Department</div>
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
                    repo_path: agent.repo_path || 'C:\\Users\\taguo\\Desktop\\ai-agents-platform',
                    github_url: agent.github_url || '',
                    model: agent.model || 'default',
                    department: agent.department || 'Engineering',
                  }}
                >
                  <Form.Item
                    name="model"
                    label={<span style={{ color: '#9ca3af' }}>AI Model (FCC Overridden)</span>}
                  >
                    <ModelSelector placeholder="Select Model (Default, Sonnet, Opus, Haiku, Fable)" />
                  </Form.Item>

                  <Form.Item
                    name="department_id"
                    label={<span style={{ color: '#9ca3af' }}>Department</span>}
                    help="Select department to govern budget and tool permissions"
                  >
                    <Select
                      showSearch
                      allowClear
                      placeholder="Select enterprise department"
                      options={departmentOptions}
                      onChange={(val) => {
                        const matched = departments.find((d) => d.id === val || d.name === val);
                        if (matched) {
                          repoForm.setFieldsValue({
                            department_id: matched.id,
                            department: matched.name,
                          });
                        } else if (val) {
                          repoForm.setFieldsValue({
                            department: val,
                          });
                        }
                      }}
                    />
                  </Form.Item>
                  <Form.Item name="department" hidden>
                    <Input />
                  </Form.Item>

                  <Form.Item
                    name="repo_path"
                    label={<span style={{ color: '#9ca3af' }}>Local Repository Path (on PC)</span>}
                  >
                    <Input
                      prefix={<FolderOpenOutlined style={{ color: '#e3b341' }} />}
                      placeholder="e.g. C:\Users\taguo\Desktop\ai-agents-platform"
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

                  <Form.Item
                    name="skills"
                    label={<span style={{ color: '#9ca3af' }}>Equipped Skills (from Skills Marketplace)</span>}
                    help="Select skills from your skills repo to equip on this desk"
                  >
                    <Select
                      mode="multiple"
                      allowClear
                      showSearch
                      placeholder="Search and equip skills (e.g., api-design)"
                      options={availableSkills}
                      filterOption={(input, option) => {
                        const labelStr = typeof option?.label === 'string' ? option.label : String(option?.value || '');
                        return (
                          labelStr.toLowerCase().includes(input.toLowerCase()) ||
                          String(option?.value || '').toLowerCase().includes(input.toLowerCase()) ||
                          String(option?.title || '').toLowerCase().includes(input.toLowerCase())
                        );
                      }}
                      style={{ width: '100%' }}
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
                      'C:\\Users\\taguo\\Desktop\\ai-agents-platform',
                      '.',
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
                <AppstoreOutlined /> Equipped Skills ({agent.skills?.length || 0})
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
