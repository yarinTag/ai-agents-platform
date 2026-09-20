import React, { useEffect, useState } from 'react';
import { Spin, Button, Tag, message } from 'antd';
import { ReloadOutlined } from '@ant-design/icons';
import { AgentFlowDiagram } from '../components/flow/AgentFlowDiagram';
import { AgentDeskDrawer } from '../components/office/AgentDeskDrawer';
import { Agent } from '../types/agent';
import { Task } from '../types/task';
import { ActivityEvent } from '../types/flow';
import { getAgents, getTasks, getRecentActivity } from '../services/api';

export const AgentFlowPage: React.FC = () => {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [activity, setActivity] = useState<ActivityEvent[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null);
  const [drawerVisible, setDrawerVisible] = useState<boolean>(false);

  const fetchData = async () => {
    try {
      const [agentsRes, tasksRes, actRes] = await Promise.all([
        getAgents(),
        getTasks(),
        getRecentActivity(15).catch(() => ({ data: { activity: [] } })),
      ]);
      setAgents(agentsRes.data || []);
      setTasks(tasksRes.data || []);
      setActivity(actRes.data?.activity || []);
    } catch (err) {
      console.error('Failed to load flow data', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    // Live update polling every 3s
    const interval = setInterval(fetchData, 3000);
    return () => clearInterval(interval);
  }, []);

  const handleSelectAgent = (agent: Agent) => {
    setSelectedAgent(agent);
    setDrawerVisible(true);
  };

  return (
    <div>
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
          <h2 style={{ margin: 0, color: '#f3f4f6', fontSize: '22px', fontWeight: 700 }}>
            ⚡ Real-Time Agent Execution Flow ("FLOWO")
          </h2>
          <span style={{ color: '#9ca3af', fontSize: '13px' }}>
            Live orchestration, asynchronous task dispatch, and inter-agent pipeline
          </span>
        </div>

        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
          <Tag color="cyan" style={{ borderRadius: '12px', padding: '4px 10px', fontSize: '12px' }}>
            ● LIVE STREAMING
          </Tag>
          <Button
            icon={<ReloadOutlined />}
            onClick={() => {
              setLoading(true);
              fetchData();
            }}
            style={{ background: '#21262d', color: '#c9d1d9', borderColor: '#30363d' }}
          >
            Refresh
          </Button>
        </div>
      </div>

      {loading && agents.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '60px 0' }}>
          <Spin size="large" />
          <div style={{ marginTop: '16px', color: '#8b949e' }}>Streaming Live Execution Graph...</div>
        </div>
      ) : (
        <AgentFlowDiagram
          agents={agents}
          tasks={tasks}
          recentActivity={activity}
          onSelectAgent={handleSelectAgent}
        />
      )}

      {/* Desk Drawer */}
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

export default AgentFlowPage;
