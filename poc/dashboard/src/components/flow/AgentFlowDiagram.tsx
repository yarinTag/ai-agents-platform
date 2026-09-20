import React, { useState } from 'react';
import { Card, Tag, Button, Badge, Timeline } from 'antd';
import {
  ArrowRightOutlined,
  SyncOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  BranchesOutlined,
  LaptopOutlined,
  RocketOutlined,
  SafetyCertificateOutlined,
  FileDoneOutlined,
} from '@ant-design/icons';
import { Agent } from '../../types/agent';
import { Task } from '../../types/task';
import { ActivityEvent } from '../../types/flow';

interface AgentFlowDiagramProps {
  agents: Agent[];
  tasks: Task[];
  recentActivity: ActivityEvent[];
  onSelectAgent: (agent: Agent) => void;
}

interface PipelineStage {
  id: string;
  name: string;
  icon: React.ReactNode;
  color: string;
  description: string;
}

const STAGES: PipelineStage[] = [
  { id: 'input', name: 'Task Ingestion', icon: <RocketOutlined />, color: '#10b981', description: 'Queued requests & objectives' },
  { id: 'plan', name: 'Architecture & Planning', icon: <BranchesOutlined />, color: '#8b5cf6', description: 'Decomposing goals & schema design' },
  { id: 'code', name: 'Engineering & Execution', icon: <LaptopOutlined />, color: '#3b82f6', description: 'Code writing & implementation' },
  { id: 'verify', name: 'QA, Tests & Security', icon: <SafetyCertificateOutlined />, color: '#f59e0b', description: 'Test execution & code review' },
  { id: 'deliver', name: 'Delivery & Artifacts', icon: <FileDoneOutlined />, color: '#06b6d4', description: 'Completed tasks & outputs' },
];

export const AgentFlowDiagram: React.FC<AgentFlowDiagramProps> = ({
  agents,
  tasks,
  recentActivity,
  onSelectAgent,
}) => {

  const runningTasks = tasks.filter((t) => t.status === 'running');
  const completedTasks = tasks.filter((t) => t.status === 'completed');
  const queuedTasks = tasks.filter((t) => t.status === 'queued');

  // Assign agents to pipeline stages intelligently
  const getAgentsByStage = (stageId: string): Agent[] => {
    switch (stageId) {
      case 'plan':
        return agents.filter(
          (a) =>
            (a.department || '').toLowerCase().includes('arch') ||
            a.name.toLowerCase().includes('plan') ||
            a.name.toLowerCase().includes('lead')
        );
      case 'code':
        return agents.filter(
          (a) =>
            (a.department || '').toLowerCase().includes('eng') ||
            (!a.department && !a.name.toLowerCase().includes('qa'))
        );
      case 'verify':
        return agents.filter(
          (a) =>
            (a.department || '').toLowerCase().includes('qa') ||
            a.name.toLowerCase().includes('test') ||
            a.name.toLowerCase().includes('review')
        );
      default:
        return [];
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Top Real-Time Metrics Banner */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: '16px',
        }}
      >
        <div style={{ background: '#161b22', border: '1px solid #30363d', borderRadius: '12px', padding: '16px' }}>
          <div style={{ color: '#8b949e', fontSize: '12px' }}>LIVE IN-FLIGHT FLOWS</div>
          <div style={{ fontSize: '24px', fontWeight: 700, color: '#52c41a', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <SyncOutlined spin={runningTasks.length > 0} /> {runningTasks.length} Active
          </div>
          <div style={{ color: '#6e7681', fontSize: '11px', marginTop: '4px' }}>
            {queuedTasks.length} queued in pipeline
          </div>
        </div>

        <div style={{ background: '#161b22', border: '1px solid #30363d', borderRadius: '12px', padding: '16px' }}>
          <div style={{ color: '#8b949e', fontSize: '12px' }}>ACTIVE COLLABORATING AGENTS</div>
          <div style={{ fontSize: '24px', fontWeight: 700, color: '#58a6ff' }}>
            {agents.length} Online
          </div>
          <div style={{ color: '#6e7681', fontSize: '11px', marginTop: '4px' }}>
            Multi-agent workspace ready
          </div>
        </div>

        <div style={{ background: '#161b22', border: '1px solid #30363d', borderRadius: '12px', padding: '16px' }}>
          <div style={{ color: '#8b949e', fontSize: '12px' }}>TOTAL DELIVERIES COMPLETED</div>
          <div style={{ fontSize: '24px', fontWeight: 700, color: '#a371f7' }}>
            {completedTasks.length} Finished
          </div>
          <div style={{ color: '#6e7681', fontSize: '11px', marginTop: '4px' }}>
            All deliverables recorded
          </div>
        </div>
      </div>

      {/* Visual Pipeline Canvas */}
      <div
        style={{
          background: '#0d1117',
          border: '1px solid #30363d',
          borderRadius: '16px',
          padding: '24px',
          overflowX: 'auto',
          boxShadow: '0 8px 32px rgba(0, 0, 0, 0.5)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px' }}>
          <div>
            <h3 style={{ margin: 0, color: '#f3f4f6', fontSize: '18px', fontWeight: 600 }}>
              ⚡ Real-Time Multi-Agent Execution Pipeline ("FLOWO")
            </h3>
            <span style={{ color: '#8b949e', fontSize: '12px' }}>
              Live task routing and asynchronous inter-agent collaboration graph
            </span>
          </div>
          <Tag color="cyan" style={{ borderRadius: '12px', padding: '4px 10px' }}>
            LIVE STREAMING ACTIVE
          </Tag>
        </div>

        {/* Pipeline Stage Nodes */}
        <div
          style={{
            display: 'flex',
            alignItems: 'flex-start',
            gap: '12px',
            minWidth: '950px',
            justifyContent: 'space-between',
          }}
        >
          {STAGES.map((stage, idx) => {
            const stageAgents = getAgentsByStage(stage.id);
            const isLast = idx === STAGES.length - 1;

            return (
              <React.Fragment key={stage.id}>
                {/* Stage Column */}
                <div
                  style={{
                    flex: 1,
                    background: '#161b22',
                    borderRadius: '12px',
                    border: `1px solid ${stage.color}44`,
                    padding: '16px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '12px',
                    position: 'relative',
                  }}
                >
                  {/* Stage Header */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', borderBottom: '1px solid #30363d', paddingBottom: '10px' }}>
                    <span style={{ fontSize: '18px', color: stage.color }}>{stage.icon}</span>
                    <div>
                      <div style={{ fontWeight: 600, color: '#f3f4f6', fontSize: '13px' }}>{stage.name}</div>
                      <div style={{ fontSize: '10px', color: '#8b949e' }}>{stage.description}</div>
                    </div>
                  </div>

                  {/* Stage Items (Tasks or Agents) */}
                  <div style={{ minHeight: '160px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
                    {stage.id === 'input' ? (
                      <div>
                        <div style={{ fontSize: '11px', color: '#8b949e', marginBottom: '6px' }}>Active Ingestion Queue:</div>
                        {queuedTasks.length === 0 ? (
                          <div style={{ background: '#0d1117', padding: '12px', borderRadius: '8px', textAlign: 'center', color: '#6e7681', fontSize: '12px' }}>
                            Queue Clear
                          </div>
                        ) : (
                          queuedTasks.map((t) => (
                            <div key={t.id} style={{ background: '#0d1117', padding: '8px', borderRadius: '6px', border: '1px solid #30363d', fontSize: '11px', color: '#d1d5db' }}>
                              <Badge status="processing" text={`Task #${t.id}`} />
                            </div>
                          ))
                        )}
                      </div>
                    ) : stage.id === 'deliver' ? (
                      <div>
                        <div style={{ fontSize: '11px', color: '#8b949e', marginBottom: '6px' }}>Recent Deliverables:</div>
                        {completedTasks.slice(0, 3).map((t) => (
                          <div key={t.id} style={{ background: '#0d1117', padding: '8px', borderRadius: '6px', border: '1px solid #238636', fontSize: '11px', color: '#a7f3d0', marginBottom: '6px' }}>
                            <CheckCircleOutlined style={{ color: '#52c41a', marginRight: '6px' }} />
                            Task #{t.id} Verified
                          </div>
                        ))}
                      </div>
                    ) : (
                      // Agent nodes for this stage
                      (stageAgents.length > 0 ? stageAgents : agents.slice(0, 2)).map((agent) => {
                        const isAgentWorking = tasks.some(
                          (t) => String(t.agent_id) === String(agent.id) && t.status === 'running'
                        );

                        return (
                          <div
                            key={agent.id}
                            onClick={() => onSelectAgent(agent)}
                            style={{
                              background: '#0d1117',
                              borderRadius: '8px',
                              border: `1px solid ${isAgentWorking ? '#52c41a' : '#30363d'}`,
                              padding: '10px 12px',
                              cursor: 'pointer',
                              boxShadow: isAgentWorking ? '0 0 10px rgba(82, 196, 26, 0.4)' : 'none',
                              transition: 'all 0.2s ease',
                            }}
                            onMouseEnter={(e) => (e.currentTarget.style.borderColor = stage.color)}
                            onMouseLeave={(e) => (e.currentTarget.style.borderColor = isAgentWorking ? '#52c41a' : '#30363d')}
                          >
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                              <div style={{ fontWeight: 600, color: '#f3f4f6', fontSize: '12px' }}>{agent.name}</div>
                              <span
                                style={{
                                  width: 8,
                                  height: 8,
                                  borderRadius: '50%',
                                  background: isAgentWorking ? '#52c41a' : '#4b5563',
                                  boxShadow: isAgentWorking ? '0 0 8px #52c41a' : 'none',
                                }}
                              />
                            </div>
                            <div style={{ fontSize: '10px', color: '#8b949e', marginTop: '4px', display: 'flex', justifyContent: 'space-between' }}>
                              <span>{agent.model ? agent.model.split('/').pop() : 'Default'}</span>
                              <span style={{ color: isAgentWorking ? '#52c41a' : '#6e7681' }}>
                                {isAgentWorking ? 'PROCESSING' : 'STANDBY'}
                              </span>
                            </div>
                          </div>
                        );
                      })
                    )}
                  </div>
                </div>

                {/* Animated Flow Connector Arrow */}
                {!isLast && (
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      height: '100%',
                      paddingTop: '80px',
                    }}
                  >
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '2px',
                        color: runningTasks.length > 0 ? '#52c41a' : '#4b5563',
                        fontSize: '18px',
                      }}
                    >
                      <ArrowRightOutlined />
                    </div>
                  </div>
                )}
              </React.Fragment>
            );
          })}
        </div>
      </div>

      {/* Real-time Activity Feed */}
      <div
        style={{
          background: '#0d1117',
          border: '1px solid #30363d',
          borderRadius: '16px',
          padding: '20px',
        }}
      >
        <h4 style={{ color: '#f3f4f6', margin: '0 0 16px 0', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <ClockCircleOutlined /> Live Event Timeline & Stream
        </h4>

        {recentActivity.length === 0 ? (
          <div style={{ color: '#6e7681', padding: '12px 0' }}>No activity events recorded yet.</div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '220px', overflowY: 'auto' }}>
            {recentActivity.slice(0, 10).map((act, index) => (
              <div
                key={index}
                style={{
                  background: '#161b22',
                  padding: '8px 12px',
                  borderRadius: '6px',
                  border: '1px solid #21262d',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  fontSize: '12px',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ color: '#58a6ff', fontWeight: 600 }}>{act.action}</span>
                  <span style={{ color: '#8b949e' }}>{act.description}</span>
                </div>
                <span style={{ color: '#6e7681', fontSize: '11px' }}>
                  {new Date(act.timestamp).toLocaleTimeString()}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
