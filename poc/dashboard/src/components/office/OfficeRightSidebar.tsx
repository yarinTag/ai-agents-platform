import React, { useState, useEffect } from 'react';
import { Input, Button, Dropdown, MenuProps, Tag, Progress, message, Tooltip } from 'antd';
import {
  DownOutlined,
  ThunderboltOutlined,
  CheckCircleOutlined,
  SyncOutlined,
  DeleteOutlined,
  ClockCircleOutlined,
  SendOutlined,
} from '@ant-design/icons';
import { Task } from '../../types/task';
import { Agent } from '../../types/agent';
import { createTask, deleteTask } from '../../services/api';

interface OfficeRightSidebarProps {
  agents: Agent[];
  tasks: Task[];
  onTaskCreated: () => void;
  onSelectDepartment?: (dept: string) => void;
  onSelectAgent?: (agent: Agent) => void;
}

interface DepartmentOption {
  key: string;
  name: string;
  color: string;
  suggestions: string[];
}

const DEPARTMENTS: DepartmentOption[] = [
  {
    key: 'Marketing',
    name: 'MARKETING',
    color: '#f43f5e',
    suggestions: ['Launch Q4 Growth Sprint', 'A/B Test Ad Copy', 'Weekly competitor pricing scan'],
  },
  {
    key: 'Emails',
    name: 'EMAILS',
    color: '#10b981',
    suggestions: ['Draft Cold Sequence v3', 'Triage Customer Inbox', 'Rebuild welcome sequence'],
  },
  {
    key: 'Delivery',
    name: 'DELIVERY',
    color: '#0ea5e9',
    suggestions: ['Run Zero-Defect Release Audit', 'Verify Test Repo Pipeline', 'Frontend build acceptance'],
  },
  {
    key: 'Sales',
    name: 'SALES',
    color: '#f59e0b',
    suggestions: ['Score Inbound Leads ICP', 'Forecast Pipeline Velocity', 'Enterprise pitch preparation'],
  },
  {
    key: 'Operations',
    name: 'OPERATIONS',
    color: '#8b5cf6',
    suggestions: ['Audit System SLA Health', 'Automate Workflow Sync', 'Data retention check'],
  },
  {
    key: 'Finance',
    name: 'FINANCE',
    color: '#6366f1',
    suggestions: ['Calculate Token Unit Economics', 'Monthly Margin Reconciliation', 'Invoicing audit'],
  },
];

export const OfficeRightSidebar: React.FC<OfficeRightSidebarProps> = ({
  agents,
  tasks,
  onTaskCreated,
  onSelectDepartment,
  onSelectAgent,
}) => {
  const [selectedDept, setSelectedDept] = useState<DepartmentOption>(DEPARTMENTS[0]);
  const [taskPrompt, setTaskPrompt] = useState<string>('');
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [activeFilter, setActiveFilter] = useState<'ALL' | 'BACKLOG' | 'IN PROGRESS' | 'WAITING' | 'DONE'>('ALL');

  // Live real-time progressing percentage map
  const [progressMap, setProgressMap] = useState<Record<string, number>>({});

  // Real-time ticking effect for running tasks
  useEffect(() => {
    const timer = setInterval(() => {
      setProgressMap((prev) => {
        let changed = false;
        const nextMap = { ...prev };

        tasks.forEach((t) => {
          if (t.status === 'running') {
            const current = nextMap[t.id] ?? 18;
            if (current < 100) {
              const increment = Math.floor(Math.random() * 8) + 4; // +4-12%
              nextMap[t.id] = Math.min(100, current + increment);
              changed = true;
            }
          } else if (t.status === 'completed') {
            nextMap[t.id] = 100;
          }
        });

        return changed ? nextMap : prev;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [tasks]);

  const handleAddTask = async (customPrompt?: string) => {
    const promptToSend = (customPrompt || taskPrompt).trim();
    if (!promptToSend) return;

    // Find lead or agent in this department
    const targetAgent =
      agents.find((a) => (a.department || '').toLowerCase().includes(selectedDept.name.toLowerCase().split(' ')[0])) ||
      agents[0];

    try {
      setSubmitting(true);
      const res = await createTask({
        agent_id: targetAgent ? targetAgent.id : 'chief-orchestrator',
        project_id: null,
        skill_id: null,
        input_data: {
          task: promptToSend,
          department: selectedDept.name,
          timestamp: new Date().toISOString(),
        },
      });

      message.success(`Task dispatched to ${selectedDept.name}!`);
      setTaskPrompt('');

      // Immediately register in local progress
      if (res?.data?.id) {
        setProgressMap((prev) => ({ ...prev, [res.data.id]: 15 }));
      }

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

  const menuItems: MenuProps['items'] = DEPARTMENTS.map((dept) => ({
    key: dept.key,
    label: (
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <span style={{ width: 8, height: 8, borderRadius: '50%', background: dept.color }} />
        <span>{dept.name}</span>
      </div>
    ),
    onClick: () => {
      setSelectedDept(dept);
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
    const rawPrompt = (t.input_data as any)?.task || (t.input_data as any)?.prompt || (t as any).prompt || `Mission #${t.id.slice(0, 8)}`;
    const deptInTask = (t.input_data as any)?.department || 'GENERAL';
    const currentPercent = t.status === 'completed' ? 100 : (progressMap[t.id] ?? (t.status === 'running' ? 35 : 0));
    const isRunning = t.status === 'running' && currentPercent < 100;
    const isDone = t.status === 'completed' || currentPercent >= 100;

    const matchedAgent = agents.find((a) => String(a.id) === String(t.agent_id));

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

  return (
    <div
      style={{
        width: '380px',
        minWidth: '360px',
        background: '#ffffff',
        borderLeft: '1px solid #e5e2d8',
        padding: '18px 20px',
        display: 'flex',
        flexDirection: 'column',
        gap: '16px',
        height: 'calc(100vh - 52px)',
        overflowY: 'auto',
      }}
    >
      {/* Top Add Task Input Card */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        <div
          style={{
            background: '#ffffff',
            borderRadius: '24px',
            border: '1.5px solid #e5e2d8',
            padding: '4px 8px',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            boxShadow: '0 4px 14px rgba(0,0,0,0.04)',
          }}
        >
          <Dropdown menu={{ items: menuItems }} trigger={['click']}>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                cursor: 'pointer',
                padding: '4px 8px',
                borderRadius: '12px',
                fontSize: '11px',
                fontWeight: 800,
                color: '#1c1917',
                whiteSpace: 'nowrap',
                background: '#f7f6f2',
              }}
            >
              <span style={{ width: 7, height: 7, borderRadius: '50%', background: selectedDept.color }} />
              <span>{selectedDept.name}</span>
              <DownOutlined style={{ fontSize: '9px', color: '#78716c' }} />
            </div>
          </Dropdown>

          <Input
            placeholder={`Type a task for ${selectedDept.name.toLowerCase()}...`}
            value={taskPrompt}
            onChange={(e) => setTaskPrompt(e.target.value)}
            onPressEnter={() => handleAddTask()}
            variant="borderless"
            style={{
              fontSize: '12px',
              color: '#1c1917',
              padding: '2px 4px',
            }}
          />

          <Button
            type="primary"
            onClick={() => handleAddTask()}
            loading={submitting}
            style={{
              background: '#1c1917',
              borderColor: '#1c1917',
              borderRadius: '18px',
              fontWeight: 800,
              fontSize: '11px',
              height: '28px',
              padding: '0 12px',
              color: '#fff',
            }}
          >
            ADD
          </Button>
        </div>

        {/* Quick Suggestion Chips */}
        <div style={{ display: 'flex', gap: '4px', overflowX: 'auto', paddingBottom: '2px' }}>
          {selectedDept.suggestions.map((sug, sIdx) => (
            <button
              key={sIdx}
              onClick={() => handleAddTask(sug)}
              style={{
                background: '#f5f4ef',
                border: '1px solid #e7e4da',
                borderRadius: '10px',
                padding: '2px 8px',
                fontSize: '9px',
                fontWeight: 600,
                color: '#57534e',
                cursor: 'pointer',
                whiteSpace: 'nowrap',
              }}
              title="Click to dispatch instantly"
            >
              + {sug}
            </button>
          ))}
        </div>
      </div>

      {/* THE BRAIN Widget Card */}
      <div
        style={{
          background: '#ffffff',
          borderRadius: '16px',
          border: '1px solid #e5e2d8',
          padding: '14px 16px',
          boxShadow: '0 4px 12px rgba(0,0,0,0.03)',
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
        }}
      >
        {/* Brain Graphic Node */}
        <div
          style={{
            width: '44px',
            height: '44px',
            borderRadius: '12px',
            background: runningTasks.length > 0 ? '#ecfdf5' : '#f0fdf4',
            border: runningTasks.length > 0 ? '1.5px solid #10b981' : '1px solid #bbf7d0',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: runningTasks.length > 0 ? '0 0 12px rgba(16, 185, 129, 0.3)' : 'none',
          }}
        >
          <ThunderboltOutlined
            style={{
              color: '#16a34a',
              fontSize: '20px',
              animation: runningTasks.length > 0 ? 'spin 3s linear infinite' : 'none',
            }}
          />
        </div>

        <div style={{ flex: 1 }}>
          <div style={{ fontSize: '11px', fontWeight: 800, color: '#1c1917', letterSpacing: '0.6px' }}>
            THE BRAIN <span style={{ color: '#059669' }}>{37 + doneTasks.length} NOTES</span>
          </div>
          <div style={{ fontSize: '10px', color: '#78716c', marginTop: '2px' }}>
            {runningTasks.length > 0 ? (
              <span style={{ color: '#10b981', fontWeight: 700 }}>
                ⚡ {runningTasks.length} task in flight across departments
              </span>
            ) : (
              <span>All departments synchronized & ready</span>
            )}
          </div>
          <div
            onClick={() => {
              const brainAgent = agents.find((a) => a.id === 'chief-orchestrator');
              if (brainAgent && onSelectAgent) onSelectAgent(brainAgent);
            }}
            style={{ fontSize: '10px', fontWeight: 700, color: '#059669', marginTop: '3px', cursor: 'pointer' }}
          >
            Open Executive HQ Agent →
          </div>
        </div>
      </div>

      {/* TASK STATUS Section Header */}
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '13px', fontWeight: 800, color: '#1c1917', letterSpacing: '0.8px' }}>
              TASK STATUS
            </span>
            <span
              style={{
                fontSize: '9px',
                fontWeight: 800,
                color: runningTasks.length > 0 ? '#10b981' : '#78716c',
                border: runningTasks.length > 0 ? '1px solid #10b981' : '1px solid #d6d3c8',
                borderRadius: '6px',
                padding: '1px 5px',
                display: 'flex',
                alignItems: 'center',
                gap: '3px',
              }}
            >
              {runningTasks.length > 0 && <SyncOutlined spin />} LIVE
            </span>
          </div>
          <span style={{ fontSize: '10px', fontWeight: 700, color: '#78716c', letterSpacing: '0.5px' }}>
            WHOLE OFFICE
          </span>
        </div>

        {/* Dynamic Task Filters Pills */}
        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '14px' }}>
          {[
            { key: 'ALL', label: `ALL ${displayTasks.length}` },
            { key: 'IN PROGRESS', label: `IN PROGRESS ${runningTasks.length}` },
            { key: 'BACKLOG', label: `BACKLOG ${backlogTasks.length}` },
            { key: 'DONE', label: `DONE ${doneTasks.length}` },
          ].map((tab) => {
            const isSelected = activeFilter === tab.key;
            return (
              <button
                key={tab.key}
                onClick={() => setActiveFilter(tab.key as any)}
                style={{
                  background: isSelected ? '#1c1917' : '#ffffff',
                  color: isSelected ? '#ffffff' : '#78716c',
                  border: `1px solid ${isSelected ? '#1c1917' : '#e5e2d8'}`,
                  borderRadius: '16px',
                  padding: '3px 10px',
                  fontSize: '9px',
                  fontWeight: 800,
                  cursor: 'pointer',
                  letterSpacing: '0.5px',
                  transition: 'all 0.15s ease',
                }}
              >
                {tab.label}
              </button>
            );
          })}
        </div>

        {/* Tasks List Cards */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {filteredTasks.length === 0 ? (
            <div
              style={{
                textAlign: 'center',
                padding: '24px 12px',
                color: '#a8a29e',
                fontSize: '11px',
                background: '#fbfaf8',
                borderRadius: '12px',
                border: '1px dashed #e2ded5',
              }}
            >
              No tasks in {activeFilter}. Type a mission above to start!
            </div>
          ) : (
            filteredTasks.map((t) => (
              <div
                key={t.id}
                onClick={() => {
                  if (t.agentObj && onSelectAgent) onSelectAgent(t.agentObj);
                }}
                style={{
                  background: '#ffffff',
                  borderRadius: '12px',
                  border: t.status === 'IN PROGRESS' ? '1px solid #10b981' : '1px solid #e7e4da',
                  padding: '12px 14px',
                  boxShadow: t.status === 'IN PROGRESS' ? '0 4px 12px rgba(16, 185, 129, 0.08)' : '0 2px 6px rgba(0,0,0,0.02)',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: '10px' }}>
                  {/* Percentage Badge */}
                  <div
                    style={{
                      border: t.status === 'DONE' ? '1.5px solid #10b981' : '1.5px solid #d6d3c8',
                      borderRadius: '12px',
                      padding: '2px 6px',
                      fontSize: '10px',
                      fontWeight: 800,
                      color: t.status === 'DONE' ? '#059669' : '#1c1917',
                      lineHeight: 1,
                      background: t.status === 'DONE' ? '#ecfdf5' : '#ffffff',
                    }}
                  >
                    {t.status === 'DONE' ? '✓' : `${t.percent}%`}
                  </div>

                  {/* Title & Metadata */}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div
                      style={{
                        fontSize: '12px',
                        fontWeight: 700,
                        color: '#1c1917',
                        lineHeight: '1.3',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}
                      title={t.title}
                    >
                      {t.title}
                    </div>
                    <div
                      style={{
                        fontSize: '9px',
                        fontWeight: 700,
                        color: '#a8a29e',
                        letterSpacing: '0.5px',
                        marginTop: '3px',
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                      }}
                    >
                      <span>
                        {t.agentName} · {t.dept}
                      </span>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <span>{t.time}</span>
                        <Tooltip title="Delete task">
                          <DeleteOutlined
                            onClick={(e) => handleDeleteTask(e, t.id)}
                            style={{ color: '#d97706', fontSize: '10px', cursor: 'pointer' }}
                          />
                        </Tooltip>
                      </div>
                    </div>

                    {/* Progress Line */}
                    <div
                      style={{
                        width: '100%',
                        height: '3px',
                        background: '#f5f3ee',
                        borderRadius: '2px',
                        marginTop: '8px',
                        overflow: 'hidden',
                      }}
                    >
                      <div
                        style={{
                          width: `${t.percent}%`,
                          height: '100%',
                          background: t.status === 'DONE' ? '#10b981' : '#1c1917',
                          transition: 'width 0.4s ease-out',
                        }}
                      />
                    </div>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};

export default OfficeRightSidebar;
