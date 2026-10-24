import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import {
  Table,
  Button,
  Modal,
  Tag,
  Space,
  Card,
  Row,
  Col,
  Statistic,
  Tabs,
  Input,
  Tooltip,
  Popconfirm,
  message,
  Switch,
  Drawer,
  Badge,
  Form,
  Alert,
} from 'antd';
import {
  ApartmentOutlined,
  PlayCircleOutlined,
  PlusOutlined,
  ReloadOutlined,
  DeleteOutlined,
  CodeOutlined,
  EyeOutlined,
  ThunderboltOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ClockCircleOutlined,
  SyncOutlined,
  SafetyCertificateOutlined,
  SlackOutlined,
  SendOutlined,
  BranchesOutlined,
  CopyOutlined,
} from '@ant-design/icons';
import {
  getWorkflows,
  updateWorkflow,
  convertWorkflowFormat,
  deleteWorkflow,
  executeWorkflow,
  executeWorkflowPlayground,
  getWorkflowExecution,
  getWorkflowExecutions,
  getMCPConnectors,
} from '../services/api';
import { PlatformWorkflow, WorkflowExecution, MCPConnector } from '../types/mcp';
import { CreateWorkflowModal } from '../components/workflows/CreateWorkflowModal';
import {
  WorkflowCanvasGraph,
  WorkflowCanvasStep,
} from '../components/workflows/WorkflowCanvasGraph';

const { TextArea } = Input;

export const WorkflowsPage: React.FC = () => {
  const [workflows, setWorkflows] = useState<PlatformWorkflow[]>([]);
  const [executions, setExecutions] = useState<WorkflowExecution[]>([]);
  const [connectors, setConnectors] = useState<MCPConnector[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [activeTab, setActiveTab] = useState<string>('workflows');

  // Modals & Drawers state
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
      const def = JSON.parse(selectedWorkflow.definition_json);
      const existingSteps: any[] = def.steps || [];
      const deletedStep = existingSteps.find((s: any) => (s.key || s.id) === stepKey);
      const parentKeys: string[] = deletedStep?.depends_on || [];

      const updatedSteps = existingSteps
        .filter((s: any) => (s.key || s.id) !== stepKey)
        .map((s: any) => {
          const deps: string[] = s.depends_on || [];
          if (!deps.includes(stepKey)) return s;
          const nextDeps = Array.from(
            new Set([
              ...deps.filter((d) => d !== stepKey),
              ...parentKeys.filter((p) => p !== (s.key || s.id)),
            ])
          );
          return { ...s, depends_on: nextDeps };
        });

      const updatedDef = { ...def, steps: updatedSteps };
      const newJson = JSON.stringify(updatedDef, null, 2);
      let newYaml = selectedWorkflow.definition_yaml;
      try {
        const convRes = await convertWorkflowFormat(newJson, 'yaml');
        if (convRes.data?.converted) {
          newYaml = convRes.data.converted;
        }
      } catch (e) {
        // Keep existing yaml if conversion endpoint fails
      }

      const res = await updateWorkflow(selectedWorkflow.id, {
        definition_json: newJson,
        definition_yaml: newYaml,
      });
      const updatedWf = res.data || {
        ...selectedWorkflow,
        definition_json: newJson,
        definition_yaml: newYaml,
      };
      setSelectedWorkflow(updatedWf);
      setWorkflows((prev) => prev.map((w) => (w.id === updatedWf.id ? updatedWf : w)));
      message.success(`Removed step "${deletedStep?.name || stepKey}"`);
    } catch (err: any) {
      message.error(err.response?.data?.detail || 'Failed to delete step');
    }
  };

  // Find telegram/slack connector safely
  const telegramConnector = Array.isArray(connectors)
    ? connectors.find((c) => c?.connector_id === 'telegram')
    : undefined;

  // Stats calculation safely
  const totalWorkflows = Array.isArray(workflows) ? workflows.length : 0;
  const activeWorkflows = Array.isArray(workflows) ? workflows.filter((w) => w?.is_active).length : 0;
  const queuedRuns = Array.isArray(executions) ? executions.filter((e) => e?.status === 'QUEUED').length : 0;
  const deduplicatedRuns = Array.isArray(executions) ? executions.filter((e) => e?.is_deduplicated).length : 0;

  // Workflows Table Columns
  const workflowColumns = [
    {
      title: 'Workflow Name',
      key: 'name',
      render: (_: any, record: PlatformWorkflow) => (
        <div>
          <Space orientation="horizontal" size={6}>
            <ApartmentOutlined style={{ color: '#8b5cf6', fontSize: 16 }} />
            <strong style={{ color: '#f0f6fc', fontSize: 14 }}>{record.name}</strong>
          </Space>
          <div style={{ color: '#8b949e', fontSize: 12, marginTop: 2 }}>
            {record.description || record.id}
          </div>
        </div>
      ),
    },
    {
      title: 'Department',
      dataIndex: 'department_id',
      key: 'department_id',
      render: (dept: string) =>
        dept ? (
          <Tag color="cyan" style={{ fontFamily: 'monospace', fontSize: 11 }}>
            {dept}
          </Tag>
        ) : (
          <Tag color="default">Global</Tag>
        ),
    },
    {
      title: 'Triggers & Bindings',
      key: 'triggers',
      render: (_: any, record: PlatformWorkflow) => (
        <Space direction="vertical" size={2}>
          {record.cron_expression && (
            <Tooltip title={`Cron schedule: ${record.cron_expression}`}>
              <Tag icon={<ClockCircleOutlined />} color="purple">
                {record.cron_expression}
              </Tag>
            </Tooltip>
          )}
          {record.webhook_enabled && record.webhook_token && (
            <Tooltip title="Webhook enabled. Click to copy webhook token.">
              <Tag
                icon={<ThunderboltOutlined />}
                color="blue"
                style={{ cursor: 'pointer' }}
                onClick={() => copyToClipboard(record.webhook_token || '', 'Webhook Token')}
              >
                Webhook: {record.webhook_token.slice(0, 8)}...
              </Tag>
            </Tooltip>
          )}
          {record.channel_binding && (
            <Tag
              icon={
                record.channel_binding.provider === 'telegram' ? (
                  <SendOutlined />
                ) : (
                  <SlackOutlined />
                )
              }
              color={record.channel_binding.provider === 'telegram' ? 'blue' : 'green'}
            >
              {record.channel_binding.channel_id}
            </Tag>
          )}
          {!record.cron_expression && !record.webhook_enabled && !record.channel_binding && (
            <Tag color="default">Manual Trigger Only</Tag>
          )}
        </Space>
      ),
    },
    {
      title: 'Steps',
      key: 'steps',
      render: (_: any, record: PlatformWorkflow) => {
        const steps = getParsedWorkflowSteps(record);
        return (
          <Tooltip title={`${steps.length} DAG execution stages`}>
            <Tag icon={<BranchesOutlined />} color="geekblue">
              {steps.length} Steps
            </Tag>
          </Tooltip>
        );
      },
    },
    {
      title: 'Status',
      dataIndex: 'is_active',
      key: 'is_active',
      render: (active: boolean) =>
        active ? (
          <Badge status="success" text={<span style={{ color: '#52c41a' }}>Active</span>} />
        ) : (
          <Badge status="default" text={<span style={{ color: '#8b949e' }}>Inactive</span>} />
        ),
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_: any, record: PlatformWorkflow) => (
        <Space size={6}>
          <Tooltip title="Execute Workflow">
            <Button
              type="primary"
              size="small"
              icon={<PlayCircleOutlined />}
              onClick={() => openRunModal(record)}
              style={{ background: '#238636', borderColor: '#238636' }}
            >
              Run
            </Button>
          </Tooltip>
          <Button size="small" onClick={() => openRunModal(record, true)}>
            Playground
          </Button>
          <Link to={`/workflows/${record.id}/logs`}><Button size="small" icon={<EyeOutlined />}>Logs</Button></Link>
          <Tooltip title="View Visual DAG Execution Graph">
            <Button
              size="small"
              icon={<ApartmentOutlined />}
              onClick={() => {
                setSelectedWorkflow(record);
                setCanvasModalOpen(true);
              }}
            />
          </Tooltip>
          <Tooltip title="View Playbook Definition (YAML/JSON)">
            <Button
              size="small"
              icon={<CodeOutlined />}
              onClick={() => {
                setSelectedWorkflow(record);
                setViewDefModalOpen(true);
              }}
            />
          </Tooltip>
          <Popconfirm
            title="Delete this workflow?"
            description="This will permanently delete this playbook and its configuration."
            onConfirm={() => handleDelete(record.id)}
            okText="Yes, Delete"
            cancelText="Cancel"
            okButtonProps={{ danger: true }}
          >
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  // Executions Table Columns
  const executionColumns = [
    {
      title: 'Execution ID',
      dataIndex: 'id',
      key: 'id',
      render: (id: string, record: WorkflowExecution) => (
        <Space direction="vertical" size={2}>
          <span style={{ fontFamily: 'monospace', color: '#58a6ff', fontWeight: 600 }}>
            {id}
          </span>
          {record.is_deduplicated && (
            <Tag color="purple" style={{ fontSize: 10, lineHeight: '14px' }}>
              ⚡ DEDUPLICATED / CACHED
            </Tag>
          )}
        </Space>
      ),
    },
    {
      title: 'Workflow',
      dataIndex: 'workflow_id',
      key: 'workflow_id',
      render: (wfId: string) => {
        const wf = workflows.find((w) => w.id === wfId);
        return (
          <div>
            <strong style={{ color: '#f0f6fc' }}>{wf?.name || wfId}</strong>
            <div style={{ color: '#8b949e', fontSize: 11 }}>{wfId}</div>
          </div>
        );
      },
    },
    {
      title: 'Trigger',
      dataIndex: 'trigger_type',
      key: 'trigger_type',
      render: (trigger: string) => {
        let color = 'default';
        if (trigger === 'PLAYGROUND') color = 'magenta';
        if (trigger === 'MANUAL') color = 'blue';
        if (trigger === 'WEBHOOK') color = 'cyan';
        if (trigger === 'CRON') color = 'purple';
        return <Tag color={color}>{trigger}</Tag>;
      },
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => {
        if (status === 'COMPLETED') {
          return <Tag icon={<CheckCircleOutlined />} color="success">COMPLETED</Tag>;
        }
        if (status === 'RUNNING') {
          return <Tag icon={<SyncOutlined spin />} color="processing">RUNNING</Tag>;
        }
        if (status === 'QUEUED') {
          return <Tag icon={<ClockCircleOutlined />} color="warning">QUEUED</Tag>;
        }
        if (status === 'FAILED') {
          return <Tag icon={<CloseCircleOutlined />} color="error">FAILED</Tag>;
        }
        return <Tag color="default">{status}</Tag>;
      },
    },
    {
      title: 'Tokens & Cost',
      key: 'tokens',
      render: (_: any, record: WorkflowExecution) => (
        <div>
          <span style={{ color: '#c9d1d9', fontSize: 12 }}>
            {(record.total_input_tokens + record.total_output_tokens).toLocaleString()} tokens
          </span>
          <div style={{ color: '#58a6ff', fontSize: 11 }}>
            ${record.total_cost_usd?.toFixed(4) || '0.0000'}
          </div>
        </div>
      ),
    },
    {
      title: 'Created At',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (d: string) => (
        <span style={{ color: '#8b949e', fontSize: 12 }}>
          {d ? new Date(d).toLocaleString() : '-'}
        </span>
      ),
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_: any, record: WorkflowExecution) => (
        <Button
          size="small"
          icon={<EyeOutlined />}
          onClick={() => {
            setSelectedExecution(record);
            setDetailDrawerOpen(true);
          }}
        >
          Inspect
        </Button>
      ),
    },
  ];

  return (
    <div style={{ padding: '24px', minHeight: '100vh', background: '#0a0d12' }}>
      {/* Header */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '20px',
        }}
      >
        <div>
          <h2
            style={{
              color: '#f0f6fc',
              margin: 0,
              fontSize: '22px',
              fontWeight: 700,
              letterSpacing: '0.5px',
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
            }}
          >
            <ApartmentOutlined style={{ color: '#8b5cf6' }} />
            Workflows & Automations Hub
          </h2>
          <div style={{ color: '#8b949e', fontSize: '13px', marginTop: '4px' }}>
            Multi-agent DAG orchestration, automated triggers, and smart execution deduplication.
          </div>
        </div>

        <Space size={10}>
          <Button
            icon={<ReloadOutlined spin={loading} />}
            onClick={() => loadData()}
            style={{
              background: '#161b22',
              borderColor: '#30363d',
              color: '#c9d1d9',
            }}
          >
            Refresh
          </Button>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => setCreateModalOpen(true)}
            style={{
              background: '#8b5cf6',
              borderColor: '#8b5cf6',
              fontWeight: 600,
            }}
          >
            + Create Workflow
          </Button>
        </Space>
      </div>

      {/* Metrics Banner */}
      <Row gutter={[16, 16]} style={{ marginBottom: '24px' }}>
        <Col xs={24} sm={12} md={6}>
          <Card
            variant="borderless"
            style={{
              background: '#161b22',
              borderRadius: '8px',
              border: '1px solid #30363d',
            }}
          >
            <Statistic
              title={<span style={{ color: '#8b949e', fontSize: 12 }}>TOTAL WORKFLOWS</span>}
              value={totalWorkflows}
              prefix={<ApartmentOutlined style={{ color: '#8b5cf6', marginRight: 6 }} />}
              styles={{ content: { color: '#f0f6fc', fontWeight: 700 } }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card
            variant="borderless"
            style={{
              background: '#161b22',
              borderRadius: '8px',
              border: '1px solid #30363d',
            }}
          >
            <Statistic
              title={<span style={{ color: '#8b949e', fontSize: 12 }}>ACTIVE PIPELINES</span>}
              value={activeWorkflows}
              prefix={<CheckCircleOutlined style={{ color: '#52c41a', marginRight: 6 }} />}
              styles={{ content: { color: '#f0f6fc', fontWeight: 700 } }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card
            variant="borderless"
            style={{
              background: '#161b22',
              borderRadius: '8px',
              border: '1px solid #30363d',
            }}
          >
            <Statistic
              title={<span style={{ color: '#8b949e', fontSize: 12 }}>QUEUED RUNS</span>}
              value={queuedRuns}
              prefix={<ThunderboltOutlined style={{ color: '#fa8c16', marginRight: 6 }} />}
              styles={{ content: { color: '#fa8c16', fontWeight: 700 } }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card
            variant="borderless"
            style={{
              background: '#161b22',
              borderRadius: '8px',
              border: '1px solid #30363d',
            }}
          >
            <Statistic
              title={<span style={{ color: '#8b949e', fontSize: 12 }}>DEDUPLICATED RUNS</span>}
              value={deduplicatedRuns}
              prefix={<SafetyCertificateOutlined style={{ color: '#38bdf8', marginRight: 6 }} />}
              styles={{ content: { color: '#38bdf8', fontWeight: 700 } }}
            />
          </Card>
        </Col>
      </Row>

      {/* Main Content Tabs */}
      <Card
        variant="borderless"
        style={{
          background: '#161b22',
          borderRadius: '8px',
          border: '1px solid #30363d',
        }}
        styles={{ body: { padding: '16px' } }}
      >
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          items={[
            {
              key: 'workflows',
              label: (
                <span style={{ fontSize: 14, fontWeight: 600 }}>
                  <ApartmentOutlined /> Playbooks & Pipelines ({workflows.length})
                </span>
              ),
              children: (
                <Table
                  dataSource={workflows}
                  columns={workflowColumns}
                  rowKey="id"
                  loading={loading}
                  pagination={{ pageSize: 10 }}
                  style={{ marginTop: 8 }}
                />
              ),
            },
            {
              key: 'executions',
              label: (
                <span style={{ fontSize: 14, fontWeight: 600 }}>
                  <SyncOutlined /> Execution History & Queue ({executions.length})
                </span>
              ),
              children: (
                <Table
                  dataSource={executions}
                  columns={executionColumns}
                  rowKey="id"
                  loading={loading}
                  pagination={{ pageSize: 15 }}
                  style={{ marginTop: 8 }}
                />
              ),
            },
          ]}
        />
      </Card>

      {/* Run Workflow Modal */}
      <Modal
        title={
          <span style={{ color: '#f0f6fc', display: 'flex', alignItems: 'center', gap: 8 }}>
            <PlayCircleOutlined style={{ color: '#52c41a' }} />
            {playgroundMode ? 'Playground' : 'Execute Workflow'}: {runningWorkflow?.name}
          </span>
        }
        open={runModalOpen}
        onCancel={() => setRunModalOpen(false)}
        onOk={handleExecute}
        confirmLoading={executing}
        okText={playgroundMode ? 'Run in Playground' : 'Launch Execution'}
        cancelText="Cancel"
      >
        {playgroundMode && <Alert type="info" showIcon style={{ marginBottom: 16 }}
          message="Tool-free workflow exercise"
          description="Runs the same DAG with real model calls and normal token costs. MCP, file and shell tools, channel notifications, and external approvals are disabled. Supply all required data in the JSON input. Each run starts fresh; results may differ from workflows using live tools."
        />}
        <Form form={runForm} layout="vertical">
          <Form.Item
            name="payload"
            label={<span style={{ color: '#c9d1d9' }}>Execution Trigger Payload (JSON)</span>}
            tooltip="Custom input variables passed to workflow steps as {{variable_name}}"
          >
            <TextArea
              rows={5}
              placeholder='{\n  "target_branch": "main",\n  "issue_number": 42\n}'
              style={{ fontFamily: 'monospace', fontSize: 12 }}
            />
          </Form.Item>

          {!playgroundMode && <Form.Item
            name="force_rerun"
            valuePropName="checked"
            label={<span style={{ color: '#c9d1d9' }}>Force Re-run</span>}
            tooltip="Bypass deduplication and caching, forcing all agents to execute from scratch"
          >
            <Switch checkedChildren="Force" unCheckedChildren="Cached" />
          </Form.Item>}
        </Form>
      </Modal>

      {/* Visual Canvas Graph Modal */}
      <Modal
        title={
          <span style={{ color: '#f0f6fc', display: 'flex', alignItems: 'center', gap: 8 }}>
            <ApartmentOutlined style={{ color: '#8b5cf6' }} />
            Workflow DAG Canvas: {selectedWorkflow?.name}
          </span>
        }
        open={canvasModalOpen}
        onCancel={() => setCanvasModalOpen(false)}
        footer={null}
        width={900}
      >
        {selectedWorkflow && (
          <WorkflowCanvasGraph
            workflowName={selectedWorkflow.name}
            steps={getParsedWorkflowSteps(selectedWorkflow)}
            channelBinding={selectedWorkflow.channel_binding}
            skills={[]}
            allowedMcps={[]}
            onDeleteStep={handleDeleteStepFromCanvas}
          />
        )}
      </Modal>

      {/* View Playbook Definition Modal */}
      <Modal
        title={
          <span style={{ color: '#f0f6fc', display: 'flex', alignItems: 'center', gap: 8 }}>
            <CodeOutlined style={{ color: '#38bdf8' }} />
            Playbook Definition: {selectedWorkflow?.name}
          </span>
        }
        open={viewDefModalOpen}
        onCancel={() => setViewDefModalOpen(false)}
        footer={[
          <Button
            key="copy"
            icon={<CopyOutlined />}
            onClick={() =>
              copyToClipboard(
                selectedWorkflow?.definition_yaml || selectedWorkflow?.definition_json || '',
                'Playbook Definition'
              )
            }
          >
            Copy
          </Button>,
          <Button key="close" type="primary" onClick={() => setViewDefModalOpen(false)}>
            Close
          </Button>,
        ]}
        width={750}
      >
        <pre
          style={{
            background: '#0d1117',
            color: '#7ee787',
            padding: '16px',
            borderRadius: '6px',
            fontSize: '12px',
            fontFamily: 'monospace',
            maxHeight: '450px',
            overflow: 'auto',
          }}
        >
          {selectedWorkflow?.definition_yaml ||
            (selectedWorkflow?.definition_json
              ? JSON.stringify(JSON.parse(selectedWorkflow.definition_json), null, 2)
              : '')}
        </pre>
      </Modal>

      {/* Execution Inspection Drawer */}
      <Drawer
        title={
          <span style={{ color: '#f0f6fc', display: 'flex', alignItems: 'center', gap: 8 }}>
            <EyeOutlined style={{ color: '#58a6ff' }} />
            Execution Inspection: {selectedExecution?.id}
            {selectedExecution && <Link to={`/workflows/${selectedExecution.workflow_id}/logs?execution=${selectedExecution.id}`}>Full logs</Link>}
          </span>
        }
        placement="right"
        styles={{ wrapper: { width: 500 } }}
        open={detailDrawerOpen}
        onClose={() => setDetailDrawerOpen(false)}
      >
        {selectedExecution && (
          <Space direction="vertical" size={16} style={{ width: '100%' }}>
            <Card size="small" style={{ background: '#161b22', borderColor: '#30363d' }}>
              <Space direction="vertical" size={4} style={{ width: '100%' }}>
                <span style={{ color: '#8b949e', fontSize: 12 }}>STATUS:</span>
                <div>
                  <Tag
                    color={
                      selectedExecution.status === 'COMPLETED'
                        ? 'success'
                        : selectedExecution.status === 'RUNNING'
                        ? 'processing'
                        : selectedExecution.status === 'QUEUED'
                        ? 'warning'
                        : 'error'
                    }
                  >
                    {selectedExecution.status}
                  </Tag>
                  {selectedExecution.is_deduplicated && (
                    <Tag color="purple">⚡ DEDUPLICATED</Tag>
                  )}
                </div>
              </Space>
            </Card>

            <Card size="small" style={{ background: '#161b22', borderColor: '#30363d' }}>
              <Space direction="vertical" size={4} style={{ width: '100%' }}>
                <span style={{ color: '#8b949e', fontSize: 12 }}>METRICS:</span>
                <div style={{ color: '#c9d1d9', fontSize: 13 }}>
                  • Input Tokens: {selectedExecution.total_input_tokens?.toLocaleString()}
                </div>
                <div style={{ color: '#c9d1d9', fontSize: 13 }}>
                  • Output Tokens: {selectedExecution.total_output_tokens?.toLocaleString()}
                </div>
                <div style={{ color: '#58a6ff', fontSize: 13, fontWeight: 600 }}>
                  • Total Cost: ${selectedExecution.total_cost_usd?.toFixed(4) || '0.0000'}
                </div>
              </Space>
            </Card>

            {selectedExecution.sandbox_path && (
              <Card size="small" style={{ background: '#161b22', borderColor: '#30363d' }}>
                <span style={{ color: '#8b949e', fontSize: 12 }}>SANDBOX DIRECTORY:</span>
                <div style={{ color: '#c9d1d9', fontFamily: 'monospace', fontSize: 11, marginTop: 4 }}>
                  {selectedExecution.sandbox_path}
                </div>
              </Card>
            )}

            {selectedExecution.error_message && (
              <Card size="small" style={{ background: '#220808', borderColor: '#8b0000' }}>
                <span style={{ color: '#ff7875', fontSize: 12 }}>ERROR DETAILS:</span>
                <pre
                  style={{
                    color: '#ff7875',
                    fontSize: 11,
                    fontFamily: 'monospace',
                    whiteSpace: 'pre-wrap',
                    marginTop: 4,
                  }}
                >
                  {selectedExecution.error_message}
                </pre>
              </Card>
            )}

            {selectedExecution.trigger_type === 'PLAYGROUND' && <Tag color="magenta">PLAYGROUND · TOOLS DISABLED</Tag>}
            {selectedExecution.step_runs?.map(step => (
              <Card key={step.id} size="small" title={`${step.step_key} · ${step.status}`}>
                <div>Cost: ${step.cost_usd.toFixed(4)}</div>
                <details><summary>Step input</summary><pre style={{ whiteSpace: 'pre-wrap' }}>{step.input_data}</pre></details>
                <pre style={{ whiteSpace: 'pre-wrap', maxHeight: 300, overflow: 'auto' }}>{step.output_data}</pre>
              </Card>
            ))}
            <Card size="small" style={{ background: '#161b22', borderColor: '#30363d' }}>
              <span style={{ color: '#8b949e', fontSize: 12 }}>INPUT PAYLOAD:</span>
              <pre
                style={{
                  background: '#0d1117',
                  color: '#7ee787',
                  padding: 8,
                  borderRadius: 4,
                  fontSize: 11,
                  fontFamily: 'monospace',
                  maxHeight: 200,
                  overflow: 'auto',
                  marginTop: 4,
                }}
              >
                {selectedExecution.trigger_payload || '(Empty payload)'}
              </pre>
            </Card>
          </Space>
        )}
      </Drawer>

      {/* Create Workflow Modal */}
      <CreateWorkflowModal
        open={createModalOpen}
        onClose={() => setCreateModalOpen(false)}
        onSuccess={() => {
          setCreateModalOpen(false);
          loadData();
        }}
        defaultChannelProvider={telegramConnector ? 'telegram' : 'slack'}
        defaultChannelId={
          telegramConnector?.configuration?.allowed_channels?.[0] ||
          telegramConnector?.configuration?.chat_id ||
          'Hermes_test'
        }
      />
    </div>
  );
};

export default WorkflowsPage;
