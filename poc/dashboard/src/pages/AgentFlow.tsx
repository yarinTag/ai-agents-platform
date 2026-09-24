import React, { useEffect, useState } from 'react';
import { Spin, Button, Tag, Badge } from 'antd';
import { ReloadOutlined, ThunderboltOutlined, WifiOutlined } from '@ant-design/icons';
import { AgentFlowDiagram } from '../components/flow/AgentFlowDiagram';
import { AgentDeskDrawer } from '../components/office/AgentDeskDrawer';
import { Agent } from '../types/agent';
import { ActivityEvent } from '../types/flow';
import { getRecentActivity } from '../services/api';
import { useOfficeEvents } from '../hooks/useOfficeEvents';

export const AgentFlowPage: React.FC = () => {
  const { agents, tasks, loading, connectionStatus, lastEvent, refresh } = useOfficeEvents();
  const [activity, setActivity] = useState<ActivityEvent[]>([]);
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null);
  const [drawerVisible, setDrawerVisible] = useState<boolean>(false);

  // Initial load of historical activity
  useEffect(() => {
    getRecentActivity(20)
      .then((res) => {
        setActivity(res.data?.activity || []);
      })
      .catch((err) => {
        console.error('Failed to load initial recent activity:', err);
      });
  }, []);

  // Ingest live SSE events into the activity feed dynamically with ZERO polling
  useEffect(() => {
    if (!lastEvent) return;

    const payload = lastEvent.payload || {};
    const desc = payload.prompt
      ? `Task: "${payload.prompt.slice(0, 50)}${payload.prompt.length > 50 ? '...' : ''}"`
      : payload.name
      ? `Agent: ${payload.name}`
      : payload.result
      ? `Result: ${String(payload.result).slice(0, 50)}`
      : payload.error
      ? `Error: ${String(payload.error).slice(0, 50)}`
      : `Event on ${lastEvent.task_id || lastEvent.agent_id || 'platform'}`;

    const newActivity: ActivityEvent = {
      type: lastEvent.event_type,
      action: lastEvent.event_type.replace(/[_.]/g, ' ').toUpperCase(),
      description: desc,
      timestamp: lastEvent.timestamp || new Date().toISOString(),
      entity_id: lastEvent.task_id || lastEvent.agent_id || '',
      entity_type: lastEvent.task_id ? 'task' : 'agent',
      agent_id: lastEvent.agent_id,
      project_id: lastEvent.project_id,
    };

    setActivity((prev) => [newActivity, ...prev.slice(0, 29)]);
  }, [lastEvent]);

  const handleSelectAgent = (agent: Agent) => {
    setSelectedAgent(agent);
    setDrawerVisible(true);
  };

  const getStatusColor = () => {
    switch (connectionStatus) {
      case 'connected':
        return '#52c41a';
      case 'reconnecting':
        return '#faad14';
      default:
        return '#ff4d4f';
    }
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
          <Tag
            color={connectionStatus === 'connected' ? 'cyan' : 'default'}
            style={{
              borderRadius: '12px',
              padding: '4px 12px',
              fontSize: '12px',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <Badge color={getStatusColor()} />
            {connectionStatus === 'connected'
              ? 'LIVE SSE STREAMING'
              : connectionStatus === 'reconnecting'
              ? 'RECONNECTING...'
              : 'OFFLINE'}
          </Tag>
          <Button
            icon={<ReloadOutlined />}
            onClick={() => refresh()}
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
        onTaskCreated={refresh}
        agents={agents}
      />
    </div>
  );
};

export default AgentFlowPage;

