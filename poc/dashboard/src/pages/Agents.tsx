import React from 'react';
import { Table, Button, Tabs } from 'antd';
import { PlusOutlined, BranchesOutlined, BookOutlined, TeamOutlined, ThunderboltOutlined } from '@ant-design/icons';
import { Agent } from '../types/agent';
import { TemplateGallery } from '../components/agents/TemplateGallery';
import { HierarchyEditor } from '../components/agents/HierarchyEditor';
import { AgentMiniChatDrawer } from '../components/chat/AgentMiniChatDrawer';

import { useAgentsPage } from './useAgentsPage';
import { createAgentColumns } from './agentColumns';
import { AgentEditor } from './AgentEditor';

export const AgentsPage: React.FC = () => {
  const model = useAgentsPage();
  const {
    agents,
    loading,
    visible,
    activeTab,
    setActiveTab,
    chatAgent,
    chatVisible,
    setChatVisible,
    fetchAgents,
    handleCreate,
    officeFloorAgents,
    workflowAgents,
  } = model;
  const columns = createAgentColumns(model);
  return (
      <div>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <div>
          <h2 style={{ margin: 0, color: '#f3f4f6', fontSize: '22px', fontWeight: 700 }}>
            👥 Agent Management & Team Hierarchy
          </h2>
          <span style={{ color: '#9ca3af', fontSize: '13px' }}>
            Assemble multi-agent units, define reporting lines, and manage model parameters.
          </span>
        </div>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={handleCreate}
          style={{ background: '#10b981', borderColor: '#10b981', borderRadius: '8px' }}
        >
          Create Custom Agent
        </Button>
      </div>

      {/* Tabs */}
      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={[
          {
            key: 'roster',
            label: (
              <span>
                <TeamOutlined /> 🏢 Office Floor Team ({officeFloorAgents.length})
              </span>
            ),
            children: (
              <Table
                dataSource={officeFloorAgents}
                columns={columns}
                rowKey="id"
                loading={loading}
                pagination={{ pageSize: 8 }}
                scroll={{ x: 1000 }}
                style={{ background: '#161b22', borderRadius: '12px' }}
              />
            ),
          },
          {
            key: 'workflows',
            label: (
              <span>
                <ThunderboltOutlined /> ⚡ Workflow Automations ({workflowAgents.length})
              </span>
            ),
            children: (
              <div>
                <div
                  style={{
                    background: 'linear-gradient(90deg, rgba(88, 28, 135, 0.25) 0%, rgba(30, 27, 75, 0.45) 100%)',
                    border: '1px solid #7c3aed',
                    borderRadius: '10px',
                    padding: '14px 18px',
                    marginBottom: '16px',
                    color: '#e9d5ff',
                    fontSize: '13px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '14px',
                  }}
                >
                  <span style={{ fontSize: '24px' }}>⚡</span>
                  <div>
                    <div style={{ fontWeight: 700, color: '#f3e8ff', fontSize: '14px', marginBottom: '2px' }}>
                      Decoupled Workflow Automation Agents
                    </div>
                    <div style={{ fontSize: '12px', color: '#c084fc', lineHeight: 1.5 }}>
                      These agents are automatically provisioned when workflows are created to maintain scheduled executions (cron) or listen to selected channel events (Telegram/Slack). They run in the cloud background and are <strong>completely detached from the 2D Pixel Office Canvas</strong>, keeping physical workstations reserved for human-collaborative team agents.
                    </div>
                  </div>
                </div>
                <Table
                  dataSource={workflowAgents}
                  columns={columns}
                  rowKey="id"
                  loading={loading}
                  pagination={{ pageSize: 8 }}
                  scroll={{ x: 1000 }}
                  style={{ background: '#161b22', borderRadius: '12px' }}
                />
              </div>
            ),
          },
          {
            key: 'hierarchy',
            label: (
              <span>
                <BranchesOutlined /> Hierarchy Tree
              </span>
            ),
            children: <HierarchyEditor onHierarchyUpdated={fetchAgents} />,
          },
          {
            key: 'templates',
            label: (
              <span>
                <BookOutlined /> Template Gallery
              </span>
            ),
            children: <TemplateGallery agents={agents} onAgentInstantiated={fetchAgents} />,
          },
        ]}
      />

      <AgentEditor {...model} />

      {/* Agent Interactive Mini-Chat Drawer */}
      <AgentMiniChatDrawer
        agent={chatAgent}
        visible={chatVisible}
        onClose={() => setChatVisible(false)}
        onTaskDispatched={fetchAgents}
      />
    </div>
  );
};
export default AgentsPage;
