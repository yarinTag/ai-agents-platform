import { useWorkflowResources } from './useWorkflowResources';
import { useState, useEffect } from 'react';
import { Form, message } from 'antd';

import { createWorkflow, generateWorkflowDefinition, convertWorkflowFormat, createSkill } from '../../services/api';

import { useAuth } from '../../context/AuthContext';

import type { WorkflowStep, AttachedSkill, CreateWorkflowModalProps } from './workflowBuilderTypes';

export function useWorkflowBuilder({ open, onClose, onSuccess, defaultChannelProvider = 'telegram', defaultChannelId = 'Hermes_test', departmentId }: CreateWorkflowModalProps) {
  const { departments, activeDepartmentId } = useAuth();
  const effectiveDepartmentId = departmentId || activeDepartmentId || departments[0]?.id;

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
  const [targetRepo, setTargetRepo] = useState<string>('');

  // Channel binding
  const [channelProvider, setChannelProvider] = useState<string>(defaultChannelProvider);
  const [channelId, setChannelId] = useState<string>(defaultChannelId);
  const [triggerEnabled, setTriggerEnabled] = useState<boolean>(true);
  const [notifyMode, setNotifyMode] = useState<string>('ON_COMPLETE');
  const [allowedMcps, setAllowedMcps] = useState<string[]>([]);
  const [workflowSkills, setWorkflowSkills] = useState<AttachedSkill[]>([]);
  const resources = useWorkflowResources({ open, channelProvider, channelId, setChannelId, setAllowedMcps });
  const { installedMcps, telegramChannels, slackChannels, githubRepos, catalogSkills, setCatalogSkills, resourcesLoading, connectorError, skillsError, reloadResources } = resources;
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
      mcp_servers: [],
      skills: [],
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

  const resourcesUnavailable = resourcesLoading ||
    Boolean(connectorError && (allowedMcps.length || channelId || steps.some(step => step.mcp_servers?.length))) ||
    Boolean(skillsError && (workflowSkills.length || steps.some(step => step.skills?.length)));

  // Trigger AI/Template generator
  const handleGenerateTemplate = async (tmplType?: string) => {
    if (resourcesUnavailable) { message.error('Required workflow resources are unavailable. Retry loading them first.'); return; }
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
    if (resourcesUnavailable) { message.error('Required workflow resources are unavailable. Retry loading them first.'); return; }
    setSaving(true);
    try {
      const res = await createWorkflow({
        name: workflowName,
        description,
        department_id: effectiveDepartmentId,
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

  return {
    resourcesLoading, connectorError, skillsError, reloadResources, resourcesUnavailable,
    open, onClose, onSuccess, defaultChannelProvider, defaultChannelId,
    departmentId, departments, activeDepartmentId, effectiveDepartmentId, activeTab,
    setActiveTab, generating, setGenerating, saving, setSaving,
    copied, setCopied, promptText, setPromptText, workflowName,
    setWorkflowName, description, setDescription, cronExpression, setCronExpression,
    webhookEnabled, setWebhookEnabled, targetRepo, setTargetRepo, channelProvider,
    setChannelProvider, channelId, setChannelId, triggerEnabled, setTriggerEnabled,
    notifyMode, setNotifyMode, telegramChannels, slackChannels,
    githubRepos, installedMcps,
    allowedMcps, setAllowedMcps, workflowSkills, setWorkflowSkills, catalogSkills,
    setCatalogSkills, createSkillModalOpen, setCreateSkillModalOpen, newSkillForm, creatingSkill,
    setCreatingSkill, steps, setSteps, yamlContent, setYamlContent,
    yamlDirty, setYamlDirty, syncToYaml, handleGenerateTemplate, handleAddStep,
    handleUpdateStep, handleDeleteStep, handleAttachExistingSkill, handleRemoveSkill, handleCreateNewSkill,
    handleCopyYaml, handleDownloadYaml, handleSyncYamlToVisual, handleSaveWorkflow,
  };
}
