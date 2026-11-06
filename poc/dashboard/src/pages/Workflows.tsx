import { usePermissions } from '../hooks/usePermissions';
import React, { useState } from 'react';
import { WorkflowChatModal } from '../components/workflows/WorkflowChatModal';
import { useWorkflowChatText } from '../i18n/workflowChat';
import { useSearchParams } from 'react-router-dom';
import { Table, Button, Modal, Space, Card, Row, Col, Statistic, Tabs, Input, message, Switch, Form, Alert, Select } from 'antd';
import { ApartmentOutlined, PlayCircleOutlined, PlusOutlined, ReloadOutlined, CodeOutlined, ThunderboltOutlined, CheckCircleOutlined, SyncOutlined, SafetyCertificateOutlined, CopyOutlined } from '@ant-design/icons';
import { WorkflowHistoryDrawer } from '../components/workflows/WorkflowHistoryDrawer';
import { WorkflowSettingsDrawer } from '../components/workflows/WorkflowSettingsDrawer';
import { CreateWorkflowModal } from '../components/workflows/CreateWorkflowModal';
import { WorkflowCanvasGraph } from '../components/workflows/WorkflowCanvasGraph';
const { TextArea } = Input;

import { useWorkflowsPage } from './useWorkflowsPage';
import { createWorkflowColumns } from './workflowColumns';
import { createWorkflowExecutionColumns } from './workflowExecutionColumns';
import { WorkflowExecutionDrawer } from './WorkflowExecutionDrawer';

export const WorkflowsPage: React.FC = () => {
  const { canManage, canOperate } = usePermissions();
  const model = useWorkflowsPage();
  const [chatSearch, setChatSearch] = useSearchParams();
  const [chatOpen, setChatOpen] = useState(() => chatSearch.has('workflowChat'));
  const closeChat = () => {
    setChatOpen(false);
    setChatSearch(previous => { const next = new URLSearchParams(previous); next.delete('workflowChat'); return next; }, { replace: true });
  };
  const chatText = useWorkflowChatText();
  const {
    workflows,
    executions,
    loading,
    activeTab,
    setActiveTab,
    editingWorkflow,
    setEditingWorkflow,
    historyWorkflow,
    setHistoryWorkflow,
    settingsWorkflow,
    setSettingsWorkflow,
    createModalOpen,
    setCreateModalOpen,
    canvasModalOpen,
    setCanvasModalOpen,
    selectedWorkflow,
    playgroundMode,
    runModalOpen,
    setRunModalOpen,
    runningWorkflow,
    runForm,
    executing,
    viewDefModalOpen,
    setViewDefModalOpen,
    loadData,
    handleExecute,
    runText,
    copyToClipboard,
    getParsedWorkflowSteps,
    handleDeleteStepFromCanvas,
    telegramConnector,
    totalWorkflows,
    activeWorkflows,
    queuedRuns,
    deduplicatedRuns,
  } = model;
  const workflowColumns = createWorkflowColumns(model, { canManage, canOperate });
  const executionColumns = createWorkflowExecutionColumns(model);
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
          <Button disabled={!canManage} onClick={() => setChatOpen(true)}>{chatText.entry}</Button>
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
            disabled={!canManage} onClick={() => { setEditingWorkflow(null); setCreateModalOpen(true); }}
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
          {!playgroundMode && <Form.Item name="dispatch_mode" label={runText.mode} initialValue="local">
            <Select options={[{ value: 'local', label: runText.local }, { value: 'queue', label: runText.queue }]} />
          </Form.Item>}
          {!playgroundMode && <Alert type="info" showIcon message={runText.help} style={{ marginBottom: 16 }} />}

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
            onDeleteStep={canManage ? handleDeleteStepFromCanvas : undefined}
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

      {chatOpen && canManage && <WorkflowChatModal onClose={closeChat} onCreated={() => { void loadData(); }} />}
      <WorkflowExecutionDrawer {...model} />

      {/* Create Workflow Modal */}
      {historyWorkflow && <WorkflowHistoryDrawer key={historyWorkflow.id} workflow={historyWorkflow}
        onClose={() => setHistoryWorkflow(null)} />}
      {settingsWorkflow && <WorkflowSettingsDrawer key={settingsWorkflow.id} workflow={settingsWorkflow}
        onClose={() => setSettingsWorkflow(null)} onSaved={() => { void loadData(); }} />}
      {createModalOpen && <CreateWorkflowModal
        key={editingWorkflow?.id || 'new'}
        workflow={editingWorkflow}
        open={createModalOpen}
        onClose={() => { setCreateModalOpen(false); setEditingWorkflow(null); }}
        onSuccess={() => {
          setCreateModalOpen(false);
          setEditingWorkflow(null);
          loadData();
        }}
        defaultChannelProvider={telegramConnector ? 'telegram' : 'slack'}
        defaultChannelId={
          telegramConnector?.configuration?.allowed_channels?.[0] ||
          telegramConnector?.configuration?.chat_id ||
          'Hermes_test'
        }
      />}
    </div>
  );
};
export default WorkflowsPage;
