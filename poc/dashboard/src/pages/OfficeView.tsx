import React, { useState } from 'react';
import { Spin, Segmented } from 'antd';
import { AppstoreOutlined, BuildOutlined, TeamOutlined, BookOutlined } from '@ant-design/icons';
import { Button, Space } from 'antd';
import { AgentsOfficeV3Canvas } from '../components/office/AgentsOfficeV3Canvas';
import { PixelOfficeCanvas } from '../components/office/PixelOfficeCanvas';
import { OfficeRightSidebar } from '../components/office/OfficeRightSidebar';
import { AgentDeskDrawer } from '../components/office/AgentDeskDrawer';
import { AgentMiniChatDrawer } from '../components/chat/AgentMiniChatDrawer';
import { WarRoomModal } from '../components/warroom/WarRoomModal';
import { ProjectSharedMemoryModal } from '../components/memory/ProjectSharedMemoryModal';
import { Agent } from '../types/agent';
import { useOfficeEvents } from '../hooks/useOfficeEvents';

export const OfficeViewPage: React.FC = () => {
  const { agents, tasks, loading, connectionStatus, refresh } = useOfficeEvents();
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null);
  const [drawerVisible, setDrawerVisible] = useState<boolean>(false);
  const [chatVisible, setChatVisible] = useState<boolean>(false);
  const [warRoomVisible, setWarRoomVisible] = useState<boolean>(false);
  const [memoryVisible, setMemoryVisible] = useState<boolean>(false);
  const [viewMode, setViewMode] = useState<string>('pixel');

  const handleSelectAgent = (agent: Agent) => {
    setSelectedAgent(agent);
    setChatVisible(true);
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
        {/* Quick Collaboration Actions on Top Left */}
        <div
          style={{
            position: 'absolute',
            top: '16px',
            left: '20px',
            zIndex: 10,
            display: 'flex',
            gap: '8px',
          }}
        >
          <Button
            type="primary"
            icon={<TeamOutlined />}
            onClick={() => setWarRoomVisible(true)}
            style={{
              background: 'rgba(99, 102, 241, 0.9)',
              borderColor: '#6366f1',
              backdropFilter: 'blur(8px)',
              fontWeight: 600,
              boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.3)',
            }}
          >
            🏛️ War Room
          </Button>

          <Button
            icon={<BookOutlined />}
            onClick={() => setMemoryVisible(true)}
            style={{
              background: 'rgba(16, 185, 129, 0.2)',
              borderColor: '#10b981',
              color: '#34d399',
              backdropFilter: 'blur(8px)',
              fontWeight: 600,
            }}
          >
            🧠 Shared Memory
          </Button>
        </div>

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

      {/* Interactive Agent Mini-Chat Drawer */}
      <AgentMiniChatDrawer
        agent={selectedAgent}
        tasks={tasks}
        visible={chatVisible}
        onClose={() => setChatVisible(false)}
        onTaskDispatched={refresh}
      />

      {/* Multi-Agent War Room Deliberation Modal */}
      <WarRoomModal
        open={warRoomVisible}
        onClose={() => setWarRoomVisible(false)}
        agents={agents}
      />

      {/* Project Shared Memory & Knowledge Base Modal */}
      <ProjectSharedMemoryModal
        open={memoryVisible}
        onClose={() => setMemoryVisible(false)}
      />
    </div>
  );
};

export default OfficeViewPage;
