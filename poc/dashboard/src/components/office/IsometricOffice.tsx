import React from 'react';
import { Card, Tag, Badge, Tooltip, Button } from 'antd';
import {
  CodeOutlined,
  LaptopOutlined,
  FolderOpenOutlined,
  ThunderboltOutlined,
  CheckCircleOutlined,
  SyncOutlined,
  ExclamationCircleOutlined,
  EyeOutlined,
  GithubOutlined
} from '@ant-design/icons';
import { Agent, AgentStatus } from '../../types/agent';
import { Task } from '../../types/task';

interface IsometricOfficeProps {
  agents: Agent[];
  tasks: Task[];
  onSelectAgent: (agent: Agent) => void;
}

const DEPARTMENTS = [
  { key: 'Engineering', title: 'Engineering & Core', color: '#1677ff', icon: '💻' },
  { key: 'Architecture', title: 'Architecture & Design', color: '#722ed1', icon: '🏛️' },
  { key: 'QA & Testing', title: 'QA, Testing & Security', color: '#13c2c2', icon: '🛡️' },
  { key: 'Research & Ops', title: 'Research & DevOps', color: '#fa8c16', icon: '🔬' },
];

export const IsometricOffice: React.FC<IsometricOfficeProps> = ({
  agents,
  tasks,
  onSelectAgent,
}) => {
  // Map agents with their dynamic running tasks
  const getAgentActiveTask = (agentId: string) => {
    return tasks.find(
      (t) => String(t.agent_id) === String(agentId) && (t.status === 'running' || t.status === 'queued')
    );
  };

  const getStatusDetails = (status?: AgentStatus, hasActiveTask?: boolean) => {
    if (hasActiveTask || status === 'running') {
      return {
        color: '#52c41a',
        badge: 'processing',
        text: 'WORKING',
        glow: '0 0 15px rgba(82, 196, 26, 0.6)',
        icon: <SyncOutlined spin />,
      };
    }
    if (status === 'reviewing') {
      return {
        color: '#722ed1',
        badge: 'warning',
        text: 'REVIEWING',
        glow: '0 0 12px rgba(114, 46, 209, 0.5)',
        icon: <EyeOutlined />,
      };
    }
    if (status === 'error') {
      return {
        color: '#f5222d',
        badge: 'error',
        text: 'ATTENTION',
        glow: '0 0 15px rgba(245, 34, 45, 0.6)',
        icon: <ExclamationCircleOutlined />,
      };
    }
    return {
      color: '#1890ff',
      badge: 'default',
      text: 'IDLE',
      glow: '0 0 8px rgba(24, 144, 255, 0.3)',
      icon: <CheckCircleOutlined />,
    };
  };

  return (
    <div style={{ padding: '4px' }}>
      {/* Office Floor Legend & Summary */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          background: 'linear-gradient(135deg, #111827 0%, #1f2937 100%)',
          padding: '12px 20px',
          borderRadius: '12px',
          marginBottom: '20px',
          border: '1px solid #374151',
          color: '#fff',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <span style={{ fontSize: '20px' }}>🏢</span>
          <div>
            <h3 style={{ margin: 0, color: '#f3f4f6', fontSize: '16px', fontWeight: 600 }}>
              Virtual Agents Office Floor
            </h3>
            <span style={{ color: '#9ca3af', fontSize: '12px' }}>
              Real-time 3D workspace simulation & interactive agent desks
            </span>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '16px', fontSize: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ width: 10, height: 10, borderRadius: '50%', background: '#52c41a', boxShadow: '0 0 8px #52c41a' }} />
            <span style={{ color: '#d1d5db' }}>Working ({agents.filter(a => !!getAgentActiveTask(a.id)).length})</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ width: 10, height: 10, borderRadius: '50%', background: '#1890ff', boxShadow: '0 0 8px #1890ff' }} />
            <span style={{ color: '#d1d5db' }}>Idle ({agents.filter(a => !getAgentActiveTask(a.id)).length})</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ width: 10, height: 10, borderRadius: '50%', background: '#722ed1', boxShadow: '0 0 8px #722ed1' }} />
            <span style={{ color: '#d1d5db' }}>Total Desks ({agents.length})</span>
          </div>
        </div>
      </div>

      {/* Departments Grid */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        {DEPARTMENTS.map((dept) => {
          const deptAgents = agents.filter(
            (a) => (a.department || 'Engineering').toLowerCase() === dept.key.toLowerCase()
          );

          // If no agents assigned specifically, distribute some or show empty office zone
          const displayAgents = deptAgents.length > 0 ? deptAgents : (dept.key === 'Engineering' ? agents : []);

          return (
            <div
              key={dept.key}
              style={{
                background: '#0d1117',
                borderRadius: '16px',
                border: `1px solid ${dept.color}33`,
                padding: '16px 20px',
                boxShadow: '0 8px 24px rgba(0, 0, 0, 0.4)',
              }}
            >
              {/* Department Header */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  borderBottom: `1px solid ${dept.color}22`,
                  paddingBottom: '10px',
                  marginBottom: '16px',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ fontSize: '18px' }}>{dept.icon}</span>
                  <span style={{ fontWeight: 600, color: '#e6edf3', fontSize: '15px' }}>{dept.title}</span>
                  <Tag color={dept.color} style={{ borderRadius: '12px', fontSize: '11px' }}>
                    {displayAgents.length} Agents
                  </Tag>
                </div>
                <span style={{ fontSize: '12px', color: '#8b949e' }}>Department Wing</span>
              </div>

              {/* Desks Isometric Grid */}
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
                  gap: '20px',
                }}
              >
                {displayAgents.map((agent, index) => {
                  const activeTask = getAgentActiveTask(agent.id);
                  const isWorking = !!activeTask;
                  const statusInfo = getStatusDetails(agent.status, isWorking);

                  return (
                    <div
                      key={agent.id || index}
                      onClick={() => onSelectAgent(agent)}
                      style={{
                        position: 'relative',
                        background: 'linear-gradient(145deg, #161b22 0%, #0d1117 100%)',
                        borderRadius: '14px',
                        border: `1px solid ${isWorking ? '#52c41a88' : '#30363d'}`,
                        padding: '16px',
                        cursor: 'pointer',
                        transition: 'all 0.25s ease-in-out',
                        boxShadow: isWorking ? statusInfo.glow : '0 4px 12px rgba(0,0,0,0.3)',
                        overflow: 'hidden',
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.transform = 'translateY(-4px)';
                        e.currentTarget.style.borderColor = dept.color;
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.transform = 'translateY(0px)';
                        e.currentTarget.style.borderColor = isWorking ? '#52c41a88' : '#30363d';
                      }}
                    >
                      {/* Isometric Desk Illustration / Computer Rig */}
                      <div
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          marginBottom: '12px',
                        }}
                      >
                        {/* Computer Screen & Terminal simulation */}
                        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                          <div
                            style={{
                              width: '46px',
                              height: '42px',
                              background: '#1f2937',
                              borderRadius: '8px',
                              border: `2px solid ${isWorking ? '#52c41a' : '#4b5563'}`,
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              position: 'relative',
                              boxShadow: isWorking ? '0 0 10px #52c41a' : 'none',
                            }}
                          >
                            <LaptopOutlined style={{ fontSize: '20px', color: isWorking ? '#52c41a' : '#9ca3af' }} />
                            {isWorking && (
                              <span
                                style={{
                                  position: 'absolute',
                                  top: '4px',
                                  right: '4px',
                                  width: '6px',
                                  height: '6px',
                                  borderRadius: '50%',
                                  background: '#52c41a',
                                  animation: 'pulse 1.5s infinite',
                                }}
                              />
                            )}
                          </div>

                          <div>
                            <div style={{ fontWeight: 600, color: '#f3f4f6', fontSize: '15px' }}>
                              {agent.name}
                            </div>
                            <div style={{ color: '#9ca3af', fontSize: '11px', display: 'flex', gap: '6px' }}>
                              <span>Desk #{index + 1}</span>
                              <span>•</span>
                              <span>{agent.model ? agent.model.split('/').pop() : 'Default Model'}</span>
                            </div>
                          </div>
                        </div>

                        {/* Status Tag */}
                        <Tag
                          color={statusInfo.color}
                          icon={statusInfo.icon}
                          style={{
                            borderRadius: '12px',
                            fontWeight: 600,
                            padding: '2px 8px',
                            fontSize: '11px',
                          }}
                        >
                          {statusInfo.text}
                        </Tag>
                      </div>

                      {/* Live Speech Bubble / Action Callout */}
                      <div
                        style={{
                          background: '#21262d',
                          borderRadius: '8px',
                          padding: '8px 12px',
                          marginBottom: '12px',
                          fontSize: '12px',
                          color: isWorking ? '#a7f3d0' : '#8b949e',
                          borderLeft: `3px solid ${isWorking ? '#52c41a' : '#6b7280'}`,
                          minHeight: '36px',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '6px',
                        }}
                      >
                        <ThunderboltOutlined style={{ color: isWorking ? '#52c41a' : '#6b7280' }} />
                        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {isWorking
                            ? `Task in flight: ${(activeTask?.input_data as any)?.task || (activeTask?.input_data as any)?.prompt || 'Executing routine...'}`
                            : (agent.description || 'Standing by for new assignments')}
                        </span>
                      </div>

                      {/* Linked Repository & Skills Bar */}
                      <div
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          fontSize: '11px',
                          color: '#8b949e',
                          borderTop: '1px solid #21262d',
                          paddingTop: '8px',
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', maxWidth: '190px' }}>
                          <FolderOpenOutlined style={{ color: '#e3b341' }} />
                          <span
                            style={{
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              whiteSpace: 'nowrap',
                              color: agent.repo_path ? '#58a6ff' : '#6e7681',
                            }}
                            title={agent.repo_path || 'No local repo linked'}
                          >
                            {agent.repo_path ? agent.repo_path.split(/[/\\]/).pop() || agent.repo_path : 'Local Repo: default'}
                          </span>
                        </div>

                        <Button
                          type="link"
                          size="small"
                          style={{ padding: 0, fontSize: '11px', color: '#58a6ff' }}
                          onClick={(e) => {
                            e.stopPropagation();
                            onSelectAgent(agent);
                          }}
                        >
                          Inspect Desk →
                        </Button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
