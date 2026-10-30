import type { AgentsOfficeV3CanvasProps, DepartmentDef } from './officeCanvasTypes';
import React, { useState } from 'react';
import { message } from 'antd';

import { Agent } from '../../types/agent';
import { Task } from '../../types/task';
import { createTask } from '../../services/api';

export function useOfficeCanvas({ agents, tasks, onSelectAgent, onSelectDepartment, onTaskCreated }: AgentsOfficeV3CanvasProps) {
  const [zoom, setZoom] = useState<number>(0.85);
  const [pan, setPan] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const [dragStart, setDragStart] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [liveSimRunning, setLiveSimRunning] = useState<boolean>(false);
  const [lastDispatchedDept, setLastDispatchedDept] = useState<string | null>(null);
  const [hoveredDept, setHoveredDept] = useState<string | null>(null);

  // Central Brain Coordinates (perfectly centered on 1280x1000 workspace)
  const brainPos = { x: 640, y: 500 };

  const PRESET_SLOTS = [
    { posX: 640, posY: 180, dotColor: '#3b82f6', stat1: 'TASKS TOTAL', stat2: 'PIPELINE' },  // North
    { posX: 1060, posY: 220, dotColor: '#0ea5e9', stat1: 'TASKS TOTAL', stat2: 'PIPELINE' }, // North-East
    { posX: 1100, posY: 500, dotColor: '#f59e0b', stat1: 'TASKS TOTAL', stat2: 'PIPELINE' }, // East
    { posX: 960, posY: 820, dotColor: '#8b5cf6', stat1: 'TASKS TOTAL', stat2: 'PIPELINE' },  // South-East
    { posX: 640, posY: 820, dotColor: '#6366f1', stat1: 'TASKS TOTAL', stat2: 'PIPELINE' },  // South
    { posX: 320, posY: 820, dotColor: '#ec4899', stat1: 'TASKS TOTAL', stat2: 'PIPELINE' },  // South-West
    { posX: 180, posY: 500, dotColor: '#f43f5e', stat1: 'TASKS TOTAL', stat2: 'PIPELINE' },  // West
    { posX: 220, posY: 220, dotColor: '#10b981', stat1: 'TASKS TOTAL', stat2: 'PIPELINE' },  // North-West
  ];

  const DEPARTMENTS: DepartmentDef[] = React.useMemo(() => {
    const set = new Set<string>();
    agents.forEach((a) => {
      if (a.role_type === 'WORKFLOW_AUTOMATION' || (a as any).is_workflow_agent || a.department === 'Workflow Automations') return;
      const d = (a.department || '').trim();
      if (d) set.add(d);
    });
    const uniqueDepts = Array.from(set);

    return uniqueDepts.map((deptName, idx) => {
      const slot = PRESET_SLOTS[idx % PRESET_SLOTS.length];
      return {
        key: deptName,
        name: deptName.toUpperCase(),
        dotColor: slot.dotColor,
        stat1Label: slot.stat1,
        stat2Label: slot.stat2,
        posX: slot.posX,
        posY: slot.posY,
        desks: [
          { title: `${deptName.toUpperCase()} LEAD`, isLead: true, relX: -60, relY: -30 },
          { title: 'SPECIALIST', relX: 60, relY: -30 },
          { title: 'OPERATOR', relX: -60, relY: 40 },
          { title: 'ANALYST', relX: 60, relY: 40 },
        ],
      };
    });
  }, [agents]);

  // Helper: Find real agent for a specific desk
  const findAgentForDesk = (deptKey: string, deskTitle: string, deskIdx: number): Agent | null => {
    // 1. Direct department filter
    const deptAgents = agents.filter(
      (a) => (a.department || '').toLowerCase().includes(deptKey.toLowerCase())
    );

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

    // Return null for unassigned open desks
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
      agentsCount: deptAgents.length,
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

  // Trigger a live test task that connects through the office in real time
  const handleTriggerLiveMission = async () => {
    if (DEPARTMENTS.length === 0 || agents.length === 0) {
      message.warning('Create at least one agent and department first!');
      return;
    }
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
            task: `Live Mission: Sync ${targetDept.name} with Central Dispatch`,
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

  return {
    agents, tasks, onSelectAgent, onSelectDepartment, onTaskCreated,
    zoom, setZoom, pan, setPan, isDragging,
    setIsDragging, dragStart, setDragStart, liveSimRunning, setLiveSimRunning,
    lastDispatchedDept, setLastDispatchedDept, hoveredDept, setHoveredDept, brainPos,
    PRESET_SLOTS, DEPARTMENTS, findAgentForDesk, getAgentActiveTask, getDeptStats,
    activeTaskAny, totalDoing, totalDone, handleTriggerLiveMission, handleMouseDown,
    handleMouseMove, handleMouseUp, handleWheel,
  };
}
