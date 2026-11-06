import { usePermissions } from '../hooks/usePermissions';
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
  const { canManage, canOperate } = usePermissions();
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
  } = model;
  const columns = createAgentColumns(model, { canManage, canOperate });
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
          disabled={!canManage} onClick={handleCreate}
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
                <TeamOutlined /> 🏢 Agents Fleet ({officeFloorAgents.length})
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
