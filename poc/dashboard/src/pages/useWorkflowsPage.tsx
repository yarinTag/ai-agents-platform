import { removeWorkflowStep } from '../services/workflowDefinitions';
import { useState, useEffect, useCallback } from 'react';
import { Table, Modal, Input, message, Drawer, Form } from 'antd';
import { getWorkflows, updateWorkflow, deleteWorkflow, executeWorkflow, executeWorkflowPlayground, getWorkflowExecution, getWorkflowExecutions, getMCPConnectors } from '../services/api';
import { PlatformWorkflow, WorkflowExecution, MCPConnector } from '../types/mcp';
import { WorkflowCanvasStep } from '../components/workflows/WorkflowCanvasGraph';

export const useWorkflowsPage = () => {
  const [workflows, setWorkflows] = useState<PlatformWorkflow[]>([]);
  const [executions, setExecutions] = useState<WorkflowExecution[]>([]);
  const [connectors, setConnectors] = useState<MCPConnector[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [activeTab, setActiveTab] = useState<string>('workflows');

  // Modals & Drawers state
  const [editingWorkflow, setEditingWorkflow] = useState<PlatformWorkflow | null>(null);
  const [historyWorkflow, setHistoryWorkflow] = useState<PlatformWorkflow | null>(null);
  const [createModalOpen, setCreateModalOpen] = useState<boolean>(false);
  const [canvasModalOpen, setCanvasModalOpen] = useState<boolean>(false);
  const [selectedWorkflow, setSelectedWorkflow] = useState<PlatformWorkflow | null>(null);

  // Run Modal state
  const [playgroundMode, setPlaygroundMode] = useState(false);
  const [runModalOpen, setRunModalOpen] = useState<boolean>(false);
  const [runningWorkflow, setRunningWorkflow] = useState<PlatformWorkflow | null>(null);
  const [runForm] = Form.useForm();
  const [executing, setExecuting] = useState<boolean>(false);

  // View Definition state
  const [viewDefModalOpen, setViewDefModalOpen] = useState<boolean>(false);

  // Execution Detail Drawer
  const [detailDrawerOpen, setDetailDrawerOpen] = useState<boolean>(false);
  const [selectedExecution, setSelectedExecution] = useState<WorkflowExecution | null>(null);

  // Load Workflows and Executions
  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [wfRes, execRes, connRes] = await Promise.allSettled([
        getWorkflows(),
        getWorkflowExecutions(undefined, 100),
        getMCPConnectors(),
      ]);
      if (wfRes.status === 'fulfilled') {
        const wfData = wfRes.value.data as any;
        setWorkflows(Array.isArray(wfData) ? wfData : (wfData?.workflows || []));
      } else {
        console.warn('Failed to load workflows:', wfRes.reason);
      }
      if (execRes.status === 'fulfilled') {
        const execData = execRes.value.data as any;
        setExecutions(Array.isArray(execData) ? execData : (execData?.executions || []));
      } else {
        console.warn('Failed to load workflow executions:', execRes.reason);
      }
      if (connRes.status === 'fulfilled') {
        const connData = connRes.value.data as any;
        const list = Array.isArray(connData) ? connData : (connData?.connectors || []);
        setConnectors(list);
      } else {
        console.warn('Failed to load MCP connectors:', connRes.reason);
      }
    } catch (err: any) {
      console.error('Failed to load workflows data:', err);
      message.error('Failed to fetch workflows data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 10000); // Polling every 10s for active runs
    return () => clearInterval(interval);
  }, [loadData]);

  useEffect(() => {
    if (!detailDrawerOpen || !selectedExecution?.id) return;
    let disposed = false;
    const refresh = async () => {
      try {
        const response = await getWorkflowExecution(selectedExecution.id);
        if (!disposed) setSelectedExecution(response.data);
      } catch {
        if (!disposed) message.error('Failed to refresh execution details');
      }
    };
    void refresh();
    const interval = setInterval(refresh, 3000);
    return () => { disposed = true; clearInterval(interval); };
  }, [detailDrawerOpen, selectedExecution?.id]);

  // Handle Delete
  const handleDelete = async (id: string) => {
    try {
      await deleteWorkflow(id);
      message.success('Workflow deleted successfully');
      loadData();
    } catch (err: any) {
      message.error(err.response?.data?.detail || 'Failed to delete workflow');
    }
  };

  // Open Run Modal
  const openRunModal = (wf: PlatformWorkflow, playground = false) => {
    setPlaygroundMode(playground);
    setRunningWorkflow(wf);
    runForm.setFieldsValue({
      payload: '{}',
      force_rerun: false,
    });
    setRunModalOpen(true);
  };

  // Submit Run Workflow
  const handleExecute = async () => {
    if (!runningWorkflow) return;
    try {
      const values = await runForm.validateFields();
      let parsedPayload: Record<string, any> = {};
      if (values.payload && values.payload.trim()) {
        try {
          parsedPayload = JSON.parse(values.payload);
          if (!parsedPayload || typeof parsedPayload !== 'object' || Array.isArray(parsedPayload)) {
            message.error('Input must be a JSON object');
            return;
          }
        } catch (e) {
          message.error('Invalid JSON payload');
          return;
        }
      }

      setExecuting(true);
      const res = playgroundMode
        ? await executeWorkflowPlayground(runningWorkflow.id, parsedPayload)
        : await executeWorkflow(
        runningWorkflow.id,
        parsedPayload,
        true,
        values.force_rerun ?? false
      );

      const execData = res.data;
      if (execData.is_deduplicated) {
        message.info(
          execData.message ||
            'Duplicate execution detected. Reusing existing active or completed run.'
        );
      } else if (execData.status === 'QUEUED') {
        message.success(
          execData.message || 'Workflow execution queued for processing.'
        );
      } else {
        message.success(`Workflow completed with status: ${execData.status}`);
      }

      setRunModalOpen(false);
      if (playgroundMode) {
        setSelectedExecution(execData);
        setDetailDrawerOpen(true);
        setActiveTab('executions');
      }
      loadData();
    } catch (err: any) {
      message.error(err.response?.data?.detail || 'Execution failed');
    } finally {
      setExecuting(false);
    }
  };

  // Copy helper
  const copyToClipboard = (text: string, label: string) => {
    navigator.clipboard.writeText(text);
    message.success(`${label} copied to clipboard`);
  };

  // Extract parsed DAG steps for Canvas Graph
  const getParsedWorkflowSteps = (wf: PlatformWorkflow): WorkflowCanvasStep[] => {
    try {
      const def = JSON.parse(wf.definition_json);
      return (def.steps || []).map((s: any) => ({
        key: s.key || s.id,
        name: s.name || s.key,
        agent_id: s.agent_id || s.agentId || 'software-architect',
        prompt_template: s.prompt_template || s.prompt || '',
        depends_on: s.depends_on || s.dependsOn || [],
        timeout_seconds: s.timeout_seconds || 300,
        skills: s.skills || [],
        mcp_servers: s.mcp_servers || s.mcpServers || [],
      }));
    } catch (e) {
      return [];
    }
  };

  // Delete a step directly from the Workflow Canvas Graph
  const handleDeleteStepFromCanvas = async (stepKey: string) => {
    if (!selectedWorkflow) return;
    try {
      const updated = removeWorkflowStep(selectedWorkflow.definition_json, stepKey);
      const newJson = updated.definitionJson;
      const res = await updateWorkflow(selectedWorkflow.id, {
        definition_json: newJson,
        expected_revision: selectedWorkflow.revision || 1,
        change_summary: `Removed step ${stepKey}`,
      });
      const updatedWf = res.data || {
        ...selectedWorkflow,
        definition_json: newJson,
      };
      setSelectedWorkflow(updatedWf);
      setWorkflows((prev) => prev.map((w) => (w.id === updatedWf.id ? updatedWf : w)));
      message.success(`Removed step "${updated.deletedName}"`);
    } catch (err: any) {
      message.error(err.response?.data?.detail || 'Failed to delete step');
    }
  };

  // Find telegram/slack connector safely
  const telegramConnector = Array.isArray(connectors)
    ? connectors.find((c) => c?.provider === 'telegram' || c?.id === 'telegram')
    : undefined;

  // Stats calculation safely
  const totalWorkflows = Array.isArray(workflows) ? workflows.length : 0;
  const activeWorkflows = Array.isArray(workflows) ? workflows.filter((w) => w?.is_active).length : 0;
  const queuedRuns = Array.isArray(executions) ? executions.filter((e) => e?.status === 'QUEUED').length : 0;
  const deduplicatedRuns = Array.isArray(executions) ? executions.filter((e) => e?.is_deduplicated).length : 0;

  // Workflows Table Columns
  return {
    workflows,
    setWorkflows,
    executions,
    setExecutions,
    connectors,
    setConnectors,
    loading,
    setLoading,
    activeTab,
    setActiveTab,
    editingWorkflow,
    setEditingWorkflow,
    historyWorkflow,
    setHistoryWorkflow,
    createModalOpen,
    setCreateModalOpen,
    canvasModalOpen,
    setCanvasModalOpen,
    selectedWorkflow,
    setSelectedWorkflow,
    playgroundMode,
    setPlaygroundMode,
    runModalOpen,
    setRunModalOpen,
    runningWorkflow,
    setRunningWorkflow,
    runForm,
    executing,
    setExecuting,
    viewDefModalOpen,
    setViewDefModalOpen,
    detailDrawerOpen,
    setDetailDrawerOpen,
    selectedExecution,
    setSelectedExecution,
    loadData,
    handleDelete,
    openRunModal,
    handleExecute,
    copyToClipboard,
    getParsedWorkflowSteps,
    handleDeleteStepFromCanvas,
    telegramConnector,
    totalWorkflows,
    activeWorkflows,
    queuedRuns,
    deduplicatedRuns,
  };
};
