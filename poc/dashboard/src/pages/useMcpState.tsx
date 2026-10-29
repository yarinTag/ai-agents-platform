import { useRequestGeneration } from '../hooks/useRequestGeneration';
import { readResource } from './resourceLoading';
import { useEffect, useState } from 'react';
import { Modal, Form, message, Drawer } from 'antd';
import { getMCPCatalog, getMCPConnectors, getAgents, getMCPPermissions, getWorkflows } from '../services/api';
import { MCPCatalogItem, MCPConnector, MCPTool, AgentMCPPermission, PlatformWorkflow } from '../types/mcp';
import { Agent } from '../types/agent';
import { useAuth } from '../context/AuthContext';

export const useMcpState = () => {
  const { departments, activeDepartmentId, organization } = useAuth();
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

  const [resourceErrors, setResourceErrors] = useState<{
    catalog: string | null; connectors: string | null; agents: string | null;
    permissions: string | null; workflows: string | null;
  }>({ catalog: null, connectors: null, agents: null, permissions: null, workflows: null });

  const { begin, invalidate } = useRequestGeneration();
  const loadData = async () => {
    const current = begin();
    if (!current()) return;
    try {
      setLoading(true);
      const [catalogError, connectorsError, agentsError, permissionsError, workflowsError] = await Promise.all([
        readResource(getMCPCatalog(), response => { if (current()) setCatalog(response.data?.catalog || []); }, 'MCP catalog'),
        readResource(getMCPConnectors(), response => { if (current()) setConnectors(response.data?.connectors || []); }, 'Connectors'),
        readResource(getAgents(), response => { if (current()) setAgents(response.data || []); }, 'Agents'),
        readResource(getMCPPermissions(), response => { if (current()) setPermissions(response.data?.permissions || []); }, 'MCP permissions'),
        readResource(getWorkflows(), response => { if (current()) setWorkflows(response.data || []); }, 'Workflows'),
      ]);
      if (!current()) return;
      setResourceErrors({
        catalog: catalogError, connectors: connectorsError, agents: agentsError,
        permissions: permissionsError, workflows: workflowsError,
      });
    } catch (err: any) {
      message.error('Failed to load MCP integrations');
      console.error(err);
    } finally {
      if (current()) setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    return invalidate;
  }, [organization?.id, activeDepartmentId, invalidate]);

  // Map icons
  return {
    departments,
    activeDepartmentId,
    loading,
    resourceErrors,
    setLoading,
    catalog,
    setCatalog,
    connectors,
    setConnectors,
    agents,
    setAgents,
    permissions,
    setPermissions,
    workflows,
    setWorkflows,
    searchQuery,
    setSearchQuery,
    selectedCategory,
    setSelectedCategory,
    modalVisible,
    setModalVisible,
    selectedCatalogItem,
    setSelectedCatalogItem,
    editingConnector,
    setEditingConnector,
    submitting,
    setSubmitting,
    form,
    discoveredResources,
    setDiscoveredResources,
    selectedResources,
    setSelectedResources,
    customResourceInput,
    setCustomResourceInput,
    fetchingResources,
    setFetchingResources,
    resourceDiscoveryError,
    setResourceDiscoveryError,
    customModalVisible,
    setCustomModalVisible,
    customForm,
    toolsDrawerVisible,
    setToolsDrawerVisible,
    drawerConnector,
    setDrawerConnector,
    connectorTools,
    setConnectorTools,
    loadingTools,
    setLoadingTools,
    permModalVisible,
    setPermModalVisible,
    permConnector,
    setPermConnector,
    updatingPerms,
    setUpdatingPerms,
    bindingModalVisible,
    setBindingModalVisible,
    bindingWorkflow,
    setBindingWorkflow,
    bindingSubmitting,
    setBindingSubmitting,
    createWfModalVisible,
    setCreateWfModalVisible,
    canvasModalVisible,
    setCanvasModalVisible,
    canvasWorkflow,
    setCanvasWorkflow,
    bindingForm,
    quickAddBindingInput,
    setQuickAddBindingInput,
    extraBindingChannels,
    setExtraBindingChannels,
    testingMap,
    setTestingMap,
    testingChannelMap,
    setTestingChannelMap,
    runningWfMap,
    setRunningWfMap,
    loadData,
  };
};
