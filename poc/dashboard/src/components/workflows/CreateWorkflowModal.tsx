import React, { useState, useEffect } from 'react';
import {
  Modal,
  Tabs,
  Form,
  Input,
  Button,
  Select,
  Checkbox,
  Tag,
  Row,
  Col,
  Card,
  Space,
  Divider,
  message,
  Tooltip,
  Radio,
} from 'antd';
import {
  ThunderboltOutlined,
  CopyOutlined,
  DownloadOutlined,
  PlusOutlined,
  DeleteOutlined,
  CheckOutlined,
  CodeOutlined,
  ApartmentOutlined,
  SendOutlined,
  SlackOutlined,
  RocketOutlined,
  SafetyCertificateOutlined,
  DashboardOutlined,
  SyncOutlined,
  ToolOutlined,
  FileTextOutlined,
  GithubOutlined,
  FolderOpenOutlined,
  GlobalOutlined,
} from '@ant-design/icons';
import {
  createWorkflow,
  generateWorkflowDefinition,
  convertWorkflowFormat,
  getMCPConnectors,
  getSkills,
  scanPlugins,
  createSkill,
} from '../../services/api';
import { PlatformWorkflow } from '../../types/mcp';
import {
  WorkflowCanvasGraph,
  WorkflowCanvasStep,
  WorkflowCanvasSkill,
} from './WorkflowCanvasGraph';

export interface WorkflowStep {
  key: string;
  name: string;
  agent_id: string;
  prompt_template: string;
  depends_on: string[];
  timeout_seconds?: number;
  mcp_servers?: string[];
  skills?: string[];
}

export interface AttachedSkill {
  id: string;
  name: string;
  source: string; // 'git' | 'local' | 'builtin' | 'custom'
  location?: string; // Git repo url or local directory/file path
  description?: string;
  content?: string;
}

interface CreateWorkflowModalProps {
  open: boolean;
  onClose: () => void;
  onSuccess: (workflow: PlatformWorkflow) => void;
  defaultChannelProvider?: string;
  defaultChannelId?: string;
}

const AVAILABLE_AGENTS = [
  { value: 'software-architect', label: 'Software Architect (System & Code Architecture)' },
  { value: 'qa-test-engineer', label: 'QA Test Engineer (Automated Verification)' },
  { value: 'release-security-reviewer', label: 'Release / Security Reviewer (Secrets & Gates)' },
  { value: 'backend-developer', label: 'Backend Developer (APIs & Database)' },
  { value: 'frontend-developer', label: 'Frontend Developer (Client & React UI)' },
  { value: 'ui-ux-designer', label: 'UI/UX Designer (Design & User Flows)' },
  { value: 'product-manager', label: 'Product Manager (PRD & Requirements)' },
  { value: 'ceo-orchestrator', label: 'CEO Orchestrator (Executive Synthesis)' },
  { value: 'auto-agent', label: 'Auto Generalist Agent (Autonomous Engine)' },
];

export const CreateWorkflowModal: React.FC<CreateWorkflowModalProps> = ({
  open,
  onClose,
  onSuccess,
  defaultChannelProvider = 'telegram',
  defaultChannelId = 'Hermes_test',
}) => {
  const [activeTab, setActiveTab] = useState<string>('ai');
  const [generating, setGenerating] = useState<boolean>(false);
  const [saving, setSaving] = useState<boolean>(false);
  const [copied, setCopied] = useState<boolean>(false);

  // Form states
  const [promptText, setPromptText] = useState<string>('');
  const [workflowName, setWorkflowName] = useState<string>('GitHub PR Review & Autonomous Gate');
  const [description, setDescription] = useState<string>(
    'Autonomous pipeline that inspects pull requests, validates architecture contracts, runs QA tests, and alerts the team.'
  );
  const [cronExpression, setCronExpression] = useState<string>('');
  const [webhookEnabled, setWebhookEnabled] = useState<boolean>(true);
  const [targetRepo, setTargetRepo] = useState<string>('yarinTag/ai-agents-platform');

  // Channel binding
  const [channelProvider, setChannelProvider] = useState<string>(defaultChannelProvider);
  const [channelId, setChannelId] = useState<string>(defaultChannelId);
  const [triggerEnabled, setTriggerEnabled] = useState<boolean>(true);
  const [notifyMode, setNotifyMode] = useState<string>('ON_COMPLETE');

  // MCP Connectors scope
  const [installedMcps, setInstalledMcps] = useState<string[]>(['telegram', 'github', 'trello', 'slack']);
  const [allowedMcps, setAllowedMcps] = useState<string[]>(['telegram', 'github']);

  // Skills
  const [workflowSkills, setWorkflowSkills] = useState<AttachedSkill[]>([
    {
      id: 'daily-git-reporter',
      name: 'Daily Git Reporter',
      source: 'git',
      location: 'https://github.com/yarinTag/ai-agents-platform.git',
      description: 'Summarizes git commits, diffs, and pull requests into structured daily digest',
    },
  ]);
  const [catalogSkills, setCatalogSkills] = useState<any[]>([]);
  const [createSkillModalOpen, setCreateSkillModalOpen] = useState<boolean>(false);
  const [newSkillForm] = Form.useForm();
  const [creatingSkill, setCreatingSkill] = useState<boolean>(false);

  // Steps
  const [steps, setSteps] = useState<WorkflowStep[]>([
    {
      key: 'pr_triage',
      name: 'PR Diff & Architecture Analysis',
      agent_id: 'software-architect',
      prompt_template: 'Inspect incoming PR {{pr_id}} on repository {{repo}}. Review architectural adherence, API contracts, and code diff.',
      depends_on: [],
      timeout_seconds: 300,
      mcp_servers: ['github'],
      skills: ['daily-git-reporter'],
    },
    {
      key: 'qa_validation',
      name: 'Automated Test Suite & Regression Check',
      agent_id: 'qa-test-engineer',
      prompt_template: 'Execute test suites and verify 100% pass rate for PR {{pr_id}} changes: {{pr_triage.output}}.',
      depends_on: ['pr_triage'],
      timeout_seconds: 300,
      mcp_servers: [],
      skills: [],
    },
    {
      key: 'security_audit',
      name: 'Secrets & Security Release Audit',
      agent_id: 'release-security-reviewer',
      prompt_template: 'Perform secrets scan, CVE check, and readiness gate audit for PR {{pr_id}}.',
      depends_on: ['qa_validation'],
      timeout_seconds: 240,
      mcp_servers: [],
      skills: [],
    },
  ]);

  // Live YAML state
  const [yamlContent, setYamlContent] = useState<string>('');
  const [yamlDirty, setYamlDirty] = useState<boolean>(false);

  // Load installed MCPs and available skills on open
  useEffect(() => {
    if (open) {
      getMCPConnectors()
        .then((res) => {
          const conns = res.data?.connectors || [];
          if (conns.length > 0) {
            const ids = conns.map((c: any) => c.id || c.provider);
            setInstalledMcps(Array.from(new Set(ids)));
            setAllowedMcps(Array.from(new Set(ids)));
          }
        })
        .catch(() => {});

      Promise.all([getSkills().catch(() => ({ data: [] })), scanPlugins().catch(() => ({ data: { plugins: [] } }))])
        .then(([skillsRes, pluginsRes]) => {
          const list: any[] = [...(skillsRes.data || [])];
          const plugList = pluginsRes.data?.plugins || [];
          plugList.forEach((p: any) => {
            (p.skills || []).forEach((sk: any) => {
              list.push({ ...sk, source: 'marketplace' });
            });
          });
          setCatalogSkills(list);
        })
        .catch(() => {});
    }
  }, [open]);

  // Generate YAML from current state
  const syncToYaml = async (
    curName = workflowName,
    curDesc = description,
    curSteps = steps,
    curCron = cronExpression,
    curWebhook = webhookEnabled,
    curProv = channelProvider,
    curChan = channelId,
    curTrig = triggerEnabled,
    curNotif = notifyMode,
    curMcps = allowedMcps,
    curSkills = workflowSkills
  ) => {
    const metadata: Record<string, any> = {};
    if (curProv && curChan) {
      metadata.channel_binding = {
        provider: curProv,
        connector_id: curProv,
        channel_id: curChan,
        channel_name: curChan,
        trigger_enabled: curTrig,
        notify_mode: curNotif,
        message_template: `🚀 Workflow ${curName} finished step execution with status: {{status}}`,
      };
    }

    const payload = {
      id: `wf_${Math.random().toString(36).substring(2, 10)}`,
      name: curName,
      description: curDesc,
      department_id: null,
      mcp_servers: curMcps,
      skills: curSkills,
      steps: curSteps,
      cron_expression: curCron || null,
      webhook_enabled: curWebhook,
      metadata,
    };

    try {
      const res = await convertWorkflowFormat({ json_content: JSON.stringify(payload, null, 2) });
      setYamlContent(res.data.yaml_content);
      setYamlDirty(false);
    } catch (err) {
      console.error('Failed to format YAML', err);
    }
  };

  useEffect(() => {
    if (open) {
      syncToYaml();
    }
  }, [open]);

  // Trigger AI/Template generator
  const handleGenerateTemplate = async (tmplType?: string) => {
    setGenerating(true);
    try {
      const res = await generateWorkflowDefinition({
        prompt: promptText || undefined,
        template_type: tmplType,
        channel_provider: channelProvider,
        channel_id: channelId,
        allowed_mcps: allowedMcps,
        skills: workflowSkills,
        target_repo: targetRepo,
      });

      const data = res.data;
      setWorkflowName(data.name);
      setDescription(data.description);
      setYamlContent(data.definition_yaml);

      // Parse generated steps from definition_json
      try {
        const parsed = JSON.parse(data.definition_json);
        if (parsed.steps) {
          setSteps(parsed.steps);
        }
        if (parsed.mcp_servers) {
          setAllowedMcps(parsed.mcp_servers);
        }
        if (parsed.skills) {
          setWorkflowSkills(parsed.skills);
        }
        if (parsed.cron_expression) {
          setCronExpression(parsed.cron_expression);
        }
        if (parsed.metadata?.channel_binding) {
          setChannelProvider(parsed.metadata.channel_binding.provider);
          setChannelId(parsed.metadata.channel_binding.channel_id);
          setTriggerEnabled(parsed.metadata.channel_binding.trigger_enabled);
          setNotifyMode(parsed.metadata.channel_binding.notify_mode);
        }
      } catch (e) {
        // ignore json parse error
      }

      message.success(`Generated workflow playbook: "${data.name}" (${data.steps_count} steps)`);
      setActiveTab('canvas'); // Switch immediately to the visual Canvas graph!
    } catch (err) {
      message.error('Failed to generate workflow');
    } finally {
      setGenerating(false);
    }
  };

  // Step operations
  const handleAddStep = () => {
    const newKey = `step_${steps.length + 1}`;
    const prevKey = steps.length > 0 ? steps[steps.length - 1].key : '';
    const newStep: WorkflowStep = {
      key: newKey,
      name: `Step ${steps.length + 1}`,
      agent_id: 'auto-agent',
      prompt_template: 'Process input and execute task for step.',
      depends_on: prevKey ? [prevKey] : [],
      timeout_seconds: 300,
      mcp_servers: allowedMcps.slice(0, 1),
      skills: [],
    };
    const updated = [...steps, newStep];
    setSteps(updated);
    syncToYaml(workflowName, description, updated);
  };

  const handleUpdateStep = (index: number, patch: Partial<WorkflowStep>) => {
    const updated = [...steps];
    updated[index] = { ...updated[index], ...patch };
    setSteps(updated);
    syncToYaml(workflowName, description, updated);
  };

  const handleDeleteStep = (index: number) => {
    const updated = steps.filter((_, i) => i !== index);
    setSteps(updated);
    syncToYaml(workflowName, description, updated);
  };

  // Skill management
  const handleAttachExistingSkill = (skillId: string) => {
    const found = catalogSkills.find((s) => s.id === skillId);
    if (!found) return;
    if (workflowSkills.some((s) => s.id === skillId)) {
      message.info('Skill already attached to this workflow');
      return;
    }
    const newSkill: AttachedSkill = {
      id: found.id,
      name: found.name,
      source: found.source || (found.path ? 'local' : 'builtin'),
      location: found.path || found.location,
      description: found.description,
      content: found.content || found.content_preview,
    };
    const updated = [...workflowSkills, newSkill];
    setWorkflowSkills(updated);
    syncToYaml(workflowName, description, steps, cronExpression, webhookEnabled, channelProvider, channelId, triggerEnabled, notifyMode, allowedMcps, updated);
    message.success(`Attached skill "${found.name}" to workflow playbook`);
  };

  const handleRemoveSkill = (skillId: string) => {
    const updated = workflowSkills.filter((s) => s.id !== skillId);
    setWorkflowSkills(updated);
    syncToYaml(workflowName, description, steps, cronExpression, webhookEnabled, channelProvider, channelId, triggerEnabled, notifyMode, allowedMcps, updated);
  };

  const handleCreateNewSkill = async (values: any) => {
    setCreatingSkill(true);
    try {
      const skillId = values.name.toLowerCase().replace(/[^a-z0-9]/g, '-');
      const newSkill: AttachedSkill = {
        id: skillId,
        name: values.name,
        source: values.source || 'custom',
        location: values.location || undefined,
        description: values.description || '',
        content: values.content || `# Skill: ${values.name}\n\n${values.description || ''}`,
      };

      if (values.save_to_library) {
        await createSkill({
          name: values.name,
          description: values.description,
          content: values.content || `# ${values.name}`,
        }).catch(() => {});
      }

      const updated = [...workflowSkills, newSkill];
      setWorkflowSkills(updated);
      syncToYaml(workflowName, description, steps, cronExpression, webhookEnabled, channelProvider, channelId, triggerEnabled, notifyMode, allowedMcps, updated);
      message.success(`Skill "${values.name}" created and added to workflow!`);
      setCreateSkillModalOpen(false);
      newSkillForm.resetFields();
    } catch (err) {
      message.error('Failed to create skill');
    } finally {
      setCreatingSkill(false);
    }
  };

  // Copy YAML
  const handleCopyYaml = () => {
    navigator.clipboard.writeText(yamlContent);
    setCopied(true);
    message.success('YAML playbook copied to clipboard!');
    setTimeout(() => setCopied(false), 2000);
  };

  // Download YAML
  const handleDownloadYaml = () => {
    const blob = new Blob([yamlContent], { type: 'text/yaml' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${workflowName.toLowerCase().replace(/[^a-z0-9]/g, '_')}.yaml`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    message.success('Downloaded workflow.yaml');
  };

  // Sync edited YAML back to visual state
  const handleSyncYamlToVisual = async () => {
    try {
      const res = await convertWorkflowFormat({ yaml_content: yamlContent });
      const parsed = JSON.parse(res.data.json_content);
      if (parsed.name) setWorkflowName(parsed.name);
      if (parsed.description) setDescription(parsed.description);
      if (parsed.steps) setSteps(parsed.steps);
      if (parsed.mcp_servers) setAllowedMcps(parsed.mcp_servers);
      if (parsed.skills) setWorkflowSkills(parsed.skills);
      if (parsed.cron_expression) setCronExpression(parsed.cron_expression);
      if (parsed.webhook_enabled !== undefined) setWebhookEnabled(parsed.webhook_enabled);
      if (parsed.metadata?.channel_binding) {
        setChannelProvider(parsed.metadata.channel_binding.provider);
        setChannelId(parsed.metadata.channel_binding.channel_id);
      }
      setYamlDirty(false);
      message.success('YAML synchronized with visual builder & canvas!');
    } catch (err: any) {
      message.error(err?.response?.data?.detail || 'Invalid YAML format');
    }
  };

  // Submit & Save
  const handleSaveWorkflow = async () => {
    setSaving(true);
    try {
      const res = await createWorkflow({
        name: workflowName,
        description,
        definition_yaml: yamlContent,
        cron_expression: cronExpression || undefined,
        webhook_enabled: webhookEnabled,
      });

      message.success(`Workflow "${workflowName}" created and active!`);
      onSuccess(res.data);
      onClose();
    } catch (err: any) {
      message.error(err?.response?.data?.detail || 'Failed to create workflow');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      title={
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <RocketOutlined style={{ color: '#38bdf8', fontSize: '20px' }} />
          <div>
            <span style={{ fontSize: '16px', fontWeight: 800, color: '#f0f6fc' }}>
              Create Workflow, Canvas DAG & Auto YAML Playbook
            </span>
            <div style={{ fontSize: '12px', color: '#8b949e', fontWeight: 400 }}>
              Design multi-agent DAG pipelines restricted strictly to configured MCPs with attached skills
            </div>
          </div>
        </div>
      }
      open={open}
      onCancel={onClose}
      width={1000}
      styles={{
        body: { background: '#0d1117', color: '#f0f6fc' },
        header: { background: '#0d1117', borderBottom: '1px solid #21262d' },
      }}
      footer={[
        <div key="summary" style={{ float: 'left', display: 'flex', alignItems: 'center', gap: '8px', paddingTop: '4px' }}>
          <Tag color="cyan">{steps.length} Steps in DAG</Tag>
          <Tag color="purple"><ToolOutlined /> {allowedMcps.length} MCPs</Tag>
          <Tag color="gold"><FileTextOutlined /> {workflowSkills.length} Skills</Tag>
          {channelProvider && channelId && (
            <Tag color={channelProvider === 'telegram' ? 'blue' : 'gold'}>
              {channelProvider === 'telegram' ? <SendOutlined /> : <SlackOutlined />} {channelId}
            </Tag>
          )}
        </div>,
        <Button key="cancel" onClick={onClose} style={{ background: '#161b22', borderColor: '#30363d', color: '#8b949e' }}>
          Cancel
        </Button>,
        <Button
          key="save"
          type="primary"
          icon={<ThunderboltOutlined />}
          loading={saving}
          onClick={handleSaveWorkflow}
          style={{ background: '#059669', borderColor: '#059669', fontWeight: 700 }}
        >
          Deploy & Save Workflow
        </Button>,
      ]}
    >
      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={[
          {
            key: 'ai',
            label: (
              <span style={{ fontWeight: 600 }}>
                <ThunderboltOutlined style={{ color: '#38bdf8' }} /> 1. AI & MCP Scope (מחולל מהיר + הגדרת MCPs)
              </span>
            ),
            children: (
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
                        Configured MCP Scope (ה-MCPs המורשים לוורק-פלואו זה בלבד):
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
                    READY-TO-USE PRESETS (תבניות מוכנות בלחיצה אחת):
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
                    OR DESCRIBE YOUR CUSTOM WORKFLOW (שפה חופשית בעברית או באנגלית):
                  </div>
                  <Input.TextArea
                    rows={3}
                    placeholder="לדוגמה: בהינתן הודעה בערוץ טלגרם כלשהו הרץ וורקפלו שבודק שינויים אחרונים בגיטאהב בריפו yarinTag/ai-agents-platform ושלח דוח יומי מסוכם בחזרה לערוץ..."
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
                        onChange={setChannelProvider}
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
                      <Input
                        size="small"
                        value={channelId}
                        onChange={(e) => setChannelId(e.target.value)}
                        placeholder="e.g. Hermes_test"
                        style={{ width: '100%', marginTop: '4px', background: '#161b22', borderColor: '#30363d', color: '#f0f6fc' }}
                      />
                    </Col>
                    <Col span={8}>
                      <span style={{ fontSize: '12px', color: '#8b949e' }}>Target Repo (owner/repo):</span>
                      <Input
                        size="small"
                        value={targetRepo}
                        onChange={(e) => setTargetRepo(e.target.value)}
                        placeholder="e.g. yarinTag/ai-agents-platform"
                        style={{ width: '100%', marginTop: '4px', background: '#161b22', borderColor: '#30363d', color: '#f0f6fc' }}
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
            ),
          },
          {
            key: 'canvas',
            label: (
              <span style={{ fontWeight: 600 }}>
                <ApartmentOutlined style={{ color: '#10b981' }} /> 2. Workflow Canvas (תרשים קאנבס)
              </span>
            ),
            children: (
              <div style={{ padding: '8px 0' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                  <div style={{ fontSize: '12px', color: '#8b949e' }}>
                    Visual DAG Canvas showing triggers, execution stages, assigned agents, restricted MCPs, and skills:
                  </div>
                  <Button
                    size="small"
                    type="dashed"
                    icon={<PlusOutlined />}
                    onClick={handleAddStep}
                    style={{ color: '#38bdf8', borderColor: '#0284c7', background: 'transparent' }}
                  >
                    + Add Step
                  </Button>
                </div>

                <WorkflowCanvasGraph
                  workflowName={workflowName}
                  steps={steps}
                  channelBinding={{
                    provider: channelProvider,
                    channel_id: channelId,
                    trigger_enabled: triggerEnabled,
                    notify_mode: notifyMode,
                  }}
                  skills={workflowSkills}
                  allowedMcps={allowedMcps}
                  height={460}
                />
              </div>
            ),
          },
          {
            key: 'builder',
            label: (
              <span style={{ fontWeight: 600 }}>
                <ToolOutlined style={{ color: '#a855f7' }} /> 3. Visual Step & Skill Builder (שלבים וסקילים)
              </span>
            ),
            children: (
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

                {/* Skills Management Section */}
                <Card
                  size="small"
                  style={{ background: '#161b22', borderColor: '#30363d', marginBottom: '16px' }}
                  title={
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <FileTextOutlined style={{ color: '#f59e0b' }} />
                        <span style={{ color: '#f0f6fc', fontWeight: 700, fontSize: '13px' }}>
                          Connected Skills ({workflowSkills.length}) - סקילים המחוברים לוורק-פלואו
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
                            options={AVAILABLE_AGENTS}
                          />
                        </Col>
                      </Row>

                      {/* MCP and Skill assignment per step */}
                      <Row gutter={8} style={{ marginBottom: '8px' }}>
                        <Col span={12}>
                          <span style={{ fontSize: '11px', color: '#8b949e' }}>Step MCP Connectors:</span>
                          <Select
                            mode="multiple"
                            size="small"
                            style={{ width: '100%' }}
                            value={st.mcp_servers || []}
                            onChange={(val) => handleUpdateStep(idx, { mcp_servers: val })}
                            options={allowedMcps.map((m) => ({ label: m.toUpperCase(), value: m }))}
                            placeholder="Select step MCPs..."
                          />
                        </Col>
                        <Col span={12}>
                          <span style={{ fontSize: '11px', color: '#8b949e' }}>Step Skills:</span>
                          <Select
                            mode="multiple"
                            size="small"
                            style={{ width: '100%' }}
                            value={st.skills || []}
                            onChange={(val) => handleUpdateStep(idx, { skills: val })}
                            options={workflowSkills.map((s) => ({ label: s.name, value: s.id }))}
                            placeholder="Assign attached skills..."
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
            ),
          },
          {
            key: 'yaml',
            label: (
              <span style={{ fontWeight: 600 }}>
                <CodeOutlined style={{ color: '#f59e0b' }} /> 4. Live YAML Playbook (קובץ ה-YAML שנוצר)
              </span>
            ),
            children: (
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                  <div style={{ color: '#8b949e', fontSize: '12px' }}>
                    Production-ready declarative YAML file generated automatically with MCPs and skills:
                  </div>
                  <Space>
                    {yamlDirty && (
                      <Button
                        size="small"
                        icon={<SyncOutlined />}
                        onClick={handleSyncYamlToVisual}
                        style={{ background: '#1e3a8a', borderColor: '#2563eb', color: '#60a5fa' }}
                      >
                        Sync to Visual Builder
                      </Button>
                    )}
                    <Button
                      size="small"
                      icon={copied ? <CheckOutlined /> : <CopyOutlined />}
                      onClick={handleCopyYaml}
                      style={{ background: '#161b22', borderColor: '#30363d', color: '#f0f6fc' }}
                    >
                      {copied ? 'Copied!' : 'Copy YAML'}
                    </Button>
                    <Button
                      size="small"
                      icon={<DownloadOutlined />}
                      onClick={handleDownloadYaml}
                      style={{ background: '#161b22', borderColor: '#30363d', color: '#38bdf8' }}
                    >
                      Download .yaml
                    </Button>
                  </Space>
                </div>

                <Input.TextArea
                  rows={15}
                  value={yamlContent}
                  onChange={(e) => {
                    setYamlContent(e.target.value);
                    setYamlDirty(true);
                  }}
                  style={{
                    fontFamily: 'monospace',
                    fontSize: '12px',
                    background: '#090d13',
                    borderColor: '#30363d',
                    color: '#34d399',
                    borderRadius: '8px',
                    padding: '12px',
                    lineHeight: '1.5',
                  }}
                />
              </div>
            ),
          },
        ]}
      />

      {/* Modal to Create New Skill with Git / Local repo location */}
      <Modal
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <FileTextOutlined style={{ color: '#f59e0b' }} />
            <span>Create New Skill for Workflow (הגדרת סקיל חדש עם מיקום בריפו)</span>
          </div>
        }
        open={createSkillModalOpen}
        onCancel={() => setCreateSkillModalOpen(false)}
        onOk={() => newSkillForm.submit()}
        confirmLoading={creatingSkill}
        okText="Add Skill to Workflow"
        styles={{
          body: { background: '#0d1117', color: '#f0f6fc' },
          header: { background: '#0d1117', borderBottom: '1px solid #21262d' },
        }}
      >
        <Form
          form={newSkillForm}
          layout="vertical"
          onFinish={handleCreateNewSkill}
          initialValues={{ source: 'git', save_to_library: true }}
        >
          <Form.Item
            name="name"
            label={<span style={{ color: '#f0f6fc' }}>Skill Name</span>}
            rules={[{ required: true, message: 'Skill name is required' }]}
          >
            <Input placeholder="e.g., Daily Git Reporter" style={{ background: '#161b22', borderColor: '#30363d', color: '#f0f6fc' }} />
          </Form.Item>

          <Form.Item
            name="source"
            label={<span style={{ color: '#f0f6fc' }}>Skill Source Type</span>}
          >
            <Radio.Group>
              <Radio value="git" style={{ color: '#f0f6fc' }}><GithubOutlined /> Git Repository</Radio>
              <Radio value="local" style={{ color: '#f0f6fc' }}><FolderOpenOutlined /> Local Filesystem Path</Radio>
              <Radio value="custom" style={{ color: '#f0f6fc' }}>Inline Instructions</Radio>
            </Radio.Group>
          </Form.Item>

          <Form.Item
            name="location"
            label={<span style={{ color: '#f0f6fc' }}>Repository / Path Location (מיקום בריפו או מקומי)</span>}
            tooltip="URL of Git repo (e.g. https://github.com/my-org/skills.git) or local path (e.g. /Users/.../skills/my-skill)"
          >
            <Input
              placeholder="e.g. https://github.com/yarinTag/ai-agents-platform.git or /path/to/skill"
              style={{ background: '#161b22', borderColor: '#30363d', color: '#f0f6fc' }}
            />
          </Form.Item>

          <Form.Item
            name="description"
            label={<span style={{ color: '#f0f6fc' }}>Description</span>}
          >
            <Input placeholder="Brief explanation of what this skill does" style={{ background: '#161b22', borderColor: '#30363d', color: '#f0f6fc' }} />
          </Form.Item>

          <Form.Item
            name="content"
            label={<span style={{ color: '#f0f6fc' }}>Skill Instructions / Prompt Specification</span>}
          >
            <Input.TextArea
              rows={3}
              placeholder="# Instructions for agent when using this skill..."
              style={{ background: '#161b22', borderColor: '#30363d', color: '#f0f6fc' }}
            />
          </Form.Item>

          <Form.Item name="save_to_library" valuePropName="checked">
            <Checkbox style={{ color: '#8b949e' }}>Also save skill to platform library for other workflows</Checkbox>
          </Form.Item>
        </Form>
      </Modal>
    </Modal>
  );
};
