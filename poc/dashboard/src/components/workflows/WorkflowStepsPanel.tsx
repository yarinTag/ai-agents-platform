import { PrPermissionSummary } from './PrPermissionSummary';
import { useWorkflowChatText } from '../../i18n/workflowChat';
import { Form, Input, Button, Select, Checkbox, Tag, Row, Col, Card, Space } from 'antd';
import { PlusOutlined, DeleteOutlined, FileTextOutlined, GithubOutlined, FolderOpenOutlined, GlobalOutlined, LinkOutlined } from '@ant-design/icons';


import { useWorkflowBuilder } from './useWorkflowBuilder';
import { WorkflowRepositoryFields } from './WorkflowRepositoryFields';

export function WorkflowStepsPanel({ model }: { model: ReturnType<typeof useWorkflowBuilder> }) {
  const {
    workflowName, setWorkflowName, description, setDescription, cronExpression,
    setCronExpression, webhookEnabled, channelProvider, setChannelProvider, channelId,
    setChannelId, triggerEnabled, setTriggerEnabled, notifyMode, setNotifyMode,
    agentOptions, getChannelLabel, telegramChannels, slackChannels, allowedMcps, workflowSkills, catalogSkills,
    setCreateSkillModalOpen, steps, syncToYaml, handleAddStep, handleUpdateStep,
    handleDeleteStep, handleAttachExistingSkill, handleRemoveSkill,
  } = model;
  const text = useWorkflowChatText();
  return (
<div style={{ maxHeight: '480px', overflowY: 'auto', paddingRight: '4px' }}>
                {/* Basic Meta */}
                <Row gutter={12} style={{ marginBottom: '12px' }}>
                  <Col span={14}>
                    <Form.Item label={<span style={{ color: '#f0f6fc' }}>Workflow Name</span>} style={{ marginBottom: '8px' }}>
                      <Input
                        value={workflowName}
                        onChange={(e) => {
                          setWorkflowName(e.target.value);
                          syncToYaml(e.target.value);
                        }}
                        style={{ background: '#161b22', borderColor: '#30363d', color: '#f0f6fc' }}
                      />
                    </Form.Item>
                  </Col>
                  <Col span={10}>
                    <Form.Item label={<span style={{ color: '#f0f6fc' }}>Cron Schedule (Optional)</span>} style={{ marginBottom: '8px' }}>
                      <Input
                        placeholder="e.g. 0 9 * * * (Every day 9 AM)"
                        value={cronExpression}
                        onChange={(e) => {
                          setCronExpression(e.target.value);
                          syncToYaml(workflowName, description, steps, e.target.value);
                        }}
                        style={{ background: '#161b22', borderColor: '#30363d', color: '#f0f6fc' }}
                      />
                    </Form.Item>
                  </Col>
                </Row>

                <Form.Item label={<span style={{ color: '#f0f6fc' }}>Description</span>} style={{ marginBottom: '12px' }}>
                  <Input.TextArea
                    rows={2}
                    value={description}
                    onChange={(e) => {
                      setDescription(e.target.value);
                      syncToYaml(workflowName, e.target.value);
                    }}
                    style={{ background: '#161b22', borderColor: '#30363d', color: '#f0f6fc' }}
                  />
                </Form.Item>

                {/* Channel Binding Section */}
                <Card
                  size="small"
                  style={{ background: '#161b22', borderColor: '#30363d', marginBottom: '16px' }}
                  title={
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <LinkOutlined style={{ color: '#10b981' }} />
                      <span style={{ color: '#f0f6fc', fontWeight: 700, fontSize: '13px' }}>
                        Channel Binding (Link Workflow to Configured Channel)
                      </span>
                    </div>
                  }
                >
                  <Row gutter={16} align="middle">
                    <Col span={6}>
                      <span style={{ fontSize: '12px', color: '#8b949e', display: 'block', marginBottom: '4px' }}>
                        Channel Provider:
                      </span>
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
                        style={{ width: '100%' }}
                        options={[
                          { label: 'Telegram', value: 'telegram' },
                          { label: 'Slack', value: 'slack' },
                          { label: 'None', value: '' },
                        ]}
                      />
                    </Col>
                    <Col span={7}>
                      <span style={{ fontSize: '12px', color: '#8b949e', display: 'block', marginBottom: '4px' }}>
                        Target Channel:
                      </span>
                      <Select
                        size="small"
                        showSearch
                        allowClear
                        value={channelId || undefined}
                        disabled={!channelProvider}
                        placeholder={channelProvider ? 'Select configured channel' : 'Select provider first'}
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
                        style={{ width: '100%' }}
                        options={(channelProvider === 'telegram'
                          ? telegramChannels
                          : channelProvider === 'slack'
                          ? slackChannels
                          : []
                        ).map((ch) => ({ label: getChannelLabel(channelProvider, ch), value: ch }))}
                      />
                    </Col>
                    <Col span={6}>
                      <span style={{ fontSize: '12px', color: '#8b949e', display: 'block', marginBottom: '4px' }}>
                        Notification Mode:
                      </span>
                      <Select
                        size="small"
                        value={['ON_COMPLETE', 'ON_FAILURE', 'ALWAYS'].includes(notifyMode) ? 'COMPLETION_ONLY' : notifyMode}
                        onChange={(val) => {
                          setNotifyMode(val);
                          syncToYaml(
                            workflowName,
                            description,
                            steps,
                            cronExpression,
                            webhookEnabled,
                            channelProvider,
                            channelId,
                            triggerEnabled,
                            val,
                            allowedMcps,
                            workflowSkills
                          );
                        }}
                        style={{ width: '100%' }}
                        options={[
                          { label: text.notifyEachStep, value: 'EACH_STEP' },
                          { label: text.notifyStartComplete, value: 'START_AND_COMPLETE' },
                          { label: text.notifyCompletion, value: 'COMPLETION_ONLY' },
                          { label: text.notifyNone, value: 'NONE' },
                        ]}
                      />
                    </Col>
                    <Col span={5}>
                      <div style={{ paddingTop: '18px' }}>
                        <Checkbox
                          checked={triggerEnabled}
                          onChange={(e) => {
                            const val = e.target.checked;
                            setTriggerEnabled(val);
                            syncToYaml(
                              workflowName,
                              description,
                              steps,
                              cronExpression,
                              webhookEnabled,
                              channelProvider,
                              channelId,
                              val,
                              notifyMode,
                              allowedMcps,
                              workflowSkills
                            );
                          }}
                          style={{ color: '#f0f6fc', fontSize: '12px' }}
                        >
                          Trigger Enabled
                        </Checkbox>
                      </div>
                    </Col>
                  </Row>
                </Card>

                {/* Skills Management Section */}
                <Card
                  size="small"
                  style={{ background: '#161b22', borderColor: '#30363d', marginBottom: '16px' }}
                  title={
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <FileTextOutlined style={{ color: '#f59e0b' }} />
                        <span style={{ color: '#f0f6fc', fontWeight: 700, fontSize: '13px' }}>
                          {text.workflowSkills} ({workflowSkills.length})
                        </span>
                      </div>
                      <Space>
                        <Select
                          size="small"
                          placeholder="+ Attach Platform Skill"
                          style={{ width: 180 }}
                          onChange={handleAttachExistingSkill}
                          value={undefined}
                          options={catalogSkills.map((s) => ({
                            label: `${s.name} (${s.source || 'builtin'})`,
                            value: s.id,
                          }))}
                        />
                        <Button
                          size="small"
                          type="primary"
                          icon={<PlusOutlined />}
                          onClick={() => setCreateSkillModalOpen(true)}
                          style={{ background: '#f59e0b', borderColor: '#d97706', color: '#000', fontWeight: 700 }}
                        >
                          + Create New Skill
                        </Button>
                      </Space>
                    </div>
                  }
                >
                  <div style={{ color: '#8b949e', marginBottom: 12 }}>{text.skillInheritance}</div>
                  {workflowSkills.length === 0 ? (
                    <div style={{ color: '#8b949e', fontSize: '12px', textAlign: 'center', padding: '12px 0' }}>
                      No skills attached yet. Attach an existing skill or create a new one with a Git/Local repo location.
                    </div>
                  ) : (
                    <Row gutter={[8, 8]}>
                      {workflowSkills.map((sk) => (
                        <Col span={12} key={sk.id}>
                          <div
                            style={{
                              background: '#0d1117',
                              border: '1px solid #30363d',
                              borderRadius: '8px',
                              padding: '8px 12px',
                              display: 'flex',
                              justifyContent: 'space-between',
                              alignItems: 'center',
                            }}
                          >
                            <div>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                                <span style={{ fontWeight: 700, color: '#f0f6fc', fontSize: '12px' }}>{sk.name}</span>
                                <Tag
                                  color={sk.source === 'git' ? 'purple' : sk.source === 'local' ? 'blue' : 'gold'}
                                  style={{ fontSize: '10px', margin: 0 }}
                                >
                                  {sk.source === 'git' ? <GithubOutlined /> : sk.source === 'local' ? <FolderOpenOutlined /> : <GlobalOutlined />}{' '}
                                  {sk.source.toUpperCase()}
                                </Tag>
                              </div>
                              {sk.location && (
                                <div style={{ fontSize: '10px', color: '#8b949e', fontFamily: 'monospace', marginTop: '2px' }}>
                                  Location: {sk.location}
                                </div>
                              )}
                            </div>
                            <Button
                              size="small"
                              type="text"
                              danger
                              icon={<DeleteOutlined />}
                              onClick={() => handleRemoveSkill(sk.id)}
                            />
                          </div>
                        </Col>
                      ))}
                    </Row>
                  )}
                </Card>

                {/* Steps Section */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                  <span style={{ fontSize: '13px', fontWeight: 700, color: '#38bdf8' }}>
                    DAG Execution Steps ({steps.length}):
                  </span>
                  <Button
                    size="small"
                    type="dashed"
                    icon={<PlusOutlined />}
                    onClick={handleAddStep}
                    style={{ color: '#38bdf8', borderColor: '#0284c7', background: 'transparent' }}
                  >
                    Add Step
                  </Button>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginBottom: '16px' }}>
                  {steps.map((st, idx) => (
                    <Card
                      key={st.key || idx}
                      size="small"
                      style={{ background: '#161b22', borderColor: '#30363d' }}
                      title={
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <Tag color="cyan">#{idx + 1}</Tag>
                          <span style={{ color: '#f0f6fc', fontWeight: 600 }}>{st.name || st.key}</span>
                        </div>
                      }
                      extra={
                        <Button
                          size="small"
                          danger
                          icon={<DeleteOutlined />}
                          onClick={() => handleDeleteStep(idx)}
                        />
                      }
                    >
                      <Row gutter={8} style={{ marginBottom: '8px' }}>
                        <Col span={8}>
                          <span style={{ fontSize: '11px', color: '#8b949e' }}>Step Key:</span>
                          <Input
                            size="small"
                            value={st.key}
                            onChange={(e) => handleUpdateStep(idx, { key: e.target.value })}
                            style={{ background: '#0d1117', borderColor: '#30363d', color: '#f0f6fc' }}
                          />
                        </Col>
                        <Col span={8}>
                          <span style={{ fontSize: '11px', color: '#8b949e' }}>Step Name:</span>
                          <Input
                            size="small"
                            value={st.name}
                            onChange={(e) => handleUpdateStep(idx, { name: e.target.value })}
                            style={{ background: '#0d1117', borderColor: '#30363d', color: '#f0f6fc' }}
                          />
                        </Col>
                        <Col span={8}>
                          <span style={{ fontSize: '11px', color: '#8b949e' }}>Assigned Agent:</span>
                          <Select
                            size="small"
                            style={{ width: '100%' }}
                            value={st.agent_id}
                            onChange={(val) => handleUpdateStep(idx, { agent_id: val })}
                            options={agentOptions.map(option => option.value === '__workflow_runner__' ? { ...option, label: text.plannedRunner } : option)}
                          />
                        </Col>
                      </Row>

                      <PrPermissionSummary step={st} />
                      {/* MCP and Skill assignment per step */}
                      <WorkflowRepositoryFields step={st} catalog={model.workspaceCatalog}
                        error={model.workspaceCatalogError} loading={model.resourcesLoading}
                        onChange={changes => handleUpdateStep(idx, changes)} />
                      <Row gutter={8} style={{ marginBottom: '8px' }}>
                        <Col span={12}>
                          <span style={{ fontSize: '11px', color: '#8b949e' }}>Step MCP Connectors:</span>
                          <Select
                            mode="multiple"
                            disabled={Boolean(st.params?.workspace)}
                            size="small"
                            style={{ width: '100%' }}
                            value={st.mcp_servers || []}
                            onChange={(val) => handleUpdateStep(idx, { mcp_servers: val })}
                            options={allowedMcps.map((m) => ({ label: m.toUpperCase(), value: m }))}
                            placeholder="Select step MCPs..."
                          />
                        </Col>

                      </Row>

                      <div style={{ marginBottom: '8px' }}>
                        <span style={{ fontSize: '11px', color: '#8b949e' }}>Prompt Template (with interpolation):</span>
                        <Input.TextArea
                          rows={2}
                          size="small"
                          value={st.prompt_template}
                          onChange={(e) => handleUpdateStep(idx, { prompt_template: e.target.value })}
                          style={{ background: '#0d1117', borderColor: '#30363d', color: '#f0f6fc' }}
                        />
                      </div>

                      <Row gutter={8}>
                        <Col span={16}>
                          <span style={{ fontSize: '11px', color: '#8b949e' }}>Depends On (DAG prior steps):</span>
                          <Select
                            mode="multiple"
                            size="small"
                            style={{ width: '100%' }}
                            value={st.depends_on}
                            onChange={(val) => handleUpdateStep(idx, { depends_on: val })}
                            options={steps.filter((_, i) => i !== idx).map((s) => ({ label: s.key, value: s.key }))}
                            placeholder="Select parent steps..."
                          />
                        </Col>
                        <Col span={8}>
                          <span style={{ fontSize: '11px', color: '#8b949e' }}>Timeout (Seconds):</span>
                          <Input
                            size="small"
                            type="number"
                            value={st.timeout_seconds || 300}
                            onChange={(e) => handleUpdateStep(idx, { timeout_seconds: parseInt(e.target.value) || 300 })}
                            style={{ background: '#0d1117', borderColor: '#30363d', color: '#f0f6fc' }}
                          />
                        </Col>
                      </Row>
                    </Card>
                  ))}
                </div>
              </div>
  );
}
