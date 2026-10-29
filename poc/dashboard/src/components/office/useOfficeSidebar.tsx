import type { OfficeRightSidebarProps, DepartmentOption } from './officeSidebarTypes';
import React, { useState } from 'react';
import { MenuProps, message } from 'antd';

import { Task } from '../../types/task';

import { createTask, deleteTask } from '../../services/api';
import { useAuth } from '../../context/AuthContext';

const DEPT_PALETTE = [
  '#3b82f6',
  '#8b5cf6',
  '#06b6d4',
  '#10b981',
  '#f59e0b',
  '#f43f5e',
  '#0ea5e9',
  '#6366f1',
  '#ec4899',
  '#14b8a6',
];

export function useOfficeSidebar({ agents, tasks, onTaskCreated, onSelectDepartment, onSelectAgent }: OfficeRightSidebarProps) {
  const { departments } = useAuth();

  const departmentList: DepartmentOption[] = React.useMemo(() => {
    const list: DepartmentOption[] = [];
    const seen = new Set<string>();

    // 1. Populate from enterprise departments
    if (departments && departments.length > 0) {
      departments.forEach((dept) => {
        const rawDept = dept.name.trim();
        const lower = rawDept.toLowerCase();
        if (!seen.has(lower)) {
          seen.add(lower);
          const color = DEPT_PALETTE[list.length % DEPT_PALETTE.length];
          list.push({
            key: rawDept,
            name: rawDept,
            color,
            suggestions: [
              `Dispatch task to ${rawDept}`,
              `Review ${rawDept} sprint goals`,
              `Verify ${rawDept} outputs`,
            ],
          });
        }
      });
    }

    // 2. Fallback to agents departments if empty
    if (list.length === 0) {
      agents.forEach((agent) => {
        const rawDept = (agent.department || '').trim();
        if (!rawDept) return;
        const lower = rawDept.toLowerCase();
        if (!seen.has(lower)) {
          seen.add(lower);
          const color = DEPT_PALETTE[list.length % DEPT_PALETTE.length];
          list.push({
            key: rawDept,
            name: rawDept,
            color,
            suggestions: [
              `Dispatch task to ${rawDept}`,
              `Review ${rawDept} sprint goals`,
              `Verify ${rawDept} outputs`,
            ],
          });
        }
      });
    }

    return list;
  }, [departments, agents]);

  const [selectedDeptKey, setSelectedDeptKey] = useState<string>('');

  const selectedDept = React.useMemo(() => {
    if (departmentList.length === 0) return null;
    return (
      departmentList.find((d) => d.key.toLowerCase() === selectedDeptKey.toLowerCase()) ||
      departmentList[0]
    );
  }, [departmentList, selectedDeptKey]);

  const [taskPrompt, setTaskPrompt] = useState<string>('');
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [activeFilter, setActiveFilter] = useState<'ALL' | 'BACKLOG' | 'IN PROGRESS' | 'WAITING' | 'DONE'>('ALL');

  const handleAddTask = async (customPrompt?: string) => {
    const promptToSend = (customPrompt || taskPrompt).trim();
    if (!promptToSend) return;

    const deptKey = selectedDept ? selectedDept.key : 'General';
    const deptName = selectedDept ? selectedDept.name : 'GENERAL';

    // Find lead or agent in this department
    const targetAgent = selectedDept
      ? agents.find((a) => (a.department || '').toLowerCase().trim() === selectedDept.key.toLowerCase().trim()) ||
        agents.find((a) => (a.department || '').toLowerCase().includes(selectedDept.key.toLowerCase())) ||
        agents[0]
      : agents[0];

    try {
      setSubmitting(true);
      await createTask({
        agent_id: targetAgent ? targetAgent.id : 'general-dispatcher',
        project_id: null,
        skill_id: null,
        input_data: {
          task: promptToSend,
          department: deptKey,
          timestamp: new Date().toISOString(),
        },
      });

      message.success(`Task dispatched to ${deptName}!`);
      setTaskPrompt('');
      onTaskCreated();
    } catch (err) {
      message.error('Failed to add task');
      console.error(err);
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeleteTask = async (e: React.MouseEvent, taskId: string) => {
    e.stopPropagation();
    try {
      await deleteTask(taskId);
      message.success('Task removed');
      onTaskCreated();
    } catch (err) {
      message.error('Failed to delete task');
    }
  };

  const menuItems: MenuProps['items'] = departmentList.map((dept) => ({
    key: dept.key,
    label: (
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <span style={{ width: 8, height: 8, borderRadius: '50%', background: dept.color }} />
        <span>{dept.name}</span>
      </div>
    ),
    onClick: () => {
      setSelectedDeptKey(dept.key);
      if (onSelectDepartment) onSelectDepartment(dept.key);
    },
  }));

  // Dynamic status mapping for all tasks
  const runningTasks = tasks.filter((t) => t.status === 'running');
  const backlogTasks = tasks.filter((t) => t.status === 'queued' || t.status === 'pending');
  const doneTasks = tasks.filter((t) => t.status === 'completed');
  const waitingTasks = tasks.filter((t) => t.status === 'cancelled' || t.status === 'failed');

  // Format tasks list for display
  const displayTasks = tasks.map((t) => {
    const matchedAgent = agents.find((a) => String(a.id) === String(t.agent_id));
    const rawPrompt = (t.input_data as any)?.task || (t.input_data as any)?.prompt || (t as any).prompt || `Mission #${t.id.slice(0, 8)}`;
    const deptInTask = (t.input_data as any)?.department || matchedAgent?.department || 'GENERAL';
    const isRunning = t.status === 'running';
    const isDone = t.status === 'completed';
    const currentPercent = isDone ? 100 : isRunning ? 50 : 0;

    return {
      id: t.id,
      title: rawPrompt,
      agentName: matchedAgent ? matchedAgent.name : t.agent_id,
      agentObj: matchedAgent,
      dept: deptInTask,
      percent: currentPercent,
      status: isDone ? 'DONE' : isRunning ? 'IN PROGRESS' : 'BACKLOG',
      time: t.created_at ? new Date(t.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'now',
    };
  });

  const filteredTasks = displayTasks.filter((t) => {
    if (activeFilter === 'ALL') return true;
    return t.status === activeFilter;
  });

  return {
    agents, tasks, onTaskCreated, onSelectDepartment, onSelectAgent,
    departments, departmentList, selectedDeptKey, setSelectedDeptKey, selectedDept,
    taskPrompt, setTaskPrompt, submitting, setSubmitting, activeFilter,
    setActiveFilter, handleAddTask, handleDeleteTask, menuItems, runningTasks,
    backlogTasks, doneTasks, waitingTasks, displayTasks, filteredTasks,
  };
}
