import { Modal, Form, message, Drawer } from 'antd';
import { installMCPConnector, updateMCPConnector, deleteMCPConnector, testMCPConnector, getMCPTools, getMCPPermissions, grantMCPPermission, revokeMCPPermission, discoverMCPResources, testChannelMessage } from '../services/api';
import { MCPCatalogItem, MCPConnector } from '../types/mcp';
import { Agent } from '../types/agent';
import type { useMcpState } from './useMcpState';

export const useMcpConnectorActions = (state: Pick<
  ReturnType<typeof useMcpState>,
  | 'resourceErrors'
  | 'catalog'
  | 'agents'
  | 'permissions'
  | 'setPermissions'
  | 'setModalVisible'
  | 'selectedCatalogItem'
  | 'setSelectedCatalogItem'
  | 'editingConnector'
  | 'setEditingConnector'
  | 'setSubmitting'
  | 'form'
  | 'setDiscoveredResources'
  | 'selectedResources'
  | 'setSelectedResources'
  | 'customResourceInput'
  | 'setCustomResourceInput'
  | 'setFetchingResources'
  | 'setResourceDiscoveryError'
  | 'setCustomModalVisible'
  | 'customForm'
  | 'setToolsDrawerVisible'
  | 'setDrawerConnector'
  | 'setConnectorTools'
  | 'setLoadingTools'
  | 'setPermModalVisible'
  | 'permConnector'
  | 'setPermConnector'
  | 'setUpdatingPerms'
  | 'setTestingMap'
  | 'setTestingChannelMap'
  | 'loadData'
>) => {
  const {
    resourceErrors,
    catalog,
    agents,
    permissions,
    setPermissions,
    setModalVisible,
    selectedCatalogItem,
    setSelectedCatalogItem,
    editingConnector,
    setEditingConnector,
    setSubmitting,
    form,
    setDiscoveredResources,
    selectedResources,
    setSelectedResources,
    customResourceInput,
    setCustomResourceInput,
    setFetchingResources,
    setResourceDiscoveryError,
    setCustomModalVisible,
    customForm,
    setToolsDrawerVisible,
    setDrawerConnector,
    setConnectorTools,
    setLoadingTools,
    setPermModalVisible,
    permConnector,
    setPermConnector,
    setUpdatingPerms,
    setTestingMap,
    setTestingChannelMap,
    loadData,
  } = state;
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
    if (resourceErrors.catalog || resourceErrors.connectors) { message.error('Required MCP data is unavailable. Refresh and retry.'); return; }
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
    if (resourceErrors.connectors) { message.error('Required MCP data is unavailable. Refresh and retry.'); return; }
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
    if (resourceErrors.permissions || resourceErrors.agents || resourceErrors.connectors) { message.error('Required MCP data is unavailable. Refresh and retry.'); return; }
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
  return {
    handleFetchResources,
    handleFetchTokenRepositories,
    handleOpenConnect,
    handleAddCustomResource,
    handleSaveConnector,
    handleSaveCustom,
    handleTestConnection,
    handleTestChannelMessage,
    handleUninstall,
    handleOpenToolsDrawer,
    handleOpenPermissions,
    handleToggleAgentPerm,
  };
};
