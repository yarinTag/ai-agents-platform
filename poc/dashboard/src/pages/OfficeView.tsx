import React, { useEffect, useState } from 'react';
import { Spin } from 'antd';
import { AgentsOfficeV3Canvas } from '../components/office/AgentsOfficeV3Canvas';
import { OfficeRightSidebar } from '../components/office/OfficeRightSidebar';
import { AgentDeskDrawer } from '../components/office/AgentDeskDrawer';
import { Agent } from '../types/agent';
import { Task } from '../types/task';
import { getAgents, getTasks } from '../services/api';

export const OfficeViewPage: React.FC = () => {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null);
  const [drawerVisible, setDrawerVisible] = useState<boolean>(false);

  const fetchData = async () => {
    try {
      const [agentsRes, tasksRes] = await Promise.all([getAgents(), getTasks()]);
      setAgents(agentsRes.data || []);
      setTasks(tasksRes.data || []);
    } catch (err) {
      console.error('Failed to load office data', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    // Synchronize every 3s
    const interval = setInterval(fetchData, 3000);
    return () => clearInterval(interval);
  }, []);

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
        background: '#f7f6f2',
      }}
    >
      {/* Left / Center: Interactive 3D Isometric Agents Office Canvas */}
      <div style={{ flex: 1, position: 'relative', height: '100%' }}>
        {loading && agents.length === 0 ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
            <Spin size="large" />
          </div>
        ) : (
          <AgentsOfficeV3Canvas
            agents={agents}
            tasks={tasks}
            onSelectAgent={handleSelectAgent}
            onTaskCreated={fetchData}
          />
        )}
      </div>

      {/* Right: Office Task Status Panel (From Screenshot) */}
      <OfficeRightSidebar
        agents={agents}
        tasks={tasks}
        onTaskCreated={fetchData}
        onSelectAgent={handleSelectAgent}
      />

      {/* Interactive Agent Workstation Drawer */}
      <AgentDeskDrawer
        agent={selectedAgent}
        tasks={tasks}
        visible={drawerVisible}
        onClose={() => setDrawerVisible(false)}
        onTaskCreated={fetchData}
      />
    </div>
  );
};

export default OfficeViewPage;
