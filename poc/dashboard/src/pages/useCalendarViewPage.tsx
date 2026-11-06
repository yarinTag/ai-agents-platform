import { Link } from 'react-router-dom';
import { CalendarRun } from './CalendarRun';
import { getWorkflowExecutions } from '../services/workflowsApi';
import type { WorkflowExecution } from '../types/mcp';
import { usePermissions } from '../hooks/usePermissions';
import { useAuth } from '../context/AuthContext';
import { useRequestGeneration } from '../hooks/useRequestGeneration';
import { readResource } from './resourceLoading';
import { useState, useEffect, useMemo } from 'react';
import { Button, Tag, Switch, Space, Tooltip, Popconfirm, message } from 'antd';
import type { Dayjs } from 'dayjs';
import { calendarDay } from './calendarDates';
import { PlayCircleOutlined, DeleteOutlined } from '@ant-design/icons';
import { ScheduledJob, ApprovalRequest } from '../types/scheduler';
import { Agent } from '../types/agent';
import { Project } from '../types/project';
import { Task } from '../types/task';
import { getSchedules, toggleSchedule, deleteSchedule, triggerScheduleNow, getAgents, getProjects, getTasks, getPendingApprovals } from '../services/api';

export const useCalendarViewPage = () => {
  const { canManage, canOperate } = usePermissions();
  const { organization, activeDepartmentId } = useAuth();
  const [schedules, setSchedules] = useState<ScheduledJob[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [executions, setExecutions] = useState<WorkflowExecution[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [pendingApprovals, setPendingApprovals] = useState<ApprovalRequest[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [modalVisible, setModalVisible] = useState<boolean>(false);
  const [activeTab, setActiveTab] = useState<string>('calendar');

  // Selected approval for modal
  const [selectedApproval, setSelectedApproval] = useState<ApprovalRequest | null>(null);
  const [approvalModalVisible, setApprovalModalVisible] = useState<boolean>(false);

  // Selected date events modal
  const [selectedDate, setSelectedDate] = useState<Dayjs | null>(null);
  const [dateModalVisible, setDateModalVisible] = useState<boolean>(false);

  const [resourceErrors, setResourceErrors] = useState<{
    schedules: string | null; agents: string | null; projects: string | null;
    executions: string | null; tasks: string | null; approvals: string | null;
  }>({ executions: null, schedules: null, agents: null, projects: null, tasks: null, approvals: null });

  const { begin, invalidate } = useRequestGeneration();
  const fetchData = async () => {
    const current = begin();
    if (!current()) return;
    try {
      setLoading(true);
      const [schedulesError, agentsError, projectsError, tasksError, executionsError, approvalsError] = await Promise.all([
        readResource(getSchedules(), response => { if (current()) setSchedules(response.data || []); }, 'Schedules'),
        readResource(getAgents(), response => { if (current()) setAgents(response.data || []); }, 'Agents'),
        readResource(getProjects(), response => { if (current()) setProjects(response.data || []); }, 'Projects'),
        readResource(getTasks(), response => { if (current()) setTasks(response.data || []); }, 'Task history'),
        readResource(getWorkflowExecutions(undefined, 200, activeDepartmentId), response => { if (current()) setExecutions(response.data || []); }, 'Workflow executions'),
        readResource(getPendingApprovals(), response => { if (current()) setPendingApprovals(response.data || []); }, 'Approvals'),
      ]);
      if (!current()) return;
      setResourceErrors({
        schedules: schedulesError, agents: agentsError, projects: projectsError,
        executions: executionsError, tasks: tasksError, approvals: approvalsError,
      });
    } catch (err) {
      console.error('Failed to load scheduler data:', err);
      message.error('Failed to load scheduler data');
    } finally {
      if (current()) setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 10000); // refresh every 10s
    return () => { clearInterval(interval); invalidate(); };
  }, [organization?.id, activeDepartmentId, invalidate]);

  const handleToggle = async (job: ScheduledJob, enabled: boolean) => {
    if (resourceErrors.schedules) return;
    try {
      await toggleSchedule(job.id, enabled);
      message.success(`Schedule ${enabled ? 'enabled' : 'paused'}`);
      fetchData();
    } catch (err) {
      message.error('Failed to toggle schedule state');
    }
  };

  const handleDelete = async (jobId: string) => {
    if (resourceErrors.schedules) return;
    try {
      await deleteSchedule(jobId);
      message.success('Scheduled job deleted');
      fetchData();
    } catch (err) {
      message.error('Failed to delete schedule');
    }
  };

  const handleTriggerNow = async (jobId: string) => {
    if (resourceErrors.schedules) return;
    try {
      const res = await triggerScheduleNow(jobId);
      message.success(`Task triggered immediately! (Run #${res.data.task_id})`);
      fetchData();
    } catch (err) {
      message.error('Failed to trigger job');
    }
  };

  const agentMap = useMemo(() => {
    const map = new Map<string, Agent>();
    agents.forEach((a) => map.set(a.id, a));
    return map;
  }, [agents]);

  // Aggregate items by date (YYYY-MM-DD)
  const dateCellRender = (value: Dayjs) => {
    const dateStr = value.format('YYYY-MM-DD');

    // 1. Scheduled jobs due on this day
    const dueJobs = resourceErrors.schedules ? [] : schedules.filter((s) => {
      if (!s.enabled || !s.next_run_at) return false;
      return calendarDay(s.next_run_at).format('YYYY-MM-DD') === dateStr;
    });

    // 2. Tasks executed on this day
    const dayTasks = resourceErrors.tasks ? [] : tasks.filter((t) => {
      const createdAt = t.started_at || t.created_at;
      if (!createdAt) return false;
      return calendarDay(createdAt).format('YYYY-MM-DD') === dateStr;
    });

    const dayExecutions = resourceErrors.executions ? [] : executions.filter(run =>
      (run.started_at || run.created_at) && calendarDay(run.started_at || run.created_at).format('YYYY-MM-DD') === dateStr);

    if (dueJobs.length === 0 && dayTasks.length === 0 && dayExecutions.length === 0) return null;

    return (
      <div
        style={{ fontSize: '11px', maxHeight: '100px', overflowY: 'auto' }}
        onClick={(e) => {
          e.stopPropagation();
          setSelectedDate(value);
          setDateModalVisible(true);
        }}
      >
        <Button type="link" size="small" style={{ padding: 0, height: 'auto' }}
          onClick={event => { event.stopPropagation(); setSelectedDate(value); setDateModalVisible(true); }}>
          View day activity
        </Button>
        {dueJobs.map((j) => (
          <div
            key={j.id}
            style={{
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              marginBottom: '2px',
              padding: '1px 4px',
              borderRadius: '3px',
              background: 'rgba(168, 85, 247, 0.15)',
              border: '1px solid rgba(168, 85, 247, 0.4)',
              color: '#c084fc',
            }}
          >
            ⏰ {calendarDay(j.next_run_at).format('HH:mm')} {j.name}
          </div>
        ))}
        {dayTasks.slice(0, 2).map((t) => {
          const status = String(t.status).toLowerCase();
          const isDone = status === 'completed';
          const isFail = status === 'failed';
          const isRun = status === 'running';

          return (
            <Link
              to={`/tasks?taskId=${encodeURIComponent(t.id)}`}
              onClick={event => event.stopPropagation()}
              title={`Open logs for task ${t.id}`}
              key={t.id}
              style={{
                display: 'block',
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                marginBottom: '2px',
                padding: '1px 4px',
                borderRadius: '3px',
                background: isDone
                  ? 'rgba(34, 197, 94, 0.15)'
                  : isFail
                  ? 'rgba(239, 68, 68, 0.15)'
                  : isRun
                  ? 'rgba(59, 130, 246, 0.15)'
                  : 'rgba(148, 163, 184, 0.15)',
                color: isDone ? '#4ade80' : isFail ? '#f87171' : isRun ? '#60a5fa' : '#94a3b8',
              }}
            >
              {isDone ? '✓' : isFail ? '✗' : isRun ? '⟳' : '•'} {t.agent_id}: Task #{t.id}
            </Link>
          );
        })}
        {dayExecutions.slice(0, 2).map(run => <CalendarRun key={run.id} execution={run} compact />)}
        {(dayTasks.length > 2 || dayExecutions.length > 2) && (
          <div style={{ color: '#8b949e', fontSize: '10px' }}>
            +{Math.max(0, dayTasks.length - 2) + Math.max(0, dayExecutions.length - 2)} more...
          </div>
        )}
      </div>
    );
  };

  const columns = [
    {
      title: 'Schedule Name',
      dataIndex: 'name',
      key: 'name',
      render: (name: string, record: ScheduledJob) => (
        <div>
          <div style={{ fontWeight: 600, color: '#f3f4f6' }}>{name}</div>
          {record.description && (
            <div style={{ fontSize: '12px', color: '#8b949e' }}>{record.description}</div>
          )}
          <Tag style={{ marginTop: '4px', fontFamily: 'monospace' }}>
            {record.cron_expression}
          </Tag>
        </div>
      ),
    },
    {
      title: 'Target Agent',
      dataIndex: 'agent_id',
      key: 'agent_id',
      render: (agentId: string) => {
        const ag = agentMap.get(agentId);
        return (
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '18px' }}>{ag?.avatar || '🤖'}</span>
            <div>
              <div style={{ fontWeight: 500, color: '#e6edf3' }}>{ag?.name || agentId}</div>
              <div style={{ fontSize: '11px', color: '#8b949e' }}>
                {ag?.department || 'Engineering'}
              </div>
            </div>
          </div>
        );
      },
    },
    {
      title: 'Next Execution',
      dataIndex: 'next_run_at',
      key: 'next_run_at',
      render: (nextRun: string, record: ScheduledJob) => (
        <div>
          <div style={{ fontWeight: 500, color: record.enabled ? '#10b981' : '#6b7280' }}>
            {record.enabled ? calendarDay(nextRun).format('YYYY-MM-DD HH:mm:ss') : 'Paused'}
          </div>
          {record.enabled && (
            <div style={{ fontSize: '11px', color: '#8b949e' }}>
              in {calendarDay(nextRun).fromNow(true)}
            </div>
          )}
        </div>
      ),
    },
    {
      title: 'Last Status',
      key: 'last_status',
      render: (_: any, record: ScheduledJob) => {
        if (!record.last_run_at) {
          return <Tag color="default">Never Run</Tag>;
        }
        const st = record.last_status || 'UNKNOWN';
        const color =
          st === 'RUNNING' ? 'processing' : st === 'SKIPPED' ? 'warning' : 'success';
        return (
          <div>
            <Tag color={color}>{st}</Tag>
            <div style={{ fontSize: '11px', color: '#8b949e', marginTop: '2px' }}>
              {calendarDay(record.last_run_at).format('MM-DD HH:mm')}
            </div>
          </div>
        );
      },
    },
    {
      title: 'Active',
      dataIndex: 'enabled',
      key: 'enabled',
      render: (enabled: boolean, record: ScheduledJob) => (
        <Switch
          disabled={!canManage}
          checked={enabled}
          onChange={(checked) => handleToggle(record, checked)}
          checkedChildren="ON"
          unCheckedChildren="OFF"
        />
      ),
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_: any, record: ScheduledJob) => (
        <Space>
          <Tooltip title="Trigger Immediate Run">
            <Button
              type="text"
              icon={<PlayCircleOutlined style={{ color: '#10b981', fontSize: '16px' }} />}
              disabled={!canOperate} onClick={() => handleTriggerNow(record.id)}
            />
          </Tooltip>
          <Popconfirm disabled={!canManage}
            title="Delete this schedule?"
            onConfirm={() => handleDelete(record.id)}
            okText="Yes"
            cancelText="No"
          >
            <Button
              type="text"
              danger disabled={!canManage}
              icon={<DeleteOutlined style={{ fontSize: '16px' }} />}
            />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return {
    executions: resourceErrors.executions ? [] : executions,
    schedules: resourceErrors.schedules ? [] : schedules,
    resourceErrors,
    setSchedules,
    agents,
    setAgents,
    projects,
    setProjects,
    tasks: resourceErrors.tasks ? [] : tasks,
    setTasks,
    pendingApprovals: resourceErrors.approvals ? [] : pendingApprovals,
    setPendingApprovals,
    loading,
    setLoading,
    modalVisible,
    setModalVisible,
    activeTab,
    setActiveTab,
    selectedApproval,
    setSelectedApproval,
    approvalModalVisible,
    setApprovalModalVisible,
    selectedDate,
    setSelectedDate,
    dateModalVisible,
    setDateModalVisible,
    fetchData,
    handleToggle,
    handleDelete,
    handleTriggerNow,
    agentMap,
    dateCellRender,
    columns,
  };
};
