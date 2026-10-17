import React, { useEffect, useState } from 'react';
import {
  Card,
  Row,
  Col,
  Tag,
  Button,
  Input,
  Modal,
  Form,
  Badge,
  Spin,
  message,
  Tabs,
  Drawer,
  List,
  Typography,
  Tooltip,
  Popconfirm,
  Checkbox,
  Divider,
  Select,
  Radio,
  Space,
  Table,
  Alert,
} from 'antd';
import {
  ApiOutlined,
  GithubOutlined,
  GitlabOutlined,
  LockOutlined,
  UnlockOutlined,
  SendOutlined,
  SlackOutlined,
  DatabaseOutlined,
  GlobalOutlined,
  FolderOpenOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  SyncOutlined,
  PlusOutlined,
  SettingOutlined,
  SafetyCertificateOutlined,
  DeleteOutlined,
  ToolOutlined,
  SearchOutlined,
  ThunderboltOutlined,
  KeyOutlined,
  AppstoreOutlined,
  CheckSquareOutlined,
  LinkOutlined,
  BellOutlined,
  BranchesOutlined,
  MessageOutlined,
  DisconnectOutlined,
  RocketOutlined,
  CaretRightOutlined,
  ApartmentOutlined,
  FileTextOutlined,
} from '@ant-design/icons';
import { CreateWorkflowModal } from '../components/workflows/CreateWorkflowModal';
import { WorkflowCanvasGraph } from '../components/workflows/WorkflowCanvasGraph';
import {
  getMCPCatalog,
  getMCPConnectors,
  installMCPConnector,
  updateMCPConnector,
  deleteMCPConnector,
  testMCPConnector,
  getMCPTools,
  getAgents,
  getMCPPermissions,
  grantMCPPermission,
  revokeMCPPermission,
  discoverMCPResources,
  testChannelMessage,
  getWorkflows,
  bindWorkflowChannel,
  unbindWorkflowChannel,
  deleteWorkflow,
  executeWorkflow,
} from '../services/api';
import {
  MCPCatalogItem,
  MCPConnector,
  MCPTool,
  AgentMCPPermission,
  PlatformWorkflow,
  WorkflowChannelBinding,
} from '../types/mcp';
import { Agent } from '../types/agent';
import { useAuth } from '../context/AuthContext';

const { Text, Paragraph } = Typography;

export const McpHubPage: React.FC = () => {
  const { departments, activeDepartmentId } = useAuth();
  const [loading, setLoading] = useState<boolean>(true);
  const [catalog, setCatalog] = useState<MCPCatalogItem[]>([]);
  const [connectors, setConnectors] = useState<MCPConnector[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [permissions, setPermissions] = useState<AgentMCPPermission[]>([]);
  const [workflows, setWorkflows] = useState<PlatformWorkflow[]>([]);

  // Search & filter
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedCategory, setSelectedCategory] = useState<string>('ALL');

  // Install / Configure Modal
  const [modalVisible, setModalVisible] = useState<boolean>(false);
  const [selectedCatalogItem, setSelectedCatalogItem] = useState<MCPCatalogItem | null>(null);
  const [editingConnector, setEditingConnector] = useState<MCPConnector | null>(null);
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [form] = Form.useForm();

  // Resource discovery (Git Repos, Slack Channels, Telegram Chats)
  const [discoveredResources, setDiscoveredResources] = useState<any[]>([]);
  const [selectedResources, setSelectedResources] = useState<string[]>([]);
  const [customResourceInput, setCustomResourceInput] = useState<string>('');
  const [fetchingResources, setFetchingResources] = useState<boolean>(false);
  const [resourceDiscoveryError, setResourceDiscoveryError] = useState<string | null>(null);

  // Custom MCP Modal
  const [customModalVisible, setCustomModalVisible] = useState<boolean>(false);
  const [customForm] = Form.useForm();

  // Tools Drawer
  const [toolsDrawerVisible, setToolsDrawerVisible] = useState<boolean>(false);
  const [drawerConnector, setDrawerConnector] = useState<MCPConnector | null>(null);
  const [connectorTools, setConnectorTools] = useState<MCPTool[]>([]);
  const [loadingTools, setLoadingTools] = useState<boolean>(false);

  // Agent Permissions Modal
  const [permModalVisible, setPermModalVisible] = useState<boolean>(false);
  const [permConnector, setPermConnector] = useState<MCPConnector | null>(null);
  const [updatingPerms, setUpdatingPerms] = useState<boolean>(false);

  // Workflow Channel Binding Modal
  const [bindingModalVisible, setBindingModalVisible] = useState<boolean>(false);
  const [bindingWorkflow, setBindingWorkflow] = useState<PlatformWorkflow | null>(null);
  const [bindingSubmitting, setBindingSubmitting] = useState<boolean>(false);
  const [createWfModalVisible, setCreateWfModalVisible] = useState<boolean>(false);
  const [canvasModalVisible, setCanvasModalVisible] = useState<boolean>(false);
  const [canvasWorkflow, setCanvasWorkflow] = useState<PlatformWorkflow | null>(null);
  const [bindingForm] = Form.useForm();
  const [quickAddBindingInput, setQuickAddBindingInput] = useState<string>('');
  const [extraBindingChannels, setExtraBindingChannels] = useState<{ slack: string[]; telegram: string[] }>({
    slack: [],
    telegram: [],
  });

  // Testing status maps
  const [testingMap, setTestingMap] = useState<Record<string, boolean>>({});
  const [testingChannelMap, setTestingChannelMap] = useState<Record<string, boolean>>({});
  const [runningWfMap, setRunningWfMap] = useState<Record<string, boolean>>({});

  const loadData = async () => {
    try {
      setLoading(true);
      const [catRes, connRes, agentsRes, permRes, wfRes] = await Promise.all([
        getMCPCatalog().catch(() => ({ data: { catalog: [] } })),
        getMCPConnectors().catch(() => ({ data: { connectors: [] } })),
        getAgents().catch(() => ({ data: [] })),
        getMCPPermissions().catch(() => ({ data: { permissions: [] } })),
        getWorkflows().catch(() => ({ data: [] })),
      ]);
      setCatalog(catRes.data?.catalog || []);
      setConnectors(connRes.data?.connectors || []);
      setAgents(agentsRes.data || []);
      setPermissions(permRes.data?.permissions || []);
      setWorkflows(wfRes.data || []);
    } catch (err: any) {
      message.error('Failed to load MCP integrations');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  // Map icons
  const getProviderIcon = (provider: string, size = 24) => {
    switch (provider.toLowerCase()) {
      case 'github':
      case 'git':
        return <GithubOutlined style={{ fontSize: size, color: '#f0f6fc' }} />;
      case 'gitlab':
        return <GitlabOutlined style={{ fontSize: size, color: '#fc6d26' }} />;
      case 'trello':
        return <CheckSquareOutlined style={{ fontSize: size, color: '#0079bf' }} />;
      case 'telegram':
        return <SendOutlined style={{ fontSize: size, color: '#229ED9' }} />;
      case 'slack':
        return <SlackOutlined style={{ fontSize: size, color: '#ECB22E' }} />;
      case 'postgres':
      case 'database':
        return <DatabaseOutlined style={{ fontSize: size, color: '#336791' }} />;
      case 'brave-search':
      case 'search':
        return <GlobalOutlined style={{ fontSize: size, color: '#FB542B' }} />;
      case 'filesystem':
        return <FolderOpenOutlined style={{ fontSize: size, color: '#10b981' }} />;
      default:
        return <ApiOutlined style={{ fontSize: size, color: '#a855f7' }} />;
    }
  };

  // Trigger Resource Discovery for Git / GitLab / Slack / Telegram
  const handleFetchResources = async (
    provider: string,
    token?: string,
    currentSelected?: string[],
    isManual: boolean = false
  ) => {
    setFetchingResources(true);
    setResourceDiscoveryError(null);

    const isGitProvider = provider === 'github' || provider === 'git' || provider === 'gitlab';
    const trimmedToken = (token || '').trim();

    if (isGitProvider && isManual && !trimmedToken) {
      const providerLabel = provider === 'gitlab' ? 'GitLab' : 'GitHub';
      const errMsg = `Please enter a valid ${providerLabel} Personal Access Token before fetching repositories.`;
      setResourceDiscoveryError(errMsg);
      message.error(errMsg);
      setFetchingResources(false);
      return;
    }

    try {
      const allFormValues = form.getFieldsValue();
      const res = await discoverMCPResources(provider, trimmedToken || undefined, allFormValues);

      if (res.data?.requires_token && isManual) {
        const errMsg = res.data.message || 'Please enter a valid Personal Access Token to view accessible repositories.';
        setResourceDiscoveryError(errMsg);
        message.error(errMsg);
        setFetchingResources(false);
        return;
      }

      if (isGitProvider) {
        const repos = res.data?.repositories || [];
        const mergedRepos = [...repos];
        if (currentSelected) {
          currentSelected.forEach((rName) => {
            if (!mergedRepos.some((r: any) => (r.name || r.full_name) === rName)) {
              mergedRepos.push({ name: rName, full_name: rName, description: 'Configured repository', is_local: false });
            }
          });
        }
        setDiscoveredResources(mergedRepos);
        if (selectedResources.length === 0 && (!currentSelected || currentSelected.length === 0) && mergedRepos.length > 0) {
          const mainRepo = mergedRepos.find((r: any) => (r.name || r.full_name) === 'ai-agents-platform') || mergedRepos[0];
          setSelectedResources([mainRepo.full_name || mainRepo.name]);
        }
        if (isManual) {
          message.success(`Discovered ${repos.length} accessible ${provider === 'gitlab' ? 'GitLab' : 'GitHub'} repositories!`);
        }
      } else if (provider === 'slack') {
        const channels = res.data?.channels || [];
        const mergedChannels = [...channels];
        if (currentSelected) {
          currentSelected.forEach((cName) => {
            if (!mergedChannels.some((c: any) => (c.name || c.id) === cName)) {
              mergedChannels.push({ id: cName, name: cName, description: 'Configured channel' });
            }
          });
        }
        setDiscoveredResources(mergedChannels);
        if (selectedResources.length === 0 && (!currentSelected || currentSelected.length === 0) && mergedChannels.length > 0) {
          setSelectedResources(['#general', '#dev-team', '#pr-review']);
        }
        if (isManual) {
          message.success(`Discovered ${channels.length} Slack channels`);
        }
      } else if (provider === 'telegram') {
        const chats = res.data?.chats || [];
        const mergedChats = [...chats];
        if (currentSelected) {
          currentSelected.forEach((cName) => {
            if (!mergedChats.some((c: any) => (c.id || c.name) === cName)) {
              mergedChats.push({ id: cName, name: cName, description: 'Configured chat / channel' });
            }
          });
        }
        setDiscoveredResources(mergedChats);
        if (selectedResources.length === 0 && (!currentSelected || currentSelected.length === 0) && mergedChats.length > 0) {
          setSelectedResources(['@agents_office_alerts']);
        }
        if (isManual) {
          message.success(`Discovered ${chats.length} Telegram chats`);
        }
      }
    } catch (err: any) {
      console.error('Resource discovery failed', err);
      const detail = err.response?.data?.detail || err.message || `Failed to discover ${provider} resources`;
      if (isManual) {
        setResourceDiscoveryError(detail);
        message.error(detail);
      } else {
        message.warning('Using default resource catalog');
      }
    } finally {
      setFetchingResources(false);
    }
  };

  const handleFetchTokenRepositories = async () => {
    const provider = (selectedCatalogItem?.provider || editingConnector?.provider || 'github').toLowerCase();
    const token = form.getFieldValue('token') || form.getFieldValue('personal_access_token') || form.getFieldValue('api_key');
    await handleFetchResources(provider, token, selectedResources, true);
  };

  // Open Connect / Configure Modal
  const handleOpenConnect = async (catItem: MCPCatalogItem, existingConn?: MCPConnector) => {
    setSelectedCatalogItem(catItem);
    setEditingConnector(existingConn || null);
    form.resetFields();
    setCustomResourceInput('');
    setResourceDiscoveryError(null);

    const provider = catItem.provider.toLowerCase();
    let initialSelected: string[] = [];

    // Pre-populate existing config or catalog defaults
    if (existingConn) {
      form.setFieldsValue({
        name: existingConn.name,
        ...existingConn.configuration,
      });

      if (provider === 'github' || provider === 'git' || provider === 'gitlab') {
        initialSelected = existingConn.configuration?.allowed_repos || ['ai-agents-platform'];
      } else if (provider === 'telegram') {
        if (Array.isArray(existingConn.configuration?.allowed_channels) && existingConn.configuration.allowed_channels.length > 0) {
          initialSelected = existingConn.configuration.allowed_channels;
        } else if (typeof existingConn.configuration?.chat_id === 'string' && existingConn.configuration.chat_id.trim()) {
          initialSelected = [existingConn.configuration.chat_id.trim()];
        } else {
          initialSelected = ['@agents_office_alerts'];
        }
      } else if (provider === 'slack') {
        if (Array.isArray(existingConn.configuration?.allowed_channels) && existingConn.configuration.allowed_channels.length > 0) {
          initialSelected = existingConn.configuration.allowed_channels;
        } else if (typeof existingConn.configuration?.default_channel === 'string' && existingConn.configuration.default_channel.trim()) {
          initialSelected = [existingConn.configuration.default_channel.trim()];
        } else {
          initialSelected = ['#general'];
        }
      }
    } else {
      const defaults: Record<string, any> = { name: catItem.name };
      Object.entries(catItem.config_schema).forEach(([key, field]) => {
        if (field.default !== undefined) {
          defaults[key] = field.default;
        }
      });
      form.setFieldsValue(defaults);
      if (provider === 'github' || provider === 'git' || provider === 'gitlab') {
        initialSelected = ['ai-agents-platform'];
      } else if (provider === 'telegram') {
        initialSelected = ['@agents_office_alerts'];
      } else if (provider === 'slack') {
        initialSelected = ['#general'];
      }
    }

    setSelectedResources(initialSelected);
    setModalVisible(true);

    // Fetch available resources for selection
    if (['github', 'git', 'gitlab', 'slack', 'telegram'].includes(provider)) {
      const existingToken = existingConn?.configuration?.token || existingConn?.configuration?.personal_access_token || existingConn?.configuration?.bot_token;
      if (existingToken) {
        await handleFetchResources(provider, existingToken, initialSelected, false);
      }
    }
  };

  // Add custom typed resource (repo or channel)
  const handleAddCustomResource = () => {
    if (!customResourceInput.trim()) return;
    const val = customResourceInput.trim();
    if (!selectedResources.includes(val)) {
      setSelectedResources((prev) => [...prev, val]);
      setDiscoveredResources((prev) => [
        ...prev,
        { name: val, full_name: val, id: val, description: 'Custom added' },
      ]);
    }
    setCustomResourceInput('');
  };

  // Submit Connect Form
  const handleSaveConnector = async () => {
    try {
      const values = await form.validateFields();
      setSubmitting(true);

      const name = values.name;
      const config: Record<string, any> = {};
      Object.keys(values).forEach((k) => {
        if (k !== 'name') {
          config[k] = values[k];
        }
      });

      const provider = (selectedCatalogItem?.provider || editingConnector?.provider || '').toLowerCase();

      // Attach selected repos or channels
      if (provider === 'github' || provider === 'git' || provider === 'gitlab') {
        config.allowed_repos = selectedResources;
      } else if (provider === 'slack' || provider === 'telegram') {
        config.allowed_channels = selectedResources;
        if (provider === 'telegram') {
          config.chat_id = selectedResources[0] || '';
        }
        if (provider === 'slack') {
          config.default_channel = selectedResources[0] || '';
        }
      }

      if (editingConnector) {
        await updateMCPConnector(editingConnector.id, {
          name,
          configuration: config,
          status: 'CONNECTED',
        });
        message.success(`Updated ${name} integration`);
      } else if (selectedCatalogItem) {
        await installMCPConnector({
          name,
          provider: selectedCatalogItem.provider,
          configuration: config,
          capabilities: selectedCatalogItem.default_tools.map((t) => t.name),
        });
        message.success(`Installed and connected ${name}`);
      }

      setModalVisible(false);
      loadData();
    } catch (err: any) {
      if (err?.errorFields) return;
      message.error(err?.response?.data?.detail || 'Failed to save connector');
    } finally {
      setSubmitting(false);
    }
  };

  // Submit Custom MCP Form
  const handleSaveCustom = async () => {
    try {
      const values = await customForm.validateFields();
      setSubmitting(true);

      await installMCPConnector({
        name: values.name,
        provider: 'custom',
        configuration: {
          command: values.command,
          args: values.args ? values.args.split(' ') : [],
          env: values.env ? JSON.parse(values.env) : {},
        },
        custom_command: values.command,
      });

      message.success(`Custom MCP server "${values.name}" registered`);
      setCustomModalVisible(false);
      customForm.resetFields();
      loadData();
    } catch (err: any) {
      if (err?.errorFields) return;
      message.error(err?.response?.data?.detail || 'Failed to create custom MCP');
    } finally {
      setSubmitting(false);
    }
  };

  // Test Connection (Ping)
  const handleTestConnection = async (connector: MCPConnector) => {
    setTestingMap((prev) => ({ ...prev, [connector.id]: true }));
    try {
      const res = await testMCPConnector(connector.id);
      message.success(res.data?.message || `Tested connection for ${connector.name}`);
      loadData();
    } catch (err: any) {
      message.error(err?.response?.data?.detail || `Connection test failed for ${connector.name}`);
    } finally {
      setTestingMap((prev) => ({ ...prev, [connector.id]: false }));
    }
  };

  // Test Channel Message
  const handleTestChannelMessage = async (provider: string, channelId: string) => {
    const key = `${provider}:${channelId}`;
    setTestingChannelMap((prev) => ({ ...prev, [key]: true }));
    try {
      await testChannelMessage({
        provider,
        channel_id: channelId,
        message: `🔔 Test notification from AI Agents Platform to ${channelId}`,
      });
      message.success(`Sent test message to ${channelId} (${provider})`);
    } catch (err) {
      message.error(`Failed to send test message to ${channelId}`);
    } finally {
      setTestingChannelMap((prev) => ({ ...prev, [key]: false }));
    }
  };

  // Uninstall
  const handleUninstall = async (connectorId: string) => {
    try {
      await deleteMCPConnector(connectorId);
      message.success('Connector uninstalled successfully');
      loadData();
    } catch (err: any) {
      message.error('Failed to uninstall connector');
    }
  };

  // View Tools Drawer
  const handleOpenToolsDrawer = async (connector: MCPConnector) => {
    setDrawerConnector(connector);
    setToolsDrawerVisible(true);
    setLoadingTools(true);
    try {
      const res = await getMCPTools(connector.id);
      setConnectorTools(res.data?.tools || []);
    } catch (err: any) {
      message.error('Failed to load connector tools');
    } finally {
      setLoadingTools(false);
    }
  };

  // Open Permissions Modal
  const handleOpenPermissions = (connector: MCPConnector) => {
    setPermConnector(connector);
    setPermModalVisible(true);
  };

  // Toggle Agent Permission
  const handleToggleAgentPerm = async (agentId: string, isAllowed: boolean) => {
    if (!permConnector) return;
    setUpdatingPerms(true);
    try {
      if (isAllowed) {
        await revokeMCPPermission({
          agent_id: agentId,
          connector_id: permConnector.id,
        });
        message.info(`Access revoked for agent`);
      } else {
        await grantMCPPermission({
          agent_id: agentId,
          connector_id: permConnector.id,
        });
        message.success(`Access granted for agent`);
      }
      const res = await getMCPPermissions();
      setPermissions(res.data?.permissions || []);
    } catch (err) {
      message.error('Failed to update agent permission');
    } finally {
      setUpdatingPerms(false);
    }
  };

  // Workflow Channel Binding Handlers
  const handleOpenBindingModal = (wf: PlatformWorkflow) => {
    setBindingWorkflow(wf);
    bindingForm.resetFields();

    if (wf.channel_binding) {
      bindingForm.setFieldsValue({
        provider: wf.channel_binding.provider,
        channel_id: wf.channel_binding.channel_id,
        trigger_enabled: wf.channel_binding.trigger_enabled,
        notify_mode: wf.channel_binding.notify_mode,
        message_template: wf.channel_binding.message_template,
      });
    } else {
      bindingForm.setFieldsValue({
        provider: 'slack',
        channel_id: '#pr-review',
        trigger_enabled: true,
        notify_mode: 'ON_COMPLETE',
      });
    }

    setBindingModalVisible(true);
  };

  const handleSaveBinding = async () => {
    if (!bindingWorkflow) return;
    try {
      const values = await bindingForm.validateFields();
      setBindingSubmitting(true);

      await bindWorkflowChannel(bindingWorkflow.id, {
        provider: values.provider,
        connector_id: values.provider,
        channel_id: values.channel_id,
        channel_name: values.channel_id,
        trigger_enabled: values.trigger_enabled,
        notify_mode: values.notify_mode,
        message_template: values.message_template,
      });

      message.success(`Bound workflow "${bindingWorkflow.name}" to channel ${values.channel_id}`);
      setBindingModalVisible(false);
      loadData();
    } catch (err: any) {
      if (err?.errorFields) return;
      message.error('Failed to save channel binding');
    } finally {
      setBindingSubmitting(false);
    }
  };

  const handleUnbindChannel = async (workflowId: string) => {
    try {
      await unbindWorkflowChannel(workflowId);
      message.success('Channel binding removed');
      loadData();
    } catch (err) {
      message.error('Failed to unbind channel');
    }
  };

  const handleRunWorkflow = async (record: PlatformWorkflow) => {
    setRunningWfMap((prev) => ({ ...prev, [record.id]: true }));
    try {
      const res = await executeWorkflow(record.id);
      message.success(`Workflow "${record.name}" finished execution! Status: ${res.data?.status || 'COMPLETED'}`);
      if (record.channel_binding) {
        message.info(`Sent completion alert to ${record.channel_binding.provider}:${record.channel_binding.channel_id}`);
      }
      loadData();
    } catch (err: any) {
      message.error(err?.response?.data?.detail || 'Failed to execute workflow');
    } finally {
      setRunningWfMap((prev) => ({ ...prev, [record.id]: false }));
    }
  };

  const handleDeleteWorkflow = async (workflowId: string) => {
    try {
      await deleteWorkflow(workflowId);
      message.success('Workflow deleted successfully');
      loadData();
    } catch (err) {
      message.error('Failed to delete workflow');
    }
  };

  // Categories list
  const categories = ['ALL', 'Developer Tools', 'Communication', 'Productivity & Planning', 'Databases', 'Data & Search'];

  // Filter catalog
  const filteredCatalog = catalog.filter((item) => {
    const matchesCat = selectedCategory === 'ALL' || item.category === selectedCategory;
    const matchesSearch =
      item.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.package.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesCat && matchesSearch;
  });

  // Extract authorized channels from Slack & Telegram connectors
  const slackConnectors = connectors.filter((c) => c.provider === 'slack' || c.id === 'slack');
  const telegramConnectors = connectors.filter((c) => c.provider === 'telegram' || c.id === 'telegram');
  const slackConnector = slackConnectors[0];
  const telegramConnector = telegramConnectors[0];

  const configuredSlackChannels = Array.from(
    new Set(
      slackConnectors.flatMap((c) => {
        const list: string[] = [];
        if (Array.isArray(c.configuration?.allowed_channels)) {
          list.push(...c.configuration.allowed_channels);
        }
        if (typeof c.configuration?.default_channel === 'string' && c.configuration.default_channel.trim()) {
          list.push(c.configuration.default_channel.trim());
        }
        return list;
      }).filter(Boolean)
    )
  );
  const availableSlackChannels: string[] =
    configuredSlackChannels.length > 0
      ? configuredSlackChannels
      : ['#general', '#dev-team', '#alerts', '#pr-review', '#workflows-feed'];

  const configuredTelegramChats = Array.from(
    new Set(
      telegramConnectors.flatMap((c) => {
        const list: string[] = [];
        if (Array.isArray(c.configuration?.allowed_channels)) {
          list.push(...c.configuration.allowed_channels);
        }
        if (typeof c.configuration?.chat_id === 'string' && c.configuration.chat_id.trim()) {
          list.push(c.configuration.chat_id.trim());
        }
        return list;
      }).filter(Boolean)
    )
  );
  const availableTelegramChats: string[] =
    configuredTelegramChats.length > 0
      ? configuredTelegramChats
      : ['@agents_office_alerts', '@workflow_dev_channel', '@pr_review_bot'];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Hero Header */}
      <div
        style={{
          background: 'radial-gradient(ellipse at top left, #1e1b4b 0%, #0d1117 70%)',
          borderRadius: '16px',
          border: '1px solid #30363d',
          padding: '24px 32px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
            <span
              style={{
                background: 'linear-gradient(135deg, #10b981 0%, #3b82f6 100%)',
                padding: '8px',
                borderRadius: '10px',
                display: 'inline-flex',
                color: '#fff',
                fontSize: '20px',
              }}
            >
              <ApiOutlined />
            </span>
            <h1 style={{ margin: 0, fontSize: '26px', fontWeight: 800, color: '#f0f6fc' }}>
              MCP Integrations & Workflow Channels
            </h1>
            <Tag color="#10b981" style={{ borderRadius: '12px', fontWeight: 600 }}>
              Model Context Protocol
            </Tag>
          </div>
          <p style={{ margin: 0, color: '#8b949e', fontSize: '14px', maxWidth: '720px' }}>
            Connect <strong>Git Repositories</strong>, <strong>Slack Channels</strong>, and <strong>Telegram Chats</strong>. Select authorized repositories and bind specific channels directly to autonomous workflows for triggering and real-time execution reporting.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
          <Button
            icon={<SyncOutlined spin={loading} />}
            onClick={loadData}
            style={{ background: '#161b22', borderColor: '#30363d', color: '#f0f6fc' }}
          >
            Refresh
          </Button>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => {
              customForm.resetFields();
              setCustomModalVisible(true);
            }}
            style={{
              background: '#10b981',
              borderColor: '#10b981',
              fontWeight: 600,
              boxShadow: '0 4px 14px rgba(16, 185, 129, 0.4)',
            }}
          >
            Add Custom MCP
          </Button>
        </div>
      </div>

      {/* Main Tabs */}
      <Tabs
        defaultActiveKey="catalog"
        tabBarStyle={{ borderBottom: '1px solid #21262d', marginBottom: '20px' }}
        items={[
          {
            key: 'catalog',
            label: (
              <span style={{ fontSize: '14px', fontWeight: 600 }}>
                <AppstoreOutlined /> Integrations Marketplace ({catalog.length})
              </span>
            ),
            children: (
              <div>
                {/* Search & Filter Bar */}
                <div
                  style={{
                    display: 'flex',
                    flexWrap: 'wrap',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    gap: '16px',
                    marginBottom: '20px',
                  }}
                >
                  <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                    {categories.map((cat) => (
                      <Button
                        key={cat}
                        size="small"
                        onClick={() => setSelectedCategory(cat)}
                        style={{
                          background: selectedCategory === cat ? '#10b981' : '#161b22',
                          borderColor: selectedCategory === cat ? '#10b981' : '#30363d',
                          color: selectedCategory === cat ? '#0a0d12' : '#8b949e',
                          fontWeight: selectedCategory === cat ? 700 : 500,
                          borderRadius: '16px',
                          padding: '0 14px',
                        }}
                      >
                        {cat}
                      </Button>
                    ))}
                  </div>

                  <Input
                    placeholder="Search integrations by name or package..."
                    prefix={<SearchOutlined style={{ color: '#8b949e' }} />}
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    allowClear
                    style={{ width: '320px', background: '#161b22', borderColor: '#30363d', color: '#f0f6fc' }}
                  />
                </div>

                {loading ? (
                  <div style={{ textAlign: 'center', padding: '60px 0' }}>
                    <Spin size="large" />
                  </div>
                ) : (
                  <Row gutter={[16, 16]}>
                    {filteredCatalog.map((item) => {
                      const installed = connectors.find(
                        (c) => c.provider === item.provider || c.id === item.id
                      );

                      const isGit = item.provider === 'github' || item.provider === 'git' || item.provider === 'gitlab';
                      const isSlack = item.provider === 'slack';
                      const isTelegram = item.provider === 'telegram';

                      const allowedRepos: string[] = installed?.configuration?.allowed_repos || [];
                      const allowedChannels: string[] = installed?.configuration?.allowed_channels || [];

                      return (
                        <Col xs={24} sm={12} lg={8} key={item.id}>
                          <Card
                            style={{
                              background: '#161b22',
                              border: installed ? '1px solid #10b981' : '1px solid #30363d',
                              borderRadius: '12px',
                              height: '100%',
                              display: 'flex',
                              flexDirection: 'column',
                              justifyContent: 'space-between',
                              boxShadow: installed ? '0 0 15px rgba(16, 185, 129, 0.15)' : 'none',
                              transition: 'all 0.2s ease',
                            }}
                            styles={{ body: { display: 'flex', flexDirection: 'column', height: '100%' } }}
                          >
                            <div>
                              {/* Header */}
                              <div
                                style={{
                                  display: 'flex',
                                  justifyContent: 'space-between',
                                  alignItems: 'flex-start',
                                  marginBottom: '14px',
                                }}
                              >
                                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                                  <div
                                    style={{
                                      width: '46px',
                                      height: '46px',
                                      borderRadius: '10px',
                                      background: '#0d1117',
                                      border: '1px solid #30363d',
                                      display: 'flex',
                                      alignItems: 'center',
                                      justifyContent: 'center',
                                    }}
                                  >
                                    {getProviderIcon(item.provider, 26)}
                                  </div>
                                  <div>
                                    <div style={{ fontSize: '16px', fontWeight: 700, color: '#f0f6fc' }}>
                                      {item.name}
                                    </div>
                                    <Tag
                                      color="blue"
                                      style={{
                                        fontSize: '10px',
                                        padding: '1px 6px',
                                        margin: '2px 0 0 0',
                                        borderRadius: '6px',
                                        background: 'rgba(59, 130, 246, 0.1)',
                                        borderColor: 'rgba(59, 130, 246, 0.3)',
                                      }}
                                    >
                                      {item.category}
                                    </Tag>
                                  </div>
                                </div>

                                {installed ? (
                                  <Tag
                                    color="success"
                                    icon={<CheckCircleOutlined />}
                                    style={{ borderRadius: '12px', padding: '2px 8px' }}
                                  >
                                    Connected
                                  </Tag>
                                ) : (
                                  <Tag style={{ borderRadius: '12px', background: '#21262d', color: '#8b949e', border: 'none' }}>
                                    Available
                                  </Tag>
                                )}
                              </div>

                              {/* Description */}
                              <p
                                style={{
                                  color: '#8b949e',
                                  fontSize: '13px',
                                  lineHeight: '1.5',
                                  minHeight: '40px',
                                  margin: '0 0 12px 0',
                                }}
                              >
                                {item.description}
                              </p>

                              {/* Package Name */}
                              <div
                                style={{
                                  background: '#0d1117',
                                  borderRadius: '6px',
                                  padding: '6px 10px',
                                  fontSize: '11px',
                                  fontFamily: 'monospace',
                                  color: '#a5b4fc',
                                  border: '1px solid #21262d',
                                  marginBottom: '12px',
                                  overflow: 'hidden',
                                  textOverflow: 'ellipsis',
                                  whiteSpace: 'nowrap',
                                }}
                              >
                                📦 {item.package}
                              </div>

                              {/* Authorized Repos or Channels Preview */}
                              {installed && isGit && allowedRepos.length > 0 && (
                                <div style={{ marginBottom: '12px', background: '#0d1117', padding: '8px', borderRadius: '6px', border: '1px solid #21262d' }}>
                                  <div style={{ fontSize: '11px', fontWeight: 600, color: '#38bdf8', marginBottom: '4px' }}>
                                    ✓ AUTHORIZED REPOSITORIES ({allowedRepos.length})
                                  </div>
                                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                                    {allowedRepos.slice(0, 3).map((repo) => (
                                      <Tag key={repo} color="cyan" style={{ fontSize: '10px' }}>
                                        {repo}
                                      </Tag>
                                    ))}
                                    {allowedRepos.length > 3 && (
                                      <span style={{ fontSize: '10px', color: '#8b949e' }}>+{allowedRepos.length - 3} more</span>
                                    )}
                                  </div>
                                </div>
                              )}

                              {installed && (isSlack || isTelegram) && allowedChannels.length > 0 && (
                                <div style={{ marginBottom: '12px', background: '#0d1117', padding: '8px', borderRadius: '6px', border: '1px solid #21262d' }}>
                                  <div style={{ fontSize: '11px', fontWeight: 600, color: '#f59e0b', marginBottom: '4px' }}>
                                    ✓ AUTHORIZED CHANNELS ({allowedChannels.length})
                                  </div>
                                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                                    {allowedChannels.slice(0, 3).map((ch) => (
                                      <Tag key={ch} color="gold" style={{ fontSize: '10px' }}>
                                        {ch}
                                      </Tag>
                                    ))}
                                  </div>
                                </div>
                              )}

                              {/* Sample Tools preview */}
                              <div style={{ marginBottom: '16px' }}>
                                <div style={{ fontSize: '11px', fontWeight: 600, color: '#6e7681', marginBottom: '6px' }}>
                                  EXPOSED MCP TOOLS ({item.default_tools.length})
                                </div>
                                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                                  {item.default_tools.slice(0, 3).map((t) => (
                                    <Tag
                                      key={t.name}
                                      style={{
                                        fontSize: '11px',
                                        background: '#1c2128',
                                        borderColor: '#30363d',
                                        color: '#34d399',
                                        borderRadius: '4px',
                                      }}
                                    >
                                      {t.name}
                                    </Tag>
                                  ))}
                                  {item.default_tools.length > 3 && (
                                    <Tag style={{ fontSize: '10px', background: '#161b22', border: 'none', color: '#8b949e' }}>
                                      +{item.default_tools.length - 3} more
                                    </Tag>
                                  )}
                                </div>
                              </div>
                            </div>

                            {/* Actions Footer */}
                            <div
                              style={{
                                borderTop: '1px solid #21262d',
                                paddingTop: '12px',
                                display: 'flex',
                                justifyContent: 'space-between',
                                alignItems: 'center',
                              }}
                            >
                              {installed ? (
                                <>
                                  <Button
                                    size="small"
                                    icon={<SettingOutlined />}
                                    onClick={() => handleOpenConnect(item, installed)}
                                    style={{ background: '#1c2128', borderColor: '#30363d', color: '#f0f6fc' }}
                                  >
                                    Configure
                                  </Button>
                                  <div style={{ display: 'flex', gap: '8px' }}>
                                    <Button
                                      size="small"
                                      icon={<ThunderboltOutlined />}
                                      loading={testingMap[installed.id]}
                                      onClick={() => handleTestConnection(installed)}
                                      style={{ background: '#064e3b', borderColor: '#059669', color: '#34d399' }}
                                    >
                                      Ping
                                    </Button>
                                    <Button
                                      size="small"
                                      icon={<ToolOutlined />}
                                      onClick={() => handleOpenToolsDrawer(installed)}
                                      style={{ background: '#1c2128', borderColor: '#30363d', color: '#60a5fa' }}
                                    >
                                      Tools
                                    </Button>
                                  </div>
                                </>
                              ) : (
                                <Button
                                  type="primary"
                                  block
                                  icon={<PlusOutlined />}
                                  onClick={() => handleOpenConnect(item)}
                                  style={{
                                    background: '#10b981',
                                    borderColor: '#10b981',
                                    fontWeight: 600,
                                  }}
                                >
                                  Connect Integration
                                </Button>
                              )}
                            </div>
                          </Card>
                        </Col>
                      );
                    })}
                  </Row>
                )}
              </div>
            ),
          },
          {
            key: 'installed',
            label: (
              <span style={{ fontSize: '14px', fontWeight: 600 }}>
                <CheckCircleOutlined /> Installed Connectors ({connectors.length})
              </span>
            ),
            children: (
              <div>
                {connectors.length === 0 ? (
                  <Card style={{ background: '#161b22', borderColor: '#30363d', textAlign: 'center', padding: '40px' }}>
                    <ApiOutlined style={{ fontSize: '42px', color: '#6e7681', marginBottom: '12px' }} />
                    <h3 style={{ color: '#f0f6fc' }}>No MCP Connectors Installed Yet</h3>
                    <p style={{ color: '#8b949e', maxWidth: '400px', margin: '0 auto 20px auto' }}>
                      Go to the marketplace tab to install Git, Trello, Telegram, or Slack connectors for your agents.
                    </p>
                  </Card>
                ) : (
                  <Row gutter={[16, 16]}>
                    {connectors.map((conn) => {
                      const isConnected = conn.status === 'CONNECTED';
                      const catDef = catalog.find((c) => c.provider === conn.provider || c.id === conn.id);
                      const permittedAgentCount = permissions.filter((p) => p.connector_id === conn.id).length;

                      const isGit = conn.provider === 'github' || conn.provider === 'git' || conn.provider === 'gitlab';
                      const isSlack = conn.provider === 'slack';
                      const isTelegram = conn.provider === 'telegram';
                      const allowedRepos: string[] = conn.configuration?.allowed_repos || [];
                      const allowedChannels: string[] = conn.configuration?.allowed_channels || [];

                      return (
                        <Col xs={24} md={12} lg={8} key={conn.id}>
                          <Card
                            style={{
                              background: '#161b22',
                              border: '1px solid #30363d',
                              borderRadius: '12px',
                              boxShadow: '0 4px 20px rgba(0,0,0,0.3)',
                            }}
                          >
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '12px' }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                                <div
                                  style={{
                                    width: '42px',
                                    height: '42px',
                                    borderRadius: '8px',
                                    background: '#0d1117',
                                    border: '1px solid #30363d',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                  }}
                                >
                                  {getProviderIcon(conn.provider, 22)}
                                </div>
                                <div>
                                  <div style={{ fontSize: '16px', fontWeight: 700, color: '#f0f6fc' }}>
                                    {conn.name}
                                  </div>
                                  <div style={{ fontSize: '11px', color: '#8b949e' }}>
                                    ID: <code style={{ color: '#38bdf8' }}>{conn.id}</code>
                                  </div>
                                </div>
                              </div>

                              <Badge
                                status={isConnected ? 'success' : 'error'}
                                text={
                                  <span style={{ fontSize: '12px', fontWeight: 600, color: isConnected ? '#52c41a' : '#ff4d4f' }}>
                                    {conn.status}
                                  </span>
                                }
                              />
                            </div>

                            {/* Config preview */}
                            <div
                              style={{
                                background: '#0d1117',
                                borderRadius: '8px',
                                padding: '10px',
                                marginBottom: '14px',
                                fontSize: '12px',
                                border: '1px solid #21262d',
                              }}
                            >
                              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                                <span style={{ color: '#8b949e' }}>Exposed Tools:</span>
                                <span style={{ color: '#34d399', fontWeight: 600 }}>{conn.tools_count || 0} registered</span>
                              </div>
                              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
                                <span style={{ color: '#8b949e' }}>Authorized Agents:</span>
                                <span style={{ color: '#60a5fa', fontWeight: 600 }}>
                                  {permittedAgentCount > 0 ? `${permittedAgentCount} agents` : 'All (Default)'}
                                </span>
                              </div>

                              {/* Allowed Repos */}
                              {isGit && allowedRepos.length > 0 && (
                                <div style={{ marginTop: '6px', paddingTop: '6px', borderTop: '1px solid #21262d' }}>
                                  <div style={{ color: '#38bdf8', fontSize: '11px', fontWeight: 600, marginBottom: '4px' }}>
                                    APPROVED REPOS ({allowedRepos.length}):
                                  </div>
                                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                                    {allowedRepos.map((r) => (
                                      <Tag key={r} color="cyan" style={{ fontSize: '10px' }}>
                                        {r}
                                      </Tag>
                                    ))}
                                  </div>
                                </div>
                              )}

                              {/* Allowed Channels */}
                              {(isSlack || isTelegram) && allowedChannels.length > 0 && (
                                <div style={{ marginTop: '6px', paddingTop: '6px', borderTop: '1px solid #21262d' }}>
                                  <div style={{ color: '#f59e0b', fontSize: '11px', fontWeight: 600, marginBottom: '4px' }}>
                                    APPROVED CHANNELS ({allowedChannels.length}):
                                  </div>
                                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                                    {allowedChannels.map((ch) => (
                                      <Tag key={ch} color="gold" style={{ fontSize: '10px' }}>
                                        {ch}
                                      </Tag>
                                    ))}
                                  </div>
                                </div>
                              )}
                            </div>

                            {/* Buttons */}
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', justifyContent: 'space-between' }}>
                              <div style={{ display: 'flex', gap: '6px' }}>
                                <Button
                                  size="small"
                                  icon={<ThunderboltOutlined />}
                                  loading={testingMap[conn.id]}
                                  onClick={() => handleTestConnection(conn)}
                                  style={{ background: '#064e3b', borderColor: '#059669', color: '#34d399' }}
                                >
                                  Test
                                </Button>
                                <Button
                                  size="small"
                                  icon={<ToolOutlined />}
                                  onClick={() => handleOpenToolsDrawer(conn)}
                                  style={{ background: '#1c2128', borderColor: '#30363d', color: '#60a5fa' }}
                                >
                                  Tools
                                </Button>
                                <Button
                                  size="small"
                                  icon={<SafetyCertificateOutlined />}
                                  onClick={() => handleOpenPermissions(conn)}
                                  style={{ background: '#1c2128', borderColor: '#30363d', color: '#c084fc' }}
                                >
                                  Access
                                </Button>
                              </div>

                              <div style={{ display: 'flex', gap: '6px' }}>
                                {catDef && (
                                  <Button
                                    size="small"
                                    icon={<SettingOutlined />}
                                    onClick={() => handleOpenConnect(catDef, conn)}
                                    style={{ background: '#1c2128', borderColor: '#30363d', color: '#f0f6fc' }}
                                  />
                                )}
                                <Popconfirm
                                  title="Uninstall this MCP connector?"
                                  description="This will remove the integration and its registered tools."
                                  onConfirm={() => handleUninstall(conn.id)}
                                  okText="Uninstall"
                                  cancelText="Cancel"
                                  okButtonProps={{ danger: true }}
                                >
                                  <Button
                                    size="small"
                                    danger
                                    icon={<DeleteOutlined />}
                                    style={{ background: '#1c2128', borderColor: '#30363d' }}
                                  />
                                </Popconfirm>
                              </div>
                            </div>
                          </Card>
                        </Col>
                      );
                    })}
                  </Row>
                )}
              </div>
            ),
          },
          {
            key: 'channels',
            label: (
              <span style={{ fontSize: '14px', fontWeight: 600 }}>
                <LinkOutlined /> Workflow Channels ({workflows.filter((w) => w.channel_binding).length} Active / {workflows.length} Total)
              </span>
            ),
            children: (
              <div>
                {/* Information banner */}
                <div
                  style={{
                    background: '#161b22',
                    border: '1px solid #30363d',
                    borderRadius: '12px',
                    padding: '16px 20px',
                    marginBottom: '20px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <MessageOutlined style={{ fontSize: '24px', color: '#ECB22E' }} />
                    <div>
                      <div style={{ fontWeight: 700, color: '#f0f6fc', fontSize: '15px' }}>
                        Bind Workflows to Communication Channels (Slack / Telegram)
                      </div>
                      <div style={{ color: '#8b949e', fontSize: '12px' }}>
                        Connected channels can trigger workflows (incoming commands/webhooks) and receive automatic execution reports and status updates.
                      </div>
                    </div>
                  </div>

                  <Button
                    type="primary"
                    icon={<RocketOutlined />}
                    onClick={() => setCreateWfModalVisible(true)}
                    style={{
                      background: 'linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%)',
                      borderColor: '#3b82f6',
                      fontWeight: 700,
                      height: '38px',
                      borderRadius: '8px',
                      boxShadow: '0 4px 12px rgba(37, 99, 235, 0.3)',
                    }}
                  >
                    + Create Workflow (Auto YAML)
                  </Button>
                </div>

                <Table
                  dataSource={workflows}
                  rowKey="id"
                  pagination={false}
                  scroll={{ x: 1650 }}
                  style={{ background: '#161b22', borderRadius: '12px', border: '1px solid #30363d' }}
                  columns={[
                    {
                      title: 'Workflow Name',
                      dataIndex: 'name',
                      key: 'name',
                      width: 230,
                      render: (text: string, record: PlatformWorkflow) => (
                        <div>
                          <div style={{ fontWeight: 700, color: '#f0f6fc' }}>{text}</div>
                          <div style={{ fontSize: '11px', color: '#8b949e' }}>ID: {record.id}</div>
                        </div>
                      ),
                    },
                    {
                      title: 'Department',
                      key: 'department',
                      width: 150,
                      render: (_: any, record: PlatformWorkflow) => {
                        const dept = departments.find((d) => d.id === record.department_id);
                        if (dept) {
                          return (
                            <Tag color="geekblue" style={{ fontSize: '11px', borderRadius: '4px' }}>
                              📁 {dept.name}
                            </Tag>
                          );
                        }
                        if (record.department_id) {
                          return (
                            <Tag style={{ background: '#21262d', color: '#8b949e', fontSize: '11px' }}>
                              {record.department_id}
                            </Tag>
                          );
                        }
                        return <span style={{ color: '#6e7681', fontSize: '11px' }}>Global</span>;
                      },
                    },
                    {
                      title: 'Bound Channel',
                      key: 'channel',
                      width: 160,
                      render: (_: any, record: PlatformWorkflow) => {
                        const b = record.channel_binding;
                        if (!b) {
                          return <Tag style={{ background: '#21262d', color: '#8b949e', border: 'none' }}>None (Unbound)</Tag>;
                        }
                        const isSlack = b.provider === 'slack';
                        return (
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <Tag
                              icon={isSlack ? <SlackOutlined /> : <SendOutlined />}
                              color={isSlack ? 'warning' : 'processing'}
                              style={{ fontWeight: 600, borderRadius: '6px', padding: '2px 8px' }}
                            >
                              {b.channel_id}
                            </Tag>
                          </div>
                        );
                      },
                    },
                    {
                      title: 'Trigger Enabled',
                      key: 'trigger',
                      width: 140,
                      render: (_: any, record: PlatformWorkflow) => {
                        const b = record.channel_binding;
                        if (!b) return <span style={{ color: '#6e7681' }}>-</span>;
                        return b.trigger_enabled ? (
                          <Tag color="success" icon={<ThunderboltOutlined />}>
                            Trigger Active
                          </Tag>
                        ) : (
                          <Tag style={{ background: '#21262d', color: '#8b949e' }}>Disabled</Tag>
                        );
                      },
                    },
                    {
                      title: 'Reporting Mode',
                      key: 'notify',
                      width: 150,
                      render: (_: any, record: PlatformWorkflow) => {
                        const b = record.channel_binding;
                        if (!b) return <span style={{ color: '#6e7681' }}>-</span>;
                        switch (b.notify_mode) {
                          case 'ALWAYS':
                            return <Tag color="cyan">Always</Tag>;
                          case 'ON_COMPLETE':
                            return <Tag color="green">On Complete</Tag>;
                          case 'ON_FAILURE':
                            return <Tag color="red">On Failure</Tag>;
                          default:
                            return <Tag style={{ background: '#21262d', color: '#8b949e' }}>Read Only</Tag>;
                        }
                      },
                    },
                    {
                      title: 'Configured MCP Scope',
                      key: 'mcp_scope',
                      width: 180,
                      render: (_: any, record: PlatformWorkflow) => {
                        let mcps: string[] = [];
                        try {
                          const def = JSON.parse(record.definition_json);
                          mcps = def.mcp_servers || [];
                        } catch (e) {}
                        if (mcps.length === 0) {
                          return <span style={{ color: '#6e7681', fontSize: '11px' }}>All Connectors</span>;
                        }
                        return (
                          <Space size="small" wrap>
                            {mcps.map((m) => (
                              <Tag key={m} color={m === 'github' ? 'purple' : m === 'telegram' ? 'blue' : 'cyan'} style={{ fontSize: '10px', margin: 0 }}>
                                <ToolOutlined /> {m.toUpperCase()}
                              </Tag>
                            ))}
                          </Space>
                        );
                      },
                    },
                    {
                      title: 'Connected Skills',
                      key: 'skills',
                      width: 180,
                      render: (_: any, record: PlatformWorkflow) => {
                        let wfSkills: any[] = [];
                        try {
                          const def = JSON.parse(record.definition_json);
                          wfSkills = def.skills || [];
                        } catch (e) {}
                        if (wfSkills.length === 0) {
                          return <span style={{ color: '#6e7681', fontSize: '11px' }}>None</span>;
                        }
                        return (
                          <Space size="small" wrap>
                            {wfSkills.map((sk: any, idx: number) => (
                              <Tooltip key={sk.id || idx} title={sk.location ? `Location: ${sk.location}` : sk.description}>
                                <Tag color="gold" style={{ fontSize: '10px', margin: 0 }}>
                                  <FileTextOutlined /> {sk.name || sk.id}
                                </Tag>
                              </Tooltip>
                            ))}
                          </Space>
                        );
                      },
                    },
                    {
                      title: 'Dedicated Runner Agent',
                      key: 'runner_agent',
                      width: 190,
                      render: (_: any, record: PlatformWorkflow) => {
                        let runnerAgentId = '';
                        try {
                          const def = JSON.parse(record.definition_json);
                          runnerAgentId = def.runner_agent_id || def.agent_id || `wf-agent-${record.id}`;
                        } catch (e) {
                          runnerAgentId = `wf-agent-${record.id}`;
                        }
                        return (
                          <Tooltip title="Autonomous background agent dedicated to this workflow. Decoupled from office canvas desks.">
                            <Tag color="purple" style={{ fontSize: '11px', padding: '2px 8px', borderRadius: '6px' }}>
                              ⚡ {runnerAgentId}
                            </Tag>
                          </Tooltip>
                        );
                      },
                    },
                    {
                      title: 'Canvas Graph',
                      key: 'canvas',
                      width: 140,
                      render: (_: any, record: PlatformWorkflow) => {
                        let stepsCount = 0;
                        try {
                          const def = JSON.parse(record.definition_json);
                          stepsCount = (def.steps || []).length;
                        } catch (e) {}
                        return (
                          <Button
                            size="small"
                            icon={<ApartmentOutlined />}
                            onClick={() => {
                              setCanvasWorkflow(record);
                              setCanvasModalVisible(true);
                            }}
                            style={{ background: '#1e1b4b', borderColor: '#6366f1', color: '#a5b4fc', fontSize: '11px' }}
                          >
                            🎨 Canvas ({stepsCount})
                          </Button>
                        );
                      },
                    },
                    {
                      title: 'Actions',
                      key: 'actions',
                      width: 270,
                      render: (_: any, record: PlatformWorkflow) => {
                        const b = record.channel_binding;
                        return (
                          <Space>
                            <Button
                              size="small"
                              type="primary"
                              icon={<CaretRightOutlined />}
                              loading={runningWfMap[record.id]}
                              onClick={() => handleRunWorkflow(record)}
                              style={{ background: '#059669', borderColor: '#059669', color: '#fff', fontWeight: 600 }}
                            >
                              Run
                            </Button>

                            <Button
                              size="small"
                              type={b ? 'default' : 'primary'}
                              icon={<LinkOutlined />}
                              onClick={() => handleOpenBindingModal(record)}
                              style={
                                !b
                                  ? { background: '#2563eb', borderColor: '#2563eb' }
                                  : { background: '#1c2128', borderColor: '#30363d', color: '#f0f6fc' }
                              }
                            >
                              {b ? 'Edit Channel' : 'Bind Channel'}
                            </Button>

                            {b && (
                              <>
                                <Button
                                  size="small"
                                  icon={<SendOutlined />}
                                  loading={testingChannelMap[`${b.provider}:${b.channel_id}`]}
                                  onClick={() => handleTestChannelMessage(b.provider, b.channel_id)}
                                  style={{ background: '#064e3b', borderColor: '#059669', color: '#34d399' }}
                                >
                                  Ping
                                </Button>
                                <Popconfirm
                                  title="Unbind this channel from the workflow?"
                                  description="This will disconnect the channel without deleting the workflow."
                                  onConfirm={() => handleUnbindChannel(record.id)}
                                  okText="Unbind"
                                  cancelText="Cancel"
                                >
                                  <Button
                                    size="small"
                                    icon={<DisconnectOutlined style={{ color: '#f59e0b' }} />}
                                    style={{ background: '#1c2128', borderColor: '#30363d', color: '#f59e0b' }}
                                    title="Unbind Channel"
                                  >
                                    Unbind
                                  </Button>
                                </Popconfirm>
                              </>
                            )}

                            <Popconfirm
                              title="Delete this workflow completely?"
                              description="This will permanently delete the workflow and its run history."
                              onConfirm={() => handleDeleteWorkflow(record.id)}
                              okText="Delete"
                              cancelText="Cancel"
                              okButtonProps={{ danger: true }}
                            >
                              <Button size="small" danger icon={<DeleteOutlined />} title="Delete Workflow" />
                            </Popconfirm>
                          </Space>
                        );
                      },
                    },
                  ]}
                />
              </div>
            ),
          },
        ]}
      />

      {/* Connect / Configure Modal */}
      <Modal
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            {selectedCatalogItem && getProviderIcon(selectedCatalogItem.provider, 22)}
            <span>
              {editingConnector ? `Configure ${selectedCatalogItem?.name}` : `Connect ${selectedCatalogItem?.name}`}
            </span>
          </div>
        }
        open={modalVisible}
        onCancel={() => setModalVisible(false)}
        onOk={handleSaveConnector}
        confirmLoading={submitting}
        okText={editingConnector ? 'Save Changes' : 'Install & Connect'}
        width={620}
      >
        <p style={{ color: '#8b949e', fontSize: '13px', marginBottom: '16px' }}>
            {selectedCatalogItem?.description}
          </p>

          <Form form={form} layout="vertical">
            <Form.Item
              name="name"
              label={<span style={{ color: '#f0f6fc' }}>Connector Name</span>}
              rules={[{ required: true, message: 'Please enter a connector name' }]}
            >
              <Input placeholder="e.g. My GitHub Account" style={{ background: '#0d1117', borderColor: '#30363d', color: '#f0f6fc' }} />
            </Form.Item>

            {selectedCatalogItem &&
              Object.entries(selectedCatalogItem.config_schema)
                .filter(([key]) => key !== 'chat_id' && key !== 'default_channel')
                .map(([key, field]) => {
                const isTokenField =
                  (key === 'token' || key === 'personal_access_token' || key === 'api_key') &&
                  (selectedCatalogItem.provider === 'github' || selectedCatalogItem.provider === 'git' || selectedCatalogItem.provider === 'gitlab');

                return (
                  <Form.Item
                    key={key}
                    name={key}
                    label={<span style={{ color: '#f0f6fc' }}>{field.label}</span>}
                    rules={[{ required: field.required, message: `${field.label} is required` }]}
                    extra={
                      isTokenField ? (
                        <div style={{ marginTop: '6px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <span style={{ color: '#8b949e', fontSize: '11px' }}>
                            Query remote repositories using this Personal Access Token
                          </span>
                          <Button
                            size="small"
                            type="primary"
                            icon={<BranchesOutlined />}
                            loading={fetchingResources}
                            onClick={handleFetchTokenRepositories}
                            style={{ background: '#10b981', borderColor: '#10b981', color: '#0d1117', fontWeight: 600, fontSize: '11px', height: '26px' }}
                          >
                            Fetch Token Repositories
                          </Button>
                        </div>
                      ) : undefined
                    }
                  >
                    {field.type === 'password' ? (
                      <Input.Password
                        placeholder={field.placeholder}
                        style={{ background: '#0d1117', borderColor: '#30363d', color: '#f0f6fc' }}
                      />
                    ) : (
                      <Input
                        placeholder={field.placeholder}
                        style={{ background: '#0d1117', borderColor: '#30363d', color: '#f0f6fc' }}
                      />
                    )}
                  </Form.Item>
                );
              })}

            {/* Git Repos Selection Section */}
            {selectedCatalogItem && (selectedCatalogItem.provider === 'github' || selectedCatalogItem.provider === 'git' || selectedCatalogItem.provider === 'gitlab') && (
              <div
                style={{
                  marginTop: '16px',
                  padding: '16px',
                  background: '#0d1117',
                  borderRadius: '8px',
                  border: '1px solid #30363d',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px', flexWrap: 'wrap', gap: '8px' }}>
                  <div style={{ fontWeight: 700, color: '#38bdf8', fontSize: '13px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <BranchesOutlined /> Authorized Repositories
                  </div>
                  <Button
                    size="small"
                    type="primary"
                    icon={<SyncOutlined spin={fetchingResources} />}
                    loading={fetchingResources}
                    onClick={handleFetchTokenRepositories}
                    style={{ background: '#10b981', borderColor: '#10b981', color: '#0d1117', fontWeight: 600 }}
                  >
                    Fetch Token Repositories
                  </Button>
                </div>

                {resourceDiscoveryError && (
                  <Alert
                    type="error"
                    showIcon
                    message="Token Authentication / Discovery Error"
                    description={resourceDiscoveryError}
                    closable
                    onClose={() => setResourceDiscoveryError(null)}
                    style={{ marginBottom: '12px', background: 'rgba(239, 68, 68, 0.12)', border: '1px solid #ef4444' }}
                  />
                )}

                <div style={{ color: '#8b949e', fontSize: '12px', marginBottom: '12px' }}>
                  Select which local and remote repositories the platform agents are authorized to access and modify:
                </div>

                {/* Currently Approved / Selected Repos */}
                <div
                  style={{
                    background: '#161b22',
                    border: '1px solid #30363d',
                    borderRadius: '8px',
                    padding: '10px 12px',
                    marginBottom: '14px',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                    <span style={{ fontSize: '12px', fontWeight: 700, color: '#38bdf8' }}>
                      ✓ Selected Repositories ({selectedResources.length}):
                    </span>
                    {selectedResources.length > 0 && (
                      <Button
                        size="small"
                        type="link"
                        danger
                        onClick={() => setSelectedResources([])}
                        style={{ padding: 0, height: 'auto', fontSize: '11px' }}
                      >
                        Clear All
                      </Button>
                    )}
                  </div>
                  {selectedResources.length === 0 ? (
                    <div style={{ color: '#8b949e', fontSize: '12px', fontStyle: 'italic' }}>
                      No repositories selected. Click on available repositories below or add a custom repo name.
                    </div>
                  ) : (
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                      {selectedResources.map((repoName) => (
                        <Tag
                          key={repoName}
                          closable
                          onClose={(e) => {
                            e.preventDefault();
                            setSelectedResources(selectedResources.filter((r) => r !== repoName));
                          }}
                          color="cyan"
                          style={{
                            fontSize: '12px',
                            padding: '3px 8px',
                            borderRadius: '6px',
                            fontWeight: 600,
                            display: 'inline-flex',
                            alignItems: 'center',
                          }}
                        >
                          {repoName}
                        </Tag>
                      ))}
                    </div>
                  )}
                </div>

                <div style={{ color: '#8b949e', fontSize: '12px', marginBottom: '8px' }}>
                  Available Repositories (click to toggle):
                </div>

                {discoveredResources.length > 0 && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '180px', overflowY: 'auto', marginBottom: '12px', paddingRight: '4px' }}>
                    {discoveredResources.map((repo: any) => {
                      const repoName = repo.full_name || repo.name;
                      const isChecked = selectedResources.includes(repoName) || selectedResources.includes(repo.name);
                      const isPrivate = repo.private !== undefined ? Boolean(repo.private) : false;
                      const defaultBranch = repo.default_branch || 'main';

                      return (
                        <div
                          key={repoName}
                          onClick={() => {
                            if (isChecked) {
                              setSelectedResources(selectedResources.filter((r) => r !== repoName && r !== repo.name));
                            } else {
                              setSelectedResources([...selectedResources, repoName]);
                            }
                          }}
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            padding: '8px 12px',
                            background: isChecked ? 'rgba(56, 189, 248, 0.12)' : '#161b22',
                            border: isChecked ? '1px solid #38bdf8' : '1px solid #21262d',
                            borderRadius: '6px',
                            cursor: 'pointer',
                            transition: 'all 0.15s ease',
                            gap: '10px',
                          }}
                        >
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flex: 1, minWidth: 0 }}>
                            <Checkbox checked={isChecked} />
                            <div style={{ display: 'flex', flexDirection: 'column', minWidth: 0 }}>
                              <span style={{ color: '#f0f6fc', fontWeight: 600, fontSize: '13px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                {repo.full_name || repo.name}
                              </span>
                              {repo.name && repo.full_name && repo.name !== repo.full_name && (
                                <span style={{ color: '#8b949e', fontSize: '11px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                  {repo.name}
                                </span>
                              )}
                            </div>
                          </div>

                          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexShrink: 0 }}>
                            {repo.private !== undefined && (
                              <Tag
                                color={isPrivate ? 'gold' : 'green'}
                                icon={isPrivate ? <LockOutlined /> : <UnlockOutlined />}
                                style={{ fontSize: '11px', margin: 0, fontWeight: 600 }}
                              >
                                {isPrivate ? 'Private' : 'Public'}
                              </Tag>
                            )}
                            <Tag color="blue" icon={<BranchesOutlined />} style={{ fontSize: '11px', margin: 0 }}>
                              {defaultBranch}
                            </Tag>
                            {repo.is_local && (
                              <Tag color="cyan" style={{ fontSize: '10px', margin: 0 }}>
                                Local
                              </Tag>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}

                {/* Add Custom Repo */}
                <div style={{ display: 'flex', gap: '8px' }}>
                  <Input
                    size="small"
                    placeholder="Add custom repository (e.g. owner/my-repo)"
                    value={customResourceInput}
                    onChange={(e) => setCustomResourceInput(e.target.value)}
                    onPressEnter={handleAddCustomResource}
                    style={{ background: '#161b22', borderColor: '#30363d', color: '#f0f6fc' }}
                  />
                  <Button size="small" type="primary" onClick={handleAddCustomResource}>
                    Add
                  </Button>
                </div>
              </div>
            )}

            {/* Slack Channels Selection Section */}
            {selectedCatalogItem && selectedCatalogItem.provider === 'slack' && (
              <div
                style={{
                  marginTop: '16px',
                  padding: '16px',
                  background: '#0d1117',
                  borderRadius: '8px',
                  border: '1px solid #30363d',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                  <div style={{ fontWeight: 700, color: '#f59e0b', fontSize: '13px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <SlackOutlined /> Authorized Channels Array
                  </div>
                  <Tag color="gold" style={{ fontSize: '11px', margin: 0 }}>
                    Multi-Channel
                  </Tag>
                </div>
                <div style={{ color: '#8b949e', fontSize: '12px', marginBottom: '12px' }}>
                  Manage authorized Slack channels array for workflows and alerting:
                </div>

                {/* 1. Add Custom Channel Input & Button at TOP */}
                <div style={{ display: 'flex', gap: '8px', marginBottom: '14px' }}>
                  <Input
                    size="middle"
                    placeholder="Add Slack channel to array (e.g. #general, #incidents, C0123456789)"
                    value={customResourceInput}
                    onChange={(e) => setCustomResourceInput(e.target.value)}
                    onPressEnter={handleAddCustomResource}
                    style={{ background: '#161b22', borderColor: '#30363d', color: '#f0f6fc' }}
                  />
                  <Button
                    type="primary"
                    icon={<PlusOutlined />}
                    onClick={handleAddCustomResource}
                    style={{ background: '#ECB22E', borderColor: '#ECB22E', color: '#0d1117', fontWeight: 600, whiteSpace: 'nowrap' }}
                  >
                    + Add Channel
                  </Button>
                </div>

                {/* 2. Configured Channels Array Box */}
                <div
                  style={{
                    background: '#161b22',
                    border: '1px solid #30363d',
                    borderRadius: '8px',
                    padding: '12px',
                    marginBottom: '14px',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                    <span style={{ fontSize: '12px', fontWeight: 700, color: '#f59e0b', display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <CheckCircleOutlined style={{ color: '#f59e0b' }} />
                      Configured Channels Array ({selectedResources.length}):
                    </span>
                    {selectedResources.length > 0 && (
                      <Button
                        size="small"
                        type="link"
                        danger
                        onClick={() => setSelectedResources([])}
                        style={{ padding: 0, height: 'auto', fontSize: '11px' }}
                      >
                        Clear All
                      </Button>
                    )}
                  </div>
                  {selectedResources.length === 0 ? (
                    <div style={{ color: '#8b949e', fontSize: '12px', fontStyle: 'italic' }}>
                      No channels added yet. Type a channel above and click "+ Add Channel" or select from suggestions below.
                    </div>
                  ) : (
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                      {selectedResources.map((chName, idx) => (
                        <Tag
                          key={chName}
                          closable
                          onClose={(e) => {
                            e.preventDefault();
                            setSelectedResources(selectedResources.filter((c) => c !== chName));
                          }}
                          color="gold"
                          style={{
                            fontSize: '12px',
                            padding: '3px 8px',
                            borderRadius: '6px',
                            fontWeight: 600,
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '4px',
                          }}
                        >
                          <span style={{ opacity: 0.65, fontSize: '10px' }}>#{idx + 1}</span>
                          <span>{chName}</span>
                        </Tag>
                      ))}
                    </div>
                  )}
                </div>

                {/* 3. Quick-toggle suggested Slack channels */}
                <div style={{ color: '#8b949e', fontSize: '12px', marginBottom: '8px' }}>
                  Suggested Slack channels (click to toggle):
                </div>

                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                  {(discoveredResources.length > 0
                    ? discoveredResources.map((c: any) => c.id || c.name)
                    : ['#general', '#dev-team', '#alerts', '#pr-review', '#workflows-feed', '#deployments']
                  ).map((chName: string) => {
                    const isChecked = selectedResources.includes(chName);
                    return (
                      <Tag.CheckableTag
                        key={chName}
                        checked={isChecked}
                        onChange={(checked) => {
                          if (checked) {
                            setSelectedResources([...selectedResources, chName]);
                          } else {
                            setSelectedResources(selectedResources.filter((c) => c !== chName));
                          }
                        }}
                        style={{
                          fontSize: '12px',
                          padding: '4px 10px',
                          borderRadius: '6px',
                          background: isChecked ? '#ECB22E' : '#161b22',
                          color: isChecked ? '#000' : '#8b949e',
                          border: '1px solid #30363d',
                        }}
                      >
                        {chName}
                      </Tag.CheckableTag>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Telegram Chats Selection Section */}
            {selectedCatalogItem && selectedCatalogItem.provider === 'telegram' && (
              <div
                style={{
                  marginTop: '16px',
                  padding: '16px',
                  background: '#0d1117',
                  borderRadius: '8px',
                  border: '1px solid #30363d',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                  <div style={{ fontWeight: 700, color: '#38bdf8', fontSize: '13px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <SendOutlined /> Authorized Chats & Channels Array
                  </div>
                  <Tag color="blue" style={{ fontSize: '11px', margin: 0 }}>
                    Multi-Channel
                  </Tag>
                </div>
                <div style={{ color: '#8b949e', fontSize: '12px', marginBottom: '12px' }}>
                  Manage authorized Telegram channels and chats array for workflows and alerting:
                </div>

                {/* 1. Add Custom Channel Input & Button at TOP */}
                <div style={{ display: 'flex', gap: '8px', marginBottom: '14px' }}>
                  <Input
                    size="middle"
                    placeholder="Add channel or chat ID to array (e.g. Hermes_test, @my_channel, -100123456789)"
                    value={customResourceInput}
                    onChange={(e) => setCustomResourceInput(e.target.value)}
                    onPressEnter={handleAddCustomResource}
                    style={{ background: '#161b22', borderColor: '#30363d', color: '#f0f6fc' }}
                  />
                  <Button
                    type="primary"
                    icon={<PlusOutlined />}
                    onClick={handleAddCustomResource}
                    style={{ background: '#229ED9', borderColor: '#229ED9', color: '#fff', fontWeight: 600, whiteSpace: 'nowrap' }}
                  >
                    + Add Channel
                  </Button>
                </div>

                {/* 2. Configured Channels Array Box */}
                <div
                  style={{
                    background: '#161b22',
                    border: '1px solid #30363d',
                    borderRadius: '8px',
                    padding: '12px',
                    marginBottom: '14px',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                    <span style={{ fontSize: '12px', fontWeight: 700, color: '#38bdf8', display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <CheckCircleOutlined style={{ color: '#38bdf8' }} />
                      Configured Channels Array ({selectedResources.length}):
                    </span>
                    {selectedResources.length > 0 && (
                      <Button
                        size="small"
                        type="link"
                        danger
                        onClick={() => setSelectedResources([])}
                        style={{ padding: 0, height: 'auto', fontSize: '11px' }}
                      >
                        Clear All
                      </Button>
                    )}
                  </div>
                  {selectedResources.length === 0 ? (
                    <div style={{ color: '#8b949e', fontSize: '12px', fontStyle: 'italic' }}>
                      No channels added yet. Type a chat ID or @channel above and click "+ Add Channel" or select from suggestions below.
                    </div>
                  ) : (
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                      {selectedResources.map((chatName, idx) => (
                        <Tag
                          key={chatName}
                          closable
                          onClose={(e) => {
                            e.preventDefault();
                            setSelectedResources(selectedResources.filter((c) => c !== chatName));
                          }}
                          color="blue"
                          style={{
                            fontSize: '12px',
                            padding: '3px 8px',
                            borderRadius: '6px',
                            fontWeight: 600,
                            background: 'rgba(56, 189, 248, 0.15)',
                            border: '1px solid #38bdf8',
                            color: '#38bdf8',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '4px',
                          }}
                        >
                          <span style={{ opacity: 0.65, fontSize: '10px' }}>#{idx + 1}</span>
                          <span>{chatName}</span>
                        </Tag>
                      ))}
                    </div>
                  )}
                </div>

                {/* 3. Quick-toggle suggested Telegram channels */}
                <div style={{ color: '#8b949e', fontSize: '12px', marginBottom: '8px' }}>
                  Suggested Telegram channels (click to toggle):
                </div>

                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                  {(discoveredResources.length > 0
                    ? discoveredResources.map((c: any) => c.id || c.name)
                    : ['@agents_office_alerts', '@workflow_dev_channel', '@pr_review_bot']
                  ).map((chatName: string) => {
                    const isChecked = selectedResources.includes(chatName);
                    return (
                      <Tag.CheckableTag
                        key={chatName}
                        checked={isChecked}
                        onChange={(checked) => {
                          if (checked) {
                            setSelectedResources([...selectedResources, chatName]);
                          } else {
                            setSelectedResources(selectedResources.filter((c) => c !== chatName));
                          }
                        }}
                        style={{
                          fontSize: '12px',
                          padding: '4px 10px',
                          borderRadius: '6px',
                          background: isChecked ? '#229ED9' : '#161b22',
                          color: isChecked ? '#fff' : '#8b949e',
                          border: '1px solid #30363d',
                        }}
                      >
                        {chatName}
                      </Tag.CheckableTag>
                    );
                  })}
                </div>
              </div>
            )}
          </Form>
      </Modal>

      {/* Workflow Channel Binding Modal */}
      <Modal
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <LinkOutlined style={{ color: '#10b981' }} />
            <span>Bind Channel to Workflow: {bindingWorkflow?.name}</span>
          </div>
        }
        open={bindingModalVisible}
        onCancel={() => setBindingModalVisible(false)}
        footer={[
          bindingWorkflow?.channel_binding ? (
            <Popconfirm
              key="unbind"
              title="Unbind this channel from the workflow?"
              description="This will disconnect the channel without deleting the workflow."
              onConfirm={async () => {
                if (bindingWorkflow) {
                  await handleUnbindChannel(bindingWorkflow.id);
                  setBindingModalVisible(false);
                }
              }}
              okText="Unbind"
              cancelText="Cancel"
            >
              <Button danger icon={<DisconnectOutlined />} style={{ float: 'left' }}>
                Unbind Channel
              </Button>
            </Popconfirm>
          ) : null,
          <Button key="cancel" onClick={() => setBindingModalVisible(false)}>
            Cancel
          </Button>,
          <Button key="submit" type="primary" loading={bindingSubmitting} onClick={handleSaveBinding}>
            Save Channel Binding
          </Button>,
        ]}
        width={540}
      >
        <p style={{ color: '#8b949e', fontSize: '13px', marginBottom: '16px' }}>
            Choose an authorized Slack or Telegram channel to connect to this workflow. You can enable incoming command triggers and configure automatic reporting.
          </p>

          <Form form={bindingForm} layout="vertical">
            <Form.Item
              name="provider"
              label={<span style={{ color: '#f0f6fc' }}>Communication Provider</span>}
              rules={[{ required: true }]}
            >
              <Radio.Group style={{ width: '100%' }}>
                <Row gutter={12}>
                  <Col span={12}>
                    <Radio.Button value="slack" style={{ width: '100%', textAlign: 'center', height: '42px', lineHeight: '40px' }}>
                      <SlackOutlined style={{ color: '#ECB22E', marginRight: '8px' }} /> Slack
                    </Radio.Button>
                  </Col>
                  <Col span={12}>
                    <Radio.Button value="telegram" style={{ width: '100%', textAlign: 'center', height: '42px', lineHeight: '40px' }}>
                      <SendOutlined style={{ color: '#229ED9', marginRight: '8px' }} /> Telegram
                    </Radio.Button>
                  </Col>
                </Row>
              </Radio.Group>
            </Form.Item>

            <Form.Item noStyle shouldUpdate={(prev, curr) => prev.provider !== curr.provider}>
              {({ getFieldValue }) => {
                const prov = getFieldValue('provider') || 'slack';
                const baseChannels = prov === 'telegram' ? availableTelegramChats : availableSlackChannels;
                const extraList = prov === 'telegram' ? extraBindingChannels.telegram : extraBindingChannels.slack;
                const allChannels = Array.from(new Set([...baseChannels, ...extraList])).filter(Boolean);
                const currentConnector = prov === 'telegram' ? telegramConnector : slackConnector;

                return (
                  <div>
                    <Form.Item
                      name="channel_id"
                      label={<span style={{ color: '#f0f6fc' }}>Target Channel / Chat</span>}
                      rules={[{ required: true, message: 'Please select a channel' }]}
                      style={{ marginBottom: '8px' }}
                    >
                      <Select
                        showSearch
                        filterOption={(input, option) =>
                          (option?.value ?? '').toString().toLowerCase().includes(input.toLowerCase())
                        }
                        style={{ width: '100%' }}
                        placeholder={`Select configured ${prov === 'telegram' ? 'Telegram' : 'Slack'} channel`}
                        options={allChannels.map((ch) => ({
                          label: (
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                              <span>{ch}</span>
                              <Tag color={prov === 'telegram' ? 'blue' : 'gold'} style={{ fontSize: '10px', marginRight: 0 }}>
                                {prov}
                              </Tag>
                            </div>
                          ),
                          value: ch,
                        }))}
                      />
                    </Form.Item>

                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        padding: '6px 10px',
                        background: '#161b22',
                        borderRadius: '6px',
                        border: '1px solid #30363d',
                        marginBottom: '16px',
                        fontSize: '12px',
                      }}
                    >
                      <span style={{ color: '#8b949e' }}>
                        {allChannels.length} configured channel{allChannels.length === 1 ? '' : 's'} in {prov} array
                      </span>
                      <Space size="small">
                        <Input
                          size="small"
                          placeholder={prov === 'telegram' ? '+ Quick add @chat' : '+ Quick add #channel'}
                          value={quickAddBindingInput}
                          onChange={(e) => setQuickAddBindingInput(e.target.value)}
                          onPressEnter={() => {
                            if (!quickAddBindingInput.trim()) return;
                            const newChan = quickAddBindingInput.trim();
                            setExtraBindingChannels((prev) => ({
                              ...prev,
                              [prov]: [...prev[prov as 'slack' | 'telegram'], newChan],
                            }));
                            bindingForm.setFieldValue('channel_id', newChan);
                            setQuickAddBindingInput('');
                            message.success(`Added ${newChan} and selected`);
                          }}
                          style={{ width: 140, background: '#0d1117', borderColor: '#30363d', color: '#f0f6fc', fontSize: '11px' }}
                        />
                        <Button
                          size="small"
                          onClick={() => {
                            if (!quickAddBindingInput.trim()) return;
                            const newChan = quickAddBindingInput.trim();
                            setExtraBindingChannels((prev) => ({
                              ...prev,
                              [prov]: [...prev[prov as 'slack' | 'telegram'], newChan],
                            }));
                            bindingForm.setFieldValue('channel_id', newChan);
                            setQuickAddBindingInput('');
                            message.success(`Added ${newChan} and selected`);
                          }}
                          style={{ fontSize: '11px', height: '24px' }}
                        >
                          Add
                        </Button>
                        {currentConnector && (
                          <Button
                            type="link"
                            size="small"
                            onClick={() => {
                              setBindingModalVisible(false);
                              const catItem = catalog.find((i) => i.provider === prov) || {
                                id: prov,
                                name: prov === 'telegram' ? 'Telegram Bot' : 'Slack',
                                provider: prov,
                                category: 'Communication',
                                description: '',
                                icon: prov,
                                config_schema: {},
                                default_tools: [],
                                package: '',
                              };
                              handleOpenConnect(catItem, currentConnector);
                            }}
                            style={{ padding: '0 4px', fontSize: '11px', color: '#38bdf8' }}
                          >
                            ⚙️ Configure MCP
                          </Button>
                        )}
                      </Space>
                    </div>
                  </div>
                );
              }}
            </Form.Item>

            <Divider style={{ borderColor: '#21262d' }} />

            <Form.Item
              name="trigger_enabled"
              valuePropName="checked"
            >
              <Checkbox style={{ color: '#f0f6fc' }}>
                <span style={{ fontWeight: 600 }}>⚡ Allow incoming messages in this channel to trigger this workflow</span>
              </Checkbox>
            </Form.Item>

            <Form.Item
              name="notify_mode"
              label={<span style={{ color: '#f0f6fc' }}>Outgoing Notification Mode</span>}
              rules={[{ required: true }]}
            >
              <Select
                style={{ width: '100%' }}
                options={[
                  { label: '✓ Post on Complete only', value: 'ON_COMPLETE' },
                  { label: '⚠️ Post on Failure only', value: 'ON_FAILURE' },
                  { label: '📢 Always', value: 'ALWAYS' },
                  { label: '🔒 Read-only (no responses sent)', value: 'NONE' },
                ]}
              />
            </Form.Item>

            <Form.Item
              name="message_template"
              label={<span style={{ color: '#f0f6fc' }}>Custom Message Template (Optional)</span>}
            >
              <Input.TextArea
                rows={2}
                placeholder="e.g. 🚀 Workflow {{workflow_name}} finished with status: {{status}}"
                style={{ background: '#0d1117', borderColor: '#30363d', color: '#f0f6fc' }}
              />
            </Form.Item>
          </Form>
      </Modal>

      {/* Custom MCP Modal */}
      <Modal
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <ApiOutlined style={{ color: '#10b981' }} />
            <span>Register Custom MCP Server</span>
          </div>
        }
        open={customModalVisible}
        onCancel={() => setCustomModalVisible(false)}
        onOk={handleSaveCustom}
        confirmLoading={submitting}
        okText="Register Server"
        width={560}
      >
        <p style={{ color: '#8b949e', fontSize: '13px', marginBottom: '16px' }}>
            Register any local or external MCP stdio server command (e.g. <code>npx -y @modelcontextprotocol/server-...</code> or <code>python mcp_server.py</code>).
          </p>

          <Form form={customForm} layout="vertical">
            <Form.Item
              name="name"
              label={<span style={{ color: '#f0f6fc' }}>Connector Name</span>}
              rules={[{ required: true, message: 'Please enter a name' }]}
            >
              <Input placeholder="e.g. My Custom Weather MCP" style={{ background: '#0d1117', borderColor: '#30363d', color: '#f0f6fc' }} />
            </Form.Item>

            <Form.Item
              name="command"
              label={<span style={{ color: '#f0f6fc' }}>Execution Command</span>}
              rules={[{ required: true, message: 'Command is required' }]}
            >
              <Input placeholder="e.g. npx -y @modelcontextprotocol/server-postgres" style={{ background: '#0d1117', borderColor: '#30363d', color: '#f0f6fc' }} />
            </Form.Item>

            <Form.Item
              name="args"
              label={<span style={{ color: '#f0f6fc' }}>CLI Arguments (Space Separated)</span>}
            >
              <Input placeholder="e.g. --port 5000 /path/to/db" style={{ background: '#0d1117', borderColor: '#30363d', color: '#f0f6fc' }} />
            </Form.Item>

            <Form.Item
              name="env"
              label={<span style={{ color: '#f0f6fc' }}>Environment Variables (JSON)</span>}
            >
              <Input.TextArea
                rows={3}
                placeholder='{"API_KEY": "secret_123"}'
                style={{ background: '#0d1117', borderColor: '#30363d', color: '#f0f6fc', fontFamily: 'monospace' }}
              />
            </Form.Item>
          </Form>
      </Modal>

      {/* Tools Drawer */}
      <Drawer
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <ToolOutlined style={{ color: '#10b981' }} />
            <span>Tools exposed by {drawerConnector?.name}</span>
          </div>
        }
        placement="right"
        width={480}
        onClose={() => setToolsDrawerVisible(false)}
        open={toolsDrawerVisible}
        styles={{
          body: { background: '#0a0d12', color: '#f0f6fc', padding: '16px' },
          header: { background: '#161b22', borderBottom: '1px solid #21262d', color: '#f0f6fc' },
        }}
      >
        {loadingTools ? (
          <div style={{ textAlign: 'center', padding: '40px 0' }}>
            <Spin />
          </div>
        ) : connectorTools.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '40px 0', color: '#8b949e' }}>
            No tools registered under this connector.
          </div>
        ) : (
          <List
            dataSource={connectorTools}
            renderItem={(tool) => (
              <List.Item
                style={{
                  border: '1px solid #21262d',
                  borderRadius: '8px',
                  background: '#161b22',
                  marginBottom: '10px',
                  padding: '12px',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'flex-start',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', width: '100%', alignItems: 'center' }}>
                  <code style={{ fontSize: '13px', fontWeight: 700, color: '#34d399' }}>
                    {tool.name}
                  </code>
                  <Tag style={{ background: '#0d1117', borderColor: '#30363d', color: '#8b949e', fontSize: '10px' }}>
                    MCP Tool
                  </Tag>
                </div>
                <p style={{ margin: '6px 0 0 0', color: '#8b949e', fontSize: '12px' }}>
                  {tool.description || 'No description provided.'}
                </p>
              </List.Item>
            )}
          />
        )}
      </Drawer>

      {/* Agent Permissions Modal */}
      <Modal
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <SafetyCertificateOutlined style={{ color: '#c084fc' }} />
            <span>Agent Access Control — {permConnector?.name}</span>
          </div>
        }
        open={permModalVisible}
        onCancel={() => setPermModalVisible(false)}
        footer={null}
        width={500}
      >
        <p style={{ color: '#8b949e', fontSize: '13px', marginBottom: '16px' }}>
            Control which agents are authorized to invoke tools from this MCP connector.
          </p>

          <List
            dataSource={agents}
            renderItem={(agent) => {
              const isAllowed = permissions.some(
                (p) => p.agent_id === agent.id && p.connector_id === permConnector?.id
              );

              return (
                <List.Item
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    padding: '10px 14px',
                    background: '#0d1117',
                    borderRadius: '8px',
                    border: '1px solid #21262d',
                    marginBottom: '8px',
                  }}
                >
                  <div>
                    <div style={{ color: '#f0f6fc', fontWeight: 600, fontSize: '14px' }}>
                      {agent.name}
                    </div>
                    <div style={{ color: '#8b949e', fontSize: '11px' }}>
                      {(agent as any).role || agent.name} &bull; {agent.department || 'General'}
                    </div>
                  </div>

                  <Button
                    size="small"
                    loading={updatingPerms}
                    onClick={() => handleToggleAgentPerm(agent.id, isAllowed)}
                    style={{
                      background: isAllowed ? 'rgba(16, 185, 129, 0.2)' : '#161b22',
                      borderColor: isAllowed ? '#10b981' : '#30363d',
                      color: isAllowed ? '#34d399' : '#8b949e',
                      fontWeight: 600,
                    }}
                  >
                    {isAllowed ? '✓ Granted' : '+ Grant Access'}
                  </Button>
                </List.Item>
              );
            }}
          />
      </Modal>

      {/* Workflow Canvas Graph Modal */}
      <Modal
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <ApartmentOutlined style={{ color: '#38bdf8' }} />
            <span>Workflow Execution Canvas Graph: {canvasWorkflow?.name}</span>
          </div>
        }
        open={canvasModalVisible}
        onCancel={() => setCanvasModalVisible(false)}
        footer={[
          <Button key="close" onClick={() => setCanvasModalVisible(false)} style={{ background: '#21262d', color: '#f0f6fc' }}>
            Close
          </Button>,
        ]}
        width={1000}
      >
        {canvasWorkflow && (() => {
          let parsedSteps: any[] = [];
          let parsedSkills: any[] = [];
          let parsedMcps: any[] = [];
          try {
            const def = JSON.parse(canvasWorkflow.definition_json);
            parsedSteps = def.steps || [];
            parsedSkills = def.skills || [];
            parsedMcps = def.mcp_servers || [];
          } catch (e) {}

          return (
            <WorkflowCanvasGraph
              workflowName={canvasWorkflow.name}
              steps={parsedSteps}
              channelBinding={canvasWorkflow.channel_binding}
              skills={parsedSkills}
              allowedMcps={parsedMcps}
              height={480}
            />
          );
        })()}
      </Modal>

      {/* Create Workflow & Auto YAML Modal */}
      <CreateWorkflowModal
        open={createWfModalVisible}
        onClose={() => setCreateWfModalVisible(false)}
        onSuccess={() => loadData()}
        defaultChannelProvider={telegramConnector ? 'telegram' : 'slack'}
        defaultChannelId={
          telegramConnector?.configuration?.allowed_channels?.[0] ||
          telegramConnector?.configuration?.chat_id ||
          'Hermes_test'
        }
        departmentId={activeDepartmentId || departments[0]?.id}
      />
    </div>
  );
};

export default McpHubPage;
