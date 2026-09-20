import React, { useState } from 'react';
import { Spin, Segmented } from 'antd';
import { AppstoreOutlined, BuildOutlined } from '@ant-design/icons';
import { AgentsOfficeV3Canvas } from '../components/office/AgentsOfficeV3Canvas';
import { PixelOfficeCanvas } from '../components/office/PixelOfficeCanvas';
import { OfficeRightSidebar } from '../components/office/OfficeRightSidebar';
import { AgentDeskDrawer } from '../components/office/AgentDeskDrawer';
import { Agent } from '../types/agent';
import { useOfficeEvents } from '../hooks/useOfficeEvents';

export const OfficeViewPage: React.FC = () => {
  const { agents, tasks, loading, connectionStatus, refresh } = useOfficeEvents();
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null);
  const [drawerVisible, setDrawerVisible] = useState<boolean>(false);
  const [viewMode, setViewMode] = useState<string>('pixel');

  const handleSelectAgent = (agent: Agent) => {
    setSelectedAgent(agent);
    setDrawerVisible(true);
  };

  return (
    <div
      style={{
        display: 'flex',
        width: '100%',
        height: 'calc(100vh - 52px)',
        overflow: 'hidden',
        background: '#0f172a',
      }}
    >
      {/* Left / Center: Interactive Agents Office Canvas */}
      <div style={{ flex: 1, position: 'relative', height: '100%' }}>
        {/* View Mode Switcher in Top Right */}
        <div
          style={{
            position: 'absolute',
            top: '16px',
            right: '20px',
            zIndex: 10,
            background: 'rgba(15, 23, 42, 0.85)',
            padding: '4px',
            borderRadius: '10px',
            border: '1px solid #334155',
            backdropFilter: 'blur(8px)',
          }}
        >
          <Segmented
            value={viewMode}
            onChange={(val) => setViewMode(val as string)}
            options={[
              {
                label: 'Pixel Art',
                value: 'pixel',
                icon: <BuildOutlined />,
              },
              {
                label: 'Isometric 3D',
                value: 'isometric',
                icon: <AppstoreOutlined />,
              },
            ]}
          />
        </div>

        {loading && agents.length === 0 ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
            <Spin size="large" />
          </div>
        ) : viewMode === 'pixel' ? (
          <PixelOfficeCanvas
            agents={agents}
            tasks={tasks}
            connectionStatus={connectionStatus}
            onSelectAgent={handleSelectAgent}
            onTaskCreated={refresh}
          />
        ) : (
          <AgentsOfficeV3Canvas
            agents={agents}
            tasks={tasks}
            onSelectAgent={handleSelectAgent}
            onTaskCreated={refresh}
          />
        )}
      </div>

      {/* Right: Office Task Status Panel */}
      <OfficeRightSidebar
        agents={agents}
        tasks={tasks}
        onTaskCreated={refresh}
        onSelectAgent={handleSelectAgent}
      />

      {/* Interactive Agent Workstation Drawer */}
      <AgentDeskDrawer
        agent={selectedAgent}
        tasks={tasks}
        visible={drawerVisible}
        onClose={() => setDrawerVisible(false)}
        onTaskCreated={refresh}
      />
    </div>
  );
};

export default OfficeViewPage;
