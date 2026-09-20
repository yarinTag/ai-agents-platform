import React, { useState, useEffect } from 'react';
import { Tag, Tooltip, Badge, Button, message } from 'antd';
import {
  PlusOutlined,
  MinusOutlined,
  HomeOutlined,
  StarFilled,
  ThunderboltFilled,
  PlayCircleFilled,
  CheckCircleFilled,
  SyncOutlined,
  FireFilled,
} from '@ant-design/icons';
import { Agent } from '../../types/agent';
import { Task } from '../../types/task';
import { createTask } from '../../services/api';

interface AgentsOfficeV3CanvasProps {
  agents: Agent[];
  tasks: Task[];
  onSelectAgent: (agent: Agent) => void;
  onSelectDepartment?: (dept: string) => void;
  onTaskCreated?: () => void;
}

interface DeskDef {
  title: string;
  isLead?: boolean;
  relX: number; // offset from platform center in px
  relY: number;
  agentId?: string;
}

interface DepartmentDef {
  key: string;
  name: string;
  dotColor: string;
  stat1Label: string;
  stat2Label: string;
  posX: number;
  posY: number;
  desks: DeskDef[];
}

export const AgentsOfficeV3Canvas: React.FC<AgentsOfficeV3CanvasProps> = ({
  agents,
  tasks,
  onSelectAgent,
  onSelectDepartment,
  onTaskCreated,
}) => {
  const [zoom, setZoom] = useState<number>(0.85);
  const [pan, setPan] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const [dragStart, setDragStart] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [liveSimRunning, setLiveSimRunning] = useState<boolean>(false);
  const [lastDispatchedDept, setLastDispatchedDept] = useState<string | null>(null);

  // Central Brain Coordinates (perfectly centered on 1280x1000 workspace)
  const brainPos = { x: 640, y: 500 };

  const DEPARTMENTS: DepartmentDef[] = [
    {
      key: 'Emails',
      name: 'EMAILS',
      dotColor: '#10b981',
      stat1Label: 'OUTREACH SENT',
      stat2Label: 'INBOX STATUS',
      posX: 380,
      posY: 180,
      desks: [
        { title: 'EMAILS LEAD', isLead: true, relX: -60, relY: -30 },
        { title: 'CLIENT OUTREACH', relX: 60, relY: -30 },
        { title: 'INBOX TRIAGE', relX: -60, relY: 40 },
        { title: 'SEQUENCES', relX: 60, relY: 40 },
      ],
    },
    {
      key: 'Delivery',
      name: 'DELIVERY',
      dotColor: '#0ea5e9',
      stat1Label: 'RELEASES SHIPPED',
      stat2Label: 'PIPELINE STATUS',
      posX: 900,
      posY: 180,
      desks: [
        { title: 'DELIVERY LEAD', isLead: true, relX: -60, relY: -30 },
        { title: 'ENGINEERING LEAD', relX: 60, relY: -30 },
        { title: 'QA AUDIT', relX: -60, relY: 40 },
        { title: 'DEPLOY PIPELINE', relX: 60, relY: 40 },
      ],
    },
    {
      key: 'Marketing',
      name: 'MARKETING',
      dotColor: '#f43f5e',
      stat1Label: 'NEW INSIGHTS',
      stat2Label: 'CAMPAIGN RUNS',
      posX: 170,
      posY: 500,
      desks: [
        { title: 'MARKETING LEAD', isLead: true, relX: -60, relY: -30 },
        { title: 'COPY & CONTENT', relX: 60, relY: -30 },
        { title: 'GROWTH STRATEGY', relX: -60, relY: 40 },
        { title: 'CAMPAIGNS', relX: 60, relY: 40 },
      ],
    },
    {
      key: 'Sales',
      name: 'SALES',
      dotColor: '#f59e0b',
      stat1Label: 'PIPELINE ACTIVE',
      stat2Label: 'DEAL STATUS',
      posX: 1110,
      posY: 500,
      desks: [
        { title: 'SALES LEAD', isLead: true, relX: -60, relY: -30 },
        { title: 'LEAD SCORING ICP', relX: 60, relY: -30 },
        { title: 'ENTERPRISE CLOSER', relX: -60, relY: 40 },
        { title: 'DEAL CONTRACTS', relX: 60, relY: 40 },
      ],
    },
    {
      key: 'Finance',
      name: 'FINANCE',
      dotColor: '#6366f1',
      stat1Label: 'BURN RATE',
      stat2Label: 'LEDGER AUDIT',
      posX: 360,
      posY: 820,
      desks: [
        { title: 'FINANCE LEAD', isLead: true, relX: -60, relY: -30 },
        { title: 'TOKEN METRICS', relX: 60, relY: -30 },
        { title: 'INVOICING', relX: -60, relY: 40 },
        { title: 'AUDIT & LEDGERS', relX: 60, relY: 40 },
      ],
    },
    {
      key: 'Operations',
      name: 'OPERATIONS',
      dotColor: '#8b5cf6',
      stat1Label: 'SLA UPTIME',
      stat2Label: 'WORKFLOW ENGINE',
      posX: 920,
      posY: 820,
      desks: [
        { title: 'OPERATIONS LEAD', isLead: true, relX: -60, relY: -30 },
        { title: 'WORKFLOW ENGINE', relX: 60, relY: -30 },
        { title: 'SLA & COMPLIANCE', relX: -60, relY: 40 },
        { title: 'RESOURCE MONITOR', relX: 60, relY: 40 },
      ],
    },
  ];

  // Helper: Find real agent for a specific desk
  const findAgentForDesk = (deptKey: string, deskTitle: string, deskIdx: number): Agent | null => {
    // 1. Direct department filter
    const deptAgents = agents.filter(
      (a) => (a.department || '').toLowerCase().includes(deptKey.toLowerCase())
    );

    // Special case: Lead Engineer belongs with Delivery & Engineering
    if (deptKey.toLowerCase() === 'delivery') {
      const engAgents = agents.filter((a) => (a.department || '').toLowerCase().includes('engineering'));
      deptAgents.push(...engAgents);
    }

    if (deptAgents.length === 0) return null;

    // If desk is lead, pick agent with lead or director in name
    if (deskTitle.includes('LEAD')) {
      const lead = deptAgents.find(
        (a) => a.name.toLowerCase().includes('lead') || a.name.toLowerCase().includes('director')
      );
      if (lead) return lead;
    }

    // Role-specific matching
    if (deskTitle.includes('COPY') || deskTitle.includes('CONTENT')) {
      const copyAgent = deptAgents.find(
        (a) => a.name.toLowerCase().includes('content') || a.name.toLowerCase().includes('copy')
      );
      if (copyAgent) return copyAgent;
    }
    if (deskTitle.includes('ENGINEERING') || deskTitle.includes('CODE')) {
      const engAgent = deptAgents.find((a) => a.name.toLowerCase().includes('engineer'));
      if (engAgent) return engAgent;
    }

    // Assign by index only if an actual agent exists for this slot
    if (deskIdx < deptAgents.length) {
      return deptAgents[deskIdx];
    }

    // Return null for unassigned open desks - DO NOT fallback to agents[0]
    return null;
  };

  // Helper: Get active task for an agent
  const getAgentActiveTask = (agentId?: string): Task | undefined => {
    if (!agentId) return undefined;
    return tasks.find(
      (t) => String(t.agent_id) === String(agentId) && (t.status === 'running' || t.status === 'queued')
    );
  };

  // Helper: Get dynamic department statistics
  const getDeptStats = (deptKey: string) => {
    const deptAgents = agents.filter((a) => (a.department || '').toLowerCase().includes(deptKey.toLowerCase()));
    const deptAgentIds = new Set(deptAgents.map((a) => a.id));

    const deptTasks = tasks.filter((t) => {
      if (deptAgentIds.has(t.agent_id)) return true;
      const deptInInput = (t.input_data as any)?.department;
      if (deptInInput && deptInInput.toLowerCase().includes(deptKey.toLowerCase())) return true;
      return false;
    });

    const doing = deptTasks.filter((t) => t.status === 'running').length;
    const next = deptTasks.filter((t) => t.status === 'queued' || t.status === 'pending').length;
    const done = deptTasks.filter((t) => t.status === 'completed').length;

    return {
      agentsCount: Math.max(deptAgents.length, 1),
      doing,
      next,
      done,
      total: deptTasks.length,
      hasActiveTask: doing > 0,
    };
  };

  // Central active task (if any agent is working)
  const activeTaskAny = tasks.find((t) => t.status === 'running');
  const totalDoing = tasks.filter((t) => t.status === 'running').length;
  const totalDone = tasks.filter((t) => t.status === 'completed').length;
  const totalNotesCount = tasks.length;

  // Trigger a live test task that connects through the office in real time
  const handleTriggerLiveMission = async () => {
    try {
      setLiveSimRunning(true);
      const targetDept = DEPARTMENTS[Math.floor(Math.random() * DEPARTMENTS.length)];
      setLastDispatchedDept(targetDept.key);

      const targetAgent = agents.find(
        (a) => (a.department || '').toLowerCase().includes(targetDept.key.toLowerCase())
      ) || agents[0];

      if (targetAgent) {
        await createTask({
          agent_id: targetAgent.id,
          project_id: null,
          skill_id: null,
          input_data: {
            task: `Live Mission: Sync ${targetDept.name} with Central Brain`,
            department: targetDept.name,
            timestamp: new Date().toISOString(),
          },
        });
        message.success(`⚡ Live mission dispatched to ${targetAgent.name} (${targetDept.name})!`);
        if (onTaskCreated) onTaskCreated();
      }
    } catch (err) {
      message.error('Failed to dispatch live mission');
    } finally {
      setTimeout(() => setLiveSimRunning(false), 2000);
    }
  };

  const handleMouseDown = (e: React.MouseEvent) => {
    if (e.button === 0) {
      setIsDragging(true);
      setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
    }
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (isDragging) {
      setPan({ x: e.clientX - dragStart.x, y: e.clientY - dragStart.y });
    }
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const zoomFactor = e.deltaY < 0 ? 0.08 : -0.08;
    setZoom((prev) => Math.min(1.6, Math.max(0.45, Number((prev + zoomFactor).toFixed(2)))));
  };

  return (
    <div
      style={{
        position: 'relative',
        width: '100%',
        height: 'calc(100vh - 52px)',
        minHeight: '750px',
        backgroundColor: '#f7f6f2',
        overflow: 'hidden',
        userSelect: 'none',
        cursor: isDragging ? 'grabbing' : 'grab',
      }}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
      onWheel={handleWheel}
    >
      {/* Top Left Floating Live Status Pill & Quick Action */}
      <div
        style={{
          position: 'absolute',
          top: '16px',
          left: '20px',
          zIndex: 20,
          display: 'flex',
          alignItems: 'center',
          gap: '10px',
        }}
      >
        <div
          style={{
            background: 'rgba(255, 255, 255, 0.95)',
            border: '1px solid #e5e2d8',
            borderRadius: '24px',
            padding: '6px 14px',
            boxShadow: '0 4px 12px rgba(0,0,0,0.06)',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            fontSize: '12px',
            fontWeight: 700,
            color: '#1c1917',
          }}
        >
          <span
            style={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              background: totalDoing > 0 ? '#10b981' : '#94a3b8',
              boxShadow: totalDoing > 0 ? '0 0 8px #10b981' : 'none',
            }}
          />
          <span>{totalDoing > 0 ? 'LIVE RUNTIME' : 'RUNTIME STANDBY'}</span>
          <span style={{ color: '#78716c', fontWeight: 500 }}>|</span>
          <span style={{ color: totalDoing > 0 ? '#059669' : '#64748b' }}>
            {totalDoing > 0 ? `${totalDoing} ACTIVE IN FLIGHT` : '0 IN FLIGHT (IDLE)'}
          </span>
          <span style={{ color: '#78716c', fontWeight: 500 }}>•</span>
          <span style={{ color: '#44403c' }}>{totalDone} COMPLETED</span>
        </div>

        <Button
          type="primary"
          icon={<ThunderboltFilled />}
          loading={liveSimRunning}
          onClick={handleTriggerLiveMission}
          style={{
            background: '#10b981',
            borderColor: '#10b981',
            borderRadius: '20px',
            boxShadow: '0 4px 12px rgba(16, 185, 129, 0.25)',
            fontWeight: 700,
            fontSize: '12px',
          }}
        >
          DISPATCH LIVE MISSION
        </Button>
      </div>

      {/* Zoom / Pan Container */}
      <div
        style={{
          transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
          transformOrigin: 'center center',
          transition: isDragging ? 'none' : 'transform 0.15s ease-out',
          width: '1280px',
          height: '1000px',
          margin: '0 auto',
          position: 'relative',
        }}
      >
        {/* SVG Interconnecting Walkways & Real-Time Animated Particle Beams */}
        <svg
          style={{
            position: 'absolute',
            inset: 0,
            width: '100%',
            height: '100%',
            overflow: 'visible',
            pointerEvents: 'none',
          }}
        >
          <defs>
            <filter id="walkway-shadow" x="-10%" y="-10%" width="120%" height="120%">
              <feDropShadow dx="0" dy="6" stdDeviation="4" floodColor="#000000" floodOpacity="0.08" />
            </filter>
            <linearGradient id="brainPulseGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#10b981" stopOpacity="0.8" />
              <stop offset="100%" stopColor="#059669" stopOpacity="0.2" />
            </linearGradient>
          </defs>

          {/* Isometric Walkways connecting Brain to Department Platforms */}
          {DEPARTMENTS.map((dept) => {
            const stats = getDeptStats(dept.key);
            const isDeptActive = stats.doing > 0 || lastDispatchedDept === dept.key;

            return (
              <g key={`bridge-${dept.key}`}>
                {/* Wide Walkway shadow */}
                <line
                  x1={brainPos.x}
                  y1={brainPos.y + 4}
                  x2={dept.posX}
                  y2={dept.posY + 4}
                  stroke="#d6d3c8"
                  strokeWidth="18"
                  strokeLinecap="round"
                />
                {/* Walkway body */}
                <line
                  x1={brainPos.x}
                  y1={brainPos.y}
                  x2={dept.posX}
                  y2={dept.posY}
                  stroke={isDeptActive ? '#dcfce7' : '#eae7dd'}
                  strokeWidth="16"
                  strokeLinecap="round"
                />
                {/* Walkway center guide rail */}
                <line
                  x1={brainPos.x}
                  y1={brainPos.y}
                  x2={dept.posX}
                  y2={dept.posY}
                  stroke={isDeptActive ? '#10b981' : '#d1cebf'}
                  strokeWidth="1.5"
                  strokeDasharray={isDeptActive ? '6 6' : '4 4'}
                />

                {/* Animated Glowing Signal Dotted Stream (Only when active) */}
                {isDeptActive && (
                  <line
                    x1={brainPos.x}
                    y1={brainPos.y}
                    x2={dept.posX}
                    y2={dept.posY}
                    stroke={dept.dotColor}
                    strokeWidth="3"
                    strokeDasharray="6 8"
                    strokeOpacity={1}
                  >
                    <animate
                      attributeName="stroke-dashoffset"
                      from="28"
                      to="0"
                      dur="0.9s"
                      repeatCount="indefinite"
                    />
                  </line>
                )}

                {/* Dynamic Energy Particle Packet Moving Along Corridor When Active */}
                {isDeptActive && (
                  <circle r="5" fill={dept.dotColor}>
                    <animateMotion
                      path={`M ${dept.posX} ${dept.posY} L ${brainPos.x} ${brainPos.y}`}
                      dur="1.3s"
                      repeatCount="indefinite"
                    />
                  </circle>
                )}
              </g>
            );
          })}
        </svg>

        {/* 6 Department Floating Isometric Platforms */}
        {DEPARTMENTS.map((dept) => {
          const stats = getDeptStats(dept.key);
          const isDeptActive = stats.doing > 0;

          return (
            <div
              key={dept.key}
              style={{
                position: 'absolute',
                left: `${dept.posX}px`,
                top: `${dept.posY}px`,
                transform: 'translate(-50%, -50%)',
                width: '260px',
                height: '190px',
              }}
            >
              {/* Isometric 3D Platform Slab */}
              <div
                style={{
                  position: 'absolute',
                  inset: 0,
                  background: isDeptActive ? '#f4fbf7' : '#eae7dd',
                  borderRadius: '24px',
                  boxShadow: isDeptActive
                    ? `0 16px 32px ${dept.dotColor}25, inset 0 2px 0 rgba(255,255,255,0.9)`
                    : '0 16px 30px rgba(0,0,0,0.12), inset 0 2px 0 rgba(255,255,255,0.7)',
                  border: isDeptActive ? `2px solid ${dept.dotColor}88` : '1px solid #dcd8ca',
                  transform: 'perspective(600px) rotateX(20deg)',
                  transformOrigin: 'center center',
                  transition: 'background 0.3s ease, border 0.3s ease',
                }}
              />

              {/* Office Plants in corners */}
              <div
                style={{
                  position: 'absolute',
                  top: '12px',
                  left: '12px',
                  fontSize: '15px',
                  filter: 'drop-shadow(0 2px 2px rgba(0,0,0,0.15))',
                  pointerEvents: 'none',
                }}
              >
                🪴
              </div>
              <div
                style={{
                  position: 'absolute',
                  bottom: '12px',
                  right: '12px',
                  fontSize: '15px',
                  filter: 'drop-shadow(0 2px 2px rgba(0,0,0,0.15))',
                  pointerEvents: 'none',
                }}
              >
                🪴
              </div>

              {/* Desks & Characters on the Platform */}
              {dept.desks.map((desk, dIdx) => {
                const deskAgent = findAgentForDesk(dept.key, desk.title, dIdx);
                const activeTask = deskAgent ? getAgentActiveTask(deskAgent.id) : undefined;
                const isWorking = !!activeTask;

                return (
                  <div
                    key={dIdx}
                    onClick={(e) => {
                      e.stopPropagation();
                      if (deskAgent) onSelectAgent(deskAgent);
                    }}
                    style={{
                      position: 'absolute',
                      left: `calc(50% + ${desk.relX}px)`,
                      top: `calc(50% + ${desk.relY}px)`,
                      transform: 'translate(-50%, -50%)',
                      cursor: 'pointer',
                      zIndex: 3,
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'center',
                      transition: 'transform 0.15s ease',
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.transform = 'translate(-50%, -55%) scale(1.1)')}
                    onMouseLeave={(e) => (e.currentTarget.style.transform = 'translate(-50%, -50%) scale(1)')}
                  >
                    {/* Live Speech / Task Bubble if Working */}
                    {isWorking && (
                      <div
                        style={{
                          background: '#10b981',
                          color: '#ffffff',
                          borderRadius: '8px',
                          padding: '2px 6px',
                          fontSize: '8px',
                          fontWeight: 700,
                          boxShadow: '0 2px 8px rgba(16, 185, 129, 0.4)',
                          whiteSpace: 'nowrap',
                          marginBottom: '2px',
                          animation: 'pulse 1.5s infinite',
                        }}
                      >
                        ⚡ WORKING...
                      </div>
                    )}

                    {/* Desk Name Tag Label */}
                    <div
                      style={{
                        background: '#ffffff',
                        border: isWorking ? '1.5px solid #10b981' : '1px solid #e2ded5',
                        borderRadius: '10px',
                        padding: '1px 6px',
                        fontSize: '9px',
                        fontWeight: desk.isLead ? 700 : 600,
                        color: desk.isLead ? '#b45309' : '#44403c',
                        boxShadow: '0 2px 6px rgba(0,0,0,0.08)',
                        whiteSpace: 'nowrap',
                        marginBottom: '3px',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '3px',
                      }}
                    >
                      {desk.isLead && <StarFilled style={{ color: '#f59e0b', fontSize: '8px' }} />}
                      {deskAgent ? deskAgent.name.split(' ')[0] : desk.title}
                    </div>

                    {/* Desk & Computer Rig (Isometric 3D Illustration) */}
                    <div
                      style={{
                        position: 'relative',
                        width: '32px',
                        height: '24px',
                        background: isWorking ? '#e6fcf5' : '#d6d2c4',
                        borderRadius: '5px',
                        border: isWorking ? '1px solid #10b981' : '1px solid #b8b3a5',
                        boxShadow: '0 4px 6px rgba(0,0,0,0.15)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                      }}
                    >
                      {/* Computer Screen */}
                      <div
                        style={{
                          width: '18px',
                          height: '13px',
                          background: isWorking ? '#059669' : '#292524',
                          borderRadius: '2px',
                          border: '1px solid #1c1917',
                          boxShadow: isWorking ? '0 0 10px #10b981' : 'none',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                        }}
                      >
                        {isWorking ? (
                          <span style={{ fontSize: '7px', color: '#ecfdf5', fontWeight: 700 }}>AI</span>
                        ) : (
                          <div style={{ width: '12px', height: '1.5px', background: '#57534e' }} />
                        )}
                      </div>

                      {/* Agent Character sitting at desk */}
                      <div
                        style={{
                          position: 'absolute',
                          bottom: '-8px',
                          width: '14px',
                          height: '14px',
                          borderRadius: '50%',
                          background: desk.isLead ? '#f59e0b' : '#0284c7',
                          border: isWorking ? '2px solid #10b981' : '2px solid #ffffff',
                          boxShadow: '0 2px 4px rgba(0,0,0,0.2)',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          color: '#fff',
                          fontSize: '8px',
                          fontWeight: 700,
                        }}
                      >
                        {deskAgent ? deskAgent.name[0] : desk.title[0]}
                      </div>
                    </div>
                  </div>
                );
              })}

              {/* Floating Department HUD Card (Exact match to screenshot!) */}
              <div
                onClick={(e) => {
                  e.stopPropagation();
                  if (onSelectDepartment) onSelectDepartment(dept.key);
                }}
                style={{
                  position: 'absolute',
                  top: '-70px',
                  left: '50%',
                  transform: 'translateX(-50%)',
                  background: '#ffffff',
                  borderRadius: '16px',
                  border: isDeptActive ? `2px solid ${dept.dotColor}` : '1px solid #e5e2d8',
                  boxShadow: isDeptActive
                    ? `0 12px 28px ${dept.dotColor}25`
                    : '0 10px 25px -5px rgba(0, 0, 0, 0.08), 0 4px 10px -3px rgba(0, 0, 0, 0.04)',
                  padding: '12px 16px',
                  minWidth: '170px',
                  cursor: 'pointer',
                  zIndex: 4,
                  transition: 'transform 0.15s ease, box-shadow 0.15s ease',
                }}
                onMouseEnter={(e) => (e.currentTarget.style.transform = 'translateX(-50%) translateY(-2px)')}
                onMouseLeave={(e) => (e.currentTarget.style.transform = 'translateX(-50%) translateY(0)')}
              >
                {/* Header: Dot + Department Name */}
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span
                      style={{
                        width: 8,
                        height: 8,
                        borderRadius: '50%',
                        background: dept.dotColor,
                        boxShadow: isDeptActive ? `0 0 6px ${dept.dotColor}` : 'none',
                      }}
                    />
                    <span style={{ fontSize: '11px', fontWeight: 800, color: '#1c1917', letterSpacing: '0.8px' }}>
                      {dept.name}
                    </span>
                  </div>
                  {isDeptActive ? (
                    <span style={{ fontSize: '9px', fontWeight: 800, color: '#10b981' }}>
                      <SyncOutlined spin /> ACTIVE
                    </span>
                  ) : (
                    <span style={{ fontSize: '9px', fontWeight: 600, color: '#94a3b8' }}>
                      IDLE
                    </span>
                  )}
                </div>

                {/* Big Agent Count */}
                <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px', margin: '4px 0 10px 0' }}>
                  <span style={{ fontSize: '28px', fontWeight: 800, color: '#1c1917', lineHeight: 1 }}>
                    {stats.agentsCount}
                  </span>
                  <span style={{ fontSize: '10px', fontWeight: 700, color: '#78716c', letterSpacing: '0.5px' }}>
                    AGENTS
                  </span>
                </div>

                {/* Two Key Metrics */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '3px', marginBottom: '10px', fontSize: '11px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: '#78716c', fontSize: '9px', fontWeight: 700 }}>{dept.stat1Label}</span>
                    <span style={{ fontWeight: 800, color: '#1c1917' }}>{stats.total}</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: '#78716c', fontSize: '9px', fontWeight: 700 }}>{dept.stat2Label}</span>
                    <span style={{ fontWeight: 800, color: isDeptActive ? '#10b981' : '#64748b' }}>
                      {isDeptActive ? `${stats.doing} IN PROGRESS` : stats.done > 0 ? `${stats.done} VERIFIED` : 'STANDBY'}
                    </span>
                  </div>
                </div>

                {/* Bottom Task Pipeline Pills: DOING X, NEXT Y, DONE Z (Dynamically populated!) */}
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    borderTop: '1px solid #f0ede4',
                    paddingTop: '6px',
                    fontSize: '9px',
                    fontWeight: 700,
                    color: '#78716c',
                  }}
                >
                  <span>
                    DOING{' '}
                    <strong style={{ color: stats.doing > 0 ? '#10b981' : '#1c1917' }}>
                      {stats.doing}
                    </strong>
                  </span>
                  <span>
                    NEXT <strong style={{ color: '#1c1917' }}>{stats.next}</strong>
                  </span>
                  <span>
                    DONE <strong style={{ color: '#059669' }}>{stats.done}</strong>
                  </span>
                </div>
              </div>
            </div>
          );
        })}

        {/* Central Hub: THE BRAIN 37 NOTES */}
        <div
          style={{
            position: 'absolute',
            left: `${brainPos.x}px`,
            top: `${brainPos.y}px`,
            transform: 'translate(-50%, -50%)',
            zIndex: 5,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
          }}
        >
          {/* Hexagonal Central Platform */}
          <div
            style={{
              width: '130px',
              height: '90px',
              background: totalDoing > 0 ? '#ecfdf5' : '#f8fafc',
              borderRadius: '20px',
              border: totalDoing > 0 ? '2.5px solid #10b981' : '1.5px solid #cbd5e1',
              boxShadow: totalDoing > 0
                ? '0 0 35px rgba(16, 185, 129, 0.4), 0 12px 30px rgba(5, 150, 105, 0.25)'
                : '0 8px 24px rgba(0, 0, 0, 0.08)',
              transform: 'perspective(600px) rotateX(25deg)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              position: 'relative',
              transition: 'all 0.3s ease',
            }}
          >
            {/* Holographic Network Node in Center */}
            <div
              style={{
                width: '44px',
                height: '44px',
                borderRadius: '50%',
                background: totalDoing > 0 ? 'rgba(16, 185, 129, 0.25)' : 'rgba(148, 163, 184, 0.15)',
                border: totalDoing > 0 ? '2px solid #10b981' : '1.5px dashed #94a3b8',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                boxShadow: totalDoing > 0 ? '0 0 20px #10b981' : 'none',
              }}
            >
              <ThunderboltFilled
                style={{
                  fontSize: '22px',
                  color: totalDoing > 0 ? '#10b981' : '#94a3b8',
                  animation: totalDoing > 0 ? 'spin 3s linear infinite' : 'none',
                }}
              />
            </div>
          </div>

          {/* Floating Pill: THE BRAIN 37 NOTES */}
          <div
            style={{
              position: 'absolute',
              top: '-32px',
              background: '#ffffff',
              border: totalDoing > 0 ? '1.5px solid #10b981' : '1.5px solid #e2e8f0',
              borderRadius: '20px',
              padding: '4px 14px',
              boxShadow: '0 8px 16px rgba(0,0,0,0.08)',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              whiteSpace: 'nowrap',
            }}
          >
            <span
              style={{
                width: 8,
                height: 8,
                borderRadius: '50%',
                background: totalDoing > 0 ? '#10b981' : '#94a3b8',
                boxShadow: totalDoing > 0 ? '0 0 8px #10b981' : 'none',
              }}
            />
            <span style={{ fontSize: '11px', fontWeight: 800, color: totalDoing > 0 ? '#065f46' : '#475569', letterSpacing: '0.5px' }}>
              THE BRAIN
            </span>
            <span style={{ fontSize: '11px', fontWeight: 800, color: '#1c1917' }}>
              {totalNotesCount} NOTES
            </span>
          </div>

          {/* Active Memory Bubble: Current Task or Standby */}
          <div
            style={{
              position: 'absolute',
              bottom: '-28px',
              background: totalDoing > 0 ? 'rgba(255, 255, 255, 0.98)' : 'rgba(248, 250, 252, 0.95)',
              border: totalDoing > 0 ? '1.5px solid #10b981' : '1px solid #cbd5e1',
              borderRadius: '12px',
              padding: '3px 12px',
              fontSize: '10px',
              fontWeight: 700,
              color: totalDoing > 0 ? '#059669' : '#64748b',
              boxShadow: totalDoing > 0 ? '0 4px 12px rgba(16, 185, 129, 0.18)' : '0 2px 6px rgba(0,0,0,0.05)',
              whiteSpace: 'nowrap',
              maxWidth: '240px',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
            }}
          >
            {activeTaskAny
              ? `⚡ ${((activeTaskAny.input_data as any)?.task || (activeTaskAny as any)?.prompt || 'EXECUTING MISSION').slice(0, 24)}...`
              : '💤 STANDBY • NO ACTIVE TASKS'}
          </div>
        </div>
      </div>

      {/* Floating Zoom & Pan Controls (Bottom Right - Exactly like in screenshot) */}
      <div
        style={{
          position: 'absolute',
          bottom: '24px',
          right: '24px',
          display: 'flex',
          flexDirection: 'column',
          gap: '6px',
          zIndex: 10,
        }}
      >
        <button
          onClick={() => setZoom((z) => Math.min(1.6, z + 0.1))}
          style={{
            width: '36px',
            height: '36px',
            borderRadius: '50%',
            background: '#ffffff',
            border: '1px solid #e5e2d8',
            boxShadow: '0 4px 10px rgba(0,0,0,0.08)',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '16px',
            color: '#44403c',
          }}
          title="Zoom In"
        >
          <PlusOutlined />
        </button>
        <button
          onClick={() => setZoom((z) => Math.max(0.6, z - 0.1))}
          style={{
            width: '36px',
            height: '36px',
            borderRadius: '50%',
            background: '#ffffff',
            border: '1px solid #e5e2d8',
            boxShadow: '0 4px 10px rgba(0,0,0,0.08)',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '16px',
            color: '#44403c',
          }}
          title="Zoom Out"
        >
          <MinusOutlined />
        </button>
        <button
          onClick={() => {
            setZoom(1);
            setPan({ x: 0, y: 0 });
          }}
          style={{
            width: '36px',
            height: '36px',
            borderRadius: '50%',
            background: '#ffffff',
            border: '1px solid #e5e2d8',
            boxShadow: '0 4px 10px rgba(0,0,0,0.08)',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '15px',
            color: '#44403c',
          }}
          title="Reset View"
        >
          <HomeOutlined />
        </button>
      </div>
    </div>
  );
};

export default AgentsOfficeV3Canvas;
