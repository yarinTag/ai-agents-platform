import React, { useState } from 'react';
import { Tag, Tooltip, Badge, Button } from 'antd';
import {
  LaptopOutlined,
  CrownOutlined,
  ThunderboltOutlined,
  SyncOutlined,
  CheckCircleOutlined,
  FolderOpenOutlined,
  AimOutlined,
  EyeOutlined,
  CodeOutlined,
} from '@ant-design/icons';
import { Agent } from '../../types/agent';
import { Task } from '../../types/task';

interface OfficeCanvasProps {
  agents: Agent[];
  tasks: Task[];
  onSelectAgent: (agent: Agent) => void;
}

export const OfficeCanvas: React.FC<OfficeCanvasProps> = ({
  agents,
  tasks,
  onSelectAgent,
}) => {
  const [hoveredAgent, setHoveredAgent] = useState<Agent | null>(null);

  // Identify Chief Orchestrator (Executive HQ in center)
  const chiefAgent = agents.find(
    (a) =>
      (a.department || '').toLowerCase().includes('hq') ||
      a.name.toLowerCase().includes('chief') ||
      a.name.toLowerCase().includes('director') ||
      a.name.toLowerCase().includes('lead architect')
  ) || agents[0];

  // Helper for active task
  const getAgentActiveTask = (agentId: string) => {
    return tasks.find(
      (t) => String(t.agent_id) === String(agentId) && (t.status === 'running' || t.status === 'queued')
    );
  };

  // Department configurations around the central HQ
  const WINGS = [
    {
      key: 'Engineering',
      title: 'Engineering Wing',
      subtitle: 'Backend, Frontend & Core Implementation',
      icon: '💻',
      color: '#3b82f6',
      accentBg: 'rgba(59, 130, 246, 0.08)',
      borderColor: '#2563eb',
      position: 'top-left',
    },
    {
      key: 'Architecture',
      title: 'Architecture Wing',
      subtitle: 'System Topology & Database Schemas',
      icon: '🏛️',
      color: '#8b5cf6',
      accentBg: 'rgba(139, 92, 246, 0.08)',
      borderColor: '#7c3aed',
      position: 'top-right',
    },
    {
      key: 'QA & Testing',
      title: 'QA & Security Wing',
      subtitle: 'Automated Tests & Vulnerability Audits',
      icon: '🛡️',
      color: '#10b981',
      accentBg: 'rgba(16, 185, 129, 0.08)',
      borderColor: '#059669',
      position: 'bottom-left',
    },
    {
      key: 'Research & Ops',
      title: 'Research & DevOps Wing',
      subtitle: 'Marketplace Plugins & CI/CD Pipelines',
      icon: '🔬',
      color: '#f59e0b',
      accentBg: 'rgba(245, 158, 11, 0.08)',
      borderColor: '#d97706',
      position: 'bottom-right',
    },
  ];

  // Get agents belonging to a wing (excluding chief if assigned to HQ)
  const getWingAgents = (wingKey: string) => {
    return agents.filter((a) => {
      if (chiefAgent && a.id === chiefAgent.id) return false;
      const dept = (a.department || 'Engineering').toLowerCase();
      return dept.includes(wingKey.toLowerCase().split(' ')[0]);
    });
  };

  return (
    <div
      style={{
        background: '#090d16',
        borderRadius: '20px',
        border: '1px solid #1e293b',
        padding: '24px',
        boxShadow: '0 20px 50px rgba(0, 0, 0, 0.7)',
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      {/* Background Architectural Grid Lines */}
      <div
        style={{
          position: 'absolute',
          inset: 0,
          backgroundImage: `
            linear-gradient(to right, rgba(255, 255, 255, 0.03) 1px, transparent 1px),
            linear-gradient(to bottom, rgba(255, 255, 255, 0.03) 1px, transparent 1px)
          `,
          backgroundSize: '40px 40px',
          pointerEvents: 'none',
        }}
      />

      {/* Top Banner with Quick Legend */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          position: 'relative',
          zIndex: 2,
          marginBottom: '20px',
          borderBottom: '1px solid #1e293b',
          paddingBottom: '16px',
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span style={{ fontSize: '24px' }}>🏢</span>
            <h3 style={{ margin: 0, color: '#f8fafc', fontSize: '18px', fontWeight: 700 }}>
              Autonomous Agents Office Canvas
            </h3>
            <Tag color="purple" style={{ borderRadius: '12px' }}>
              Central HQ Architecture
            </Tag>
          </div>
          <span style={{ color: '#94a3b8', fontSize: '12px' }}>
            Interactive floorplan: Task requests flow from Central HQ → Department Leads → Specialized Agents
          </span>
        </div>

        <div style={{ display: 'flex', gap: '16px', fontSize: '12px', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ width: 10, height: 10, borderRadius: '50%', background: '#10b981', boxShadow: '0 0 10px #10b981' }} />
            <span style={{ color: '#cbd5e1' }}>Working Task</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ width: 10, height: 10, borderRadius: '50%', background: '#3b82f6', boxShadow: '0 0 10px #3b82f6' }} />
            <span style={{ color: '#cbd5e1' }}>Ready / Idle</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ width: 10, height: 10, borderRadius: '50%', background: '#f59e0b', boxShadow: '0 0 10px #f59e0b' }} />
            <span style={{ color: '#cbd5e1' }}>Executive HQ</span>
          </div>
        </div>
      </div>

      {/* Main Floorplan Container */}
      <div
        style={{
          position: 'relative',
          minHeight: '720px',
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gridTemplateRows: '1fr 1fr',
          gap: '24px',
          zIndex: 2,
        }}
      >
        {/* SVG Conduit Flow Lines Connecting All Wings to Central HQ */}
        <svg
          style={{
            position: 'absolute',
            inset: 0,
            width: '100%',
            height: '100%',
            pointerEvents: 'none',
            zIndex: 1,
          }}
        >
          <defs>
            <linearGradient id="flow-cyan" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#38bdf8" stopOpacity="0.8" />
              <stop offset="100%" stopColor="#818cf8" stopOpacity="0.8" />
            </linearGradient>
            <linearGradient id="flow-gold" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#f59e0b" stopOpacity="0.8" />
              <stop offset="100%" stopColor="#ef4444" stopOpacity="0.8" />
            </linearGradient>
          </defs>

          {/* Diagonals to Center */}
          <line x1="25%" y1="25%" x2="50%" y2="50%" stroke="rgba(56, 189, 248, 0.4)" strokeWidth="2" strokeDasharray="6 4" />
          <line x1="75%" y1="25%" x2="50%" y2="50%" stroke="rgba(139, 92, 246, 0.4)" strokeWidth="2" strokeDasharray="6 4" />
          <line x1="25%" y1="75%" x2="50%" y2="50%" stroke="rgba(16, 185, 129, 0.4)" strokeWidth="2" strokeDasharray="6 4" />
          <line x1="75%" y1="75%" x2="50%" y2="50%" stroke="rgba(245, 158, 11, 0.4)" strokeWidth="2" strokeDasharray="6 4" />
        </svg>

        {/* 4 Corner Department Wings */}
        {WINGS.map((wing) => {
          const wingAgents = getWingAgents(wing.key);
          const leadAgent = wingAgents[0];
          const specialistAgents = wingAgents.slice(1);

          return (
            <div
              key={wing.key}
              style={{
                background: wing.accentBg,
                border: `1.5px solid ${wing.borderColor}44`,
                borderRadius: '16px',
                padding: '20px',
                display: 'flex',
                flexDirection: 'column',
                boxShadow: `0 8px 30px ${wing.borderColor}15`,
                position: 'relative',
                backdropFilter: 'blur(8px)',
              }}
            >
              {/* Wing Header */}
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  marginBottom: '14px',
                  borderBottom: `1px solid ${wing.borderColor}33`,
                  paddingBottom: '10px',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ fontSize: '20px' }}>{wing.icon}</span>
                  <div>
                    <span style={{ fontWeight: 700, color: '#f8fafc', fontSize: '14px' }}>{wing.title}</span>
                    <div style={{ fontSize: '11px', color: '#94a3b8' }}>{wing.subtitle}</div>
                  </div>
                </div>

                <Tag color={wing.color} style={{ borderRadius: '12px', fontWeight: 600 }}>
                  {wingAgents.length} Agents
                </Tag>
              </div>

              {/* Department Desks Floor */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', flex: 1 }}>
                {/* Department Lead Desk */}
                {leadAgent ? (
                  <div
                    onClick={() => onSelectAgent(leadAgent)}
                    style={{
                      background: 'linear-gradient(135deg, #1e293b 0%, #0f172a 100%)',
                      border: `1.5px solid ${getAgentActiveTask(leadAgent.id) ? '#10b981' : wing.color}`,
                      borderRadius: '12px',
                      padding: '12px 14px',
                      cursor: 'pointer',
                      transition: 'all 0.2s ease',
                      boxShadow: getAgentActiveTask(leadAgent.id) ? '0 0 16px rgba(16, 185, 129, 0.4)' : 'none',
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.transform = 'translateY(-2px)')}
                    onMouseLeave={(e) => (e.currentTarget.style.transform = 'translateY(0)')}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                        <div
                          style={{
                            width: 36,
                            height: 36,
                            borderRadius: '8px',
                            background: '#334155',
                            border: `2px solid ${wing.color}`,
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            color: wing.color,
                          }}
                        >
                          <CrownOutlined style={{ fontSize: '18px' }} />
                        </div>
                        <div>
                          <div style={{ fontWeight: 700, color: '#f8fafc', fontSize: '13px' }}>
                            {leadAgent.name} (Dept Lead)
                          </div>
                          <div style={{ fontSize: '11px', color: '#94a3b8' }}>
                            Model: {leadAgent.model?.split('/').pop()}
                          </div>
                        </div>
                      </div>

                      <Tag color={getAgentActiveTask(leadAgent.id) ? 'green' : 'blue'}>
                        {getAgentActiveTask(leadAgent.id) ? 'EXECUTING' : 'READY'}
                      </Tag>
                    </div>

                    {leadAgent.repo_path && (
                      <div style={{ marginTop: '8px', fontSize: '11px', color: '#64748b', display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <FolderOpenOutlined style={{ color: '#eab308' }} />
                        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {leadAgent.repo_path}
                        </span>
                      </div>
                    )}
                  </div>
                ) : (
                  <div style={{ color: '#64748b', fontSize: '12px', textAlign: 'center', padding: '16px' }}>
                    No Department Lead assigned
                  </div>
                )}

                {/* Specialist & Worker Desks Grid */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(170px, 1fr))', gap: '8px', marginTop: '6px' }}>
                  {specialistAgents.map((agent) => {
                    const activeTask = getAgentActiveTask(agent.id);

                    return (
                      <div
                        key={agent.id}
                        onClick={() => onSelectAgent(agent)}
                        style={{
                          background: '#0f172a',
                          border: `1px solid ${activeTask ? '#10b981' : '#334155'}`,
                          borderRadius: '10px',
                          padding: '10px',
                          cursor: 'pointer',
                          transition: 'all 0.2s ease',
                          boxShadow: activeTask ? '0 0 10px rgba(16, 185, 129, 0.3)' : 'none',
                        }}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.borderColor = '#38bdf8';
                          setHoveredAgent(agent);
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.borderColor = activeTask ? '#10b981' : '#334155';
                          setHoveredAgent(null);
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <div style={{ fontWeight: 600, color: '#f1f5f9', fontSize: '12px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {agent.name}
                          </div>
                          <span
                            style={{
                              width: 7,
                              height: 7,
                              borderRadius: '50%',
                              background: activeTask ? '#10b981' : '#64748b',
                              boxShadow: activeTask ? '0 0 6px #10b981' : 'none',
                            }}
                          />
                        </div>
                        <div style={{ fontSize: '10px', color: '#64748b', marginTop: '4px' }}>
                          Desk • {agent.model?.split('/').pop()?.slice(0, 16)}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          );
        })}

        {/* Central Command Circle (Chief Managing Director / HQ Agent) */}
        {chiefAgent && (
          <div
            onClick={() => onSelectAgent(chiefAgent)}
            style={{
              position: 'absolute',
              top: '50%',
              left: '50%',
              transform: 'translate(-50%, -50%)',
              zIndex: 10,
              width: '280px',
              background: 'linear-gradient(135deg, #1e1b4b 0%, #0f172a 100%)',
              border: '2.5px solid #f59e0b',
              borderRadius: '20px',
              padding: '18px',
              boxShadow: '0 0 40px rgba(245, 158, 11, 0.4), 0 20px 40px rgba(0,0,0,0.8)',
              cursor: 'pointer',
              transition: 'all 0.3s ease',
              textAlign: 'center',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.transform = 'translate(-50%, -54%) scale(1.03)')}
            onMouseLeave={(e) => (e.currentTarget.style.transform = 'translate(-50%, -50%) scale(1)')}
          >
            {/* Top Badge */}
            <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '8px' }}>
              <Tag color="gold" style={{ borderRadius: '12px', fontWeight: 800, padding: '2px 10px' }}>
                ⭐ EXECUTIVE HQ • CHIEF AGENT
              </Tag>
            </div>

            {/* Central Workstation Rig */}
            <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '10px' }}>
              <div
                style={{
                  width: '56px',
                  height: '52px',
                  borderRadius: '12px',
                  background: '#312e81',
                  border: '2px solid #fbbf24',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  boxShadow: '0 0 20px rgba(251, 191, 36, 0.6)',
                }}
              >
                <CrownOutlined style={{ fontSize: '28px', color: '#fbbf24' }} />
              </div>
            </div>

            <div style={{ fontWeight: 800, color: '#ffffff', fontSize: '15px' }}>
              {chiefAgent.name}
            </div>

            <div style={{ fontSize: '11px', color: '#c7d2fe', marginTop: '4px', lineHeight: '1.4' }}>
              Managing Director coordinating cross-department flows
            </div>

            <div style={{ marginTop: '10px', display: 'flex', justifyContent: 'center', gap: '8px' }}>
              <Tag color="cyan">{chiefAgent.model?.split('/').pop()}</Tag>
              <Tag color={getAgentActiveTask(chiefAgent.id) ? 'green' : 'blue'}>
                {getAgentActiveTask(chiefAgent.id) ? 'ORCHESTRATING' : 'HQ READY'}
              </Tag>
            </div>

            <div style={{ marginTop: '12px', paddingTop: '8px', borderTop: '1px solid #3730a3', fontSize: '11px', color: '#a5b4fc' }}>
              Click to Command Office Floor →
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default OfficeCanvas;
