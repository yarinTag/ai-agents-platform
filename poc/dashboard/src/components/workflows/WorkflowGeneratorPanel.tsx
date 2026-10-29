import { Input, Button, Select, Checkbox, Tag, Row, Col, Card, Divider, message } from 'antd';
import { ThunderboltOutlined, CodeOutlined, SendOutlined, RocketOutlined, SafetyCertificateOutlined, DashboardOutlined, ToolOutlined } from '@ant-design/icons';

import { useWorkflowBuilder } from './useWorkflowBuilder';

export function WorkflowGeneratorPanel({ model }: { model: ReturnType<typeof useWorkflowBuilder> }) {
  const {
    generating, promptText, setPromptText, workflowName, description,
    cronExpression, webhookEnabled, targetRepo, setTargetRepo, channelProvider,
    setChannelProvider, channelId, setChannelId, triggerEnabled, notifyMode,
    telegramChannels, slackChannels, githubRepos, installedMcps, allowedMcps,
    setAllowedMcps, workflowSkills, steps, syncToYaml, handleGenerateTemplate,
  } = model;
  return (
<div style={{ padding: '8px 0' }}>
                <div style={{ color: '#8b949e', fontSize: '13px', marginBottom: '14px' }}>
                  Generate an autonomous workflow playbook restricted strictly to your configured MCPs and connected to your Telegram/Slack channel:
                </div>

                {/* MCP Connector Restriction Box */}
                <Card
                  size="small"
                  style={{ background: '#161b22', borderColor: '#30363d', marginBottom: '16px' }}
                  title={
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <ToolOutlined style={{ color: '#a855f7' }} />
                      <span style={{ color: '#f0f6fc', fontWeight: 700, fontSize: '13px' }}>
                        Configured MCP Scope (Authorized MCPs for this workflow):
                      </span>
                    </div>
                  }
                >
                  <div style={{ fontSize: '12px', color: '#8b949e', marginBottom: '8px' }}>
                    The workflow prompt generator and DAG executor will be restricted to work ONLY with the selected active MCPs:
                  </div>
                  <Checkbox.Group
                    value={allowedMcps}
                    onChange={(vals) => {
                      const list = vals as string[];
                      setAllowedMcps(list);
                      syncToYaml(workflowName, description, steps, cronExpression, webhookEnabled, channelProvider, channelId, triggerEnabled, notifyMode, list);
                    }}
                    style={{ width: '100%' }}
                  >
                    <Row gutter={[12, 8]}>
                      {installedMcps.map((mcp) => (
                        <Col span={6} key={mcp}>
                          <Checkbox value={mcp} style={{ color: '#f0f6fc' }}>
                            <Tag color={mcp === 'github' ? 'purple' : mcp === 'telegram' ? 'blue' : mcp === 'trello' ? 'cyan' : 'gold'}>
                              {mcp.toUpperCase()}
                            </Tag>
                          </Checkbox>
                        </Col>
                      ))}
                    </Row>
                  </Checkbox.Group>
                </Card>

                {/* Templates Grid */}
                <div style={{ marginBottom: '16px' }}>
                  <div style={{ fontSize: '12px', fontWeight: 700, color: '#f0f6fc', marginBottom: '8px' }}>
                    READY-TO-USE PRESETS (One-Click Templates):
                  </div>
                  <Row gutter={[12, 12]}>
                    <Col span={12}>
                      <Card
                        hoverable
                        size="small"
                        onClick={() => handleGenerateTemplate('telegram_github_daily_report')}
                        style={{ background: '#161b22', borderColor: '#3b82f6', cursor: 'pointer', borderLeft: '4px solid #3b82f6' }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                          <SendOutlined style={{ color: '#38bdf8' }} />
                          <span style={{ fontWeight: 700, color: '#f0f6fc', fontSize: '13px' }}>
                            Telegram Trigger ➔ GitHub Daily Repo Changes
                          </span>
                        </div>
                        <div style={{ color: '#8b949e', fontSize: '11px' }}>
                          Listen to Telegram message ➡️ Fetch GitHub repo diff & commits ➡️ Synthesize daily digest ➡️ Dispatch back to Telegram
                        </div>
                      </Card>
                    </Col>
                    <Col span={12}>
                      <Card
                        hoverable
                        size="small"
                        onClick={() => handleGenerateTemplate('github_pr_review')}
                        style={{ background: '#161b22', borderColor: '#30363d', cursor: 'pointer' }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                          <RocketOutlined style={{ color: '#38bdf8' }} />
                          <span style={{ fontWeight: 700, color: '#f0f6fc', fontSize: '13px' }}>
                            GitHub PR Review & Autonomous Gate
                          </span>
                        </div>
                        <div style={{ color: '#8b949e', fontSize: '11px' }}>
                          Architect inspection ➡️ QA test runner ➡️ Security audit ➡️ Dispatch to Telegram
                        </div>
                      </Card>
                    </Col>
                    <Col span={12}>
                      <Card
                        hoverable
                        size="small"
                        onClick={() => handleGenerateTemplate('incident_triage')}
                        style={{ background: '#161b22', borderColor: '#30363d', cursor: 'pointer' }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                          <SafetyCertificateOutlined style={{ color: '#f59e0b' }} />
                          <span style={{ fontWeight: 700, color: '#f0f6fc', fontSize: '13px' }}>
                            Incident Triage & Rapid Hotfix
                          </span>
                        </div>
                        <div style={{ color: '#8b949e', fontSize: '11px' }}>
                          Crash dump triage ➡️ Backend patch draft ➡️ Release security check ➡️ On-call alert
                        </div>
                      </Card>
                    </Col>
                    <Col span={12}>
                      <Card
                        hoverable
                        size="small"
                        onClick={() => handleGenerateTemplate('daily_health_check')}
                        style={{ background: '#161b22', borderColor: '#30363d', cursor: 'pointer' }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                          <DashboardOutlined style={{ color: '#10b981' }} />
                          <span style={{ fontWeight: 700, color: '#f0f6fc', fontSize: '13px' }}>
                            Daily Health Check & Metrics Digest
                          </span>
                        </div>
                        <div style={{ color: '#8b949e', fontSize: '11px' }}>
                          Benchmark probing ➡️ Platform diagnostics ➡️ Executive digest on 9:00 AM Cron
                        </div>
                      </Card>
                    </Col>
                    <Col span={12}>
                      <Card
                        hoverable
                        size="small"
                        onClick={() => handleGenerateTemplate('branch_diff_inspector')}
                        style={{ background: '#161b22', borderColor: '#8b5cf6', cursor: 'pointer', borderLeft: '4px solid #8b5cf6' }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                          <CodeOutlined style={{ color: '#a78bfa' }} />
                          <span style={{ fontWeight: 700, color: '#f0f6fc', fontSize: '13px' }}>
                            Git Branch & Code Changes Inspector
                          </span>
                        </div>
                        <div style={{ color: '#8b949e', fontSize: '11px' }}>
                          Check active branch & git status ➡️ Analyze diff & commits ➡️ Markdown executive report
                        </div>
                      </Card>
                    </Col>
                  </Row>
                </div>

                <Divider style={{ borderColor: '#21262d', margin: '14px 0' }} />

                {/* Free Text Generator */}
                <div>
                  <div style={{ fontSize: '12px', fontWeight: 700, color: '#f0f6fc', marginBottom: '6px' }}>
                    OR DESCRIBE YOUR CUSTOM WORKFLOW (Natural language description):
                  </div>
                  <Input.TextArea
                    rows={3}
                    placeholder="e.g. Upon receiving a message in a Telegram channel, run a workflow that inspects recent changes in the GitHub repo yarinTag/ai-agents-platform and posts an executive summary back to the channel..."
                    value={promptText}
                    onChange={(e) => setPromptText(e.target.value)}
                    style={{ background: '#161b22', borderColor: '#30363d', color: '#f0f6fc', marginBottom: '12px' }}
                  />

                  <Row gutter={12} style={{ marginBottom: '12px' }}>
                    <Col span={8}>
                      <span style={{ fontSize: '12px', color: '#8b949e' }}>Target Channel:</span>
                      <Select
                        size="small"
                        value={channelProvider}
                        onChange={(val) => {
                          const newProv = val;
                          let newChan = '';
                          if (newProv === 'telegram') {
                            newChan = telegramChannels[0] || '';
                          } else if (newProv === 'slack') {
                            newChan = slackChannels[0] || '';
                          }
                          setChannelProvider(newProv);
                          setChannelId(newChan);
                          syncToYaml(
                            workflowName,
                            description,
                            steps,
                            cronExpression,
                            webhookEnabled,
                            newProv,
                            newChan,
                            triggerEnabled,
                            notifyMode,
                            allowedMcps,
                            workflowSkills
                          );
                        }}
                        style={{ width: '100%', marginTop: '4px' }}
                        options={[
                          { label: 'Telegram Bot', value: 'telegram' },
                          { label: 'Slack', value: 'slack' },
                          { label: 'None', value: '' },
                        ]}
                      />
                    </Col>
                    <Col span={8}>
                      <span style={{ fontSize: '12px', color: '#8b949e' }}>Channel ID / Chat:</span>
                      <Select
                        size="small"
                        showSearch
                        allowClear
                        value={channelId || undefined}
                        disabled={!channelProvider}
                        placeholder={channelProvider ? 'Select or search channel' : 'Select provider first'}
                        onChange={(val) => {
                          const newChan = val || '';
                          setChannelId(newChan);
                          syncToYaml(
                            workflowName,
                            description,
                            steps,
                            cronExpression,
                            webhookEnabled,
                            channelProvider,
                            newChan,
                            triggerEnabled,
                            notifyMode,
                            allowedMcps,
                            workflowSkills
                          );
                        }}
                        style={{ width: '100%', marginTop: '4px' }}
                        options={(channelProvider === 'telegram'
                          ? telegramChannels
                          : channelProvider === 'slack'
                          ? slackChannels
                          : []
                        ).map((ch) => ({ label: ch, value: ch }))}
                      />
                    </Col>
                    <Col span={8}>
                      <span style={{ fontSize: '12px', color: '#8b949e' }}>Target Repo (owner/repo):</span>
                      <Select
                        size="small"
                        showSearch
                        value={targetRepo}
                        onChange={(val) => setTargetRepo(val)}
                        placeholder="Select target repo"
                        style={{ width: '100%', marginTop: '4px' }}
                        options={githubRepos.map((r) => ({ label: r, value: r }))}
                      />
                    </Col>
                  </Row>

                  <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                    <Button
                      type="primary"
                      icon={<ThunderboltOutlined />}
                      loading={generating}
                      onClick={() => handleGenerateTemplate()}
                      style={{ background: '#2563eb', borderColor: '#2563eb', fontWeight: 700 }}
                    >
                      Generate Workflow, Canvas DAG & YAML
                    </Button>
                  </div>
                </div>
              </div>
  );
}
