import React, { useState, useEffect, useMemo } from 'react';
import {
  Calendar,
  Badge,
  Card,
  Row,
  Col,
  Statistic,
  Button,
  Table,
  Tag,
  Switch,
  Space,
  Tabs,
  Typography,
  Tooltip,
  Popconfirm,
  message,
  Empty,
  Modal,
} from 'antd';
import type { Dayjs } from 'dayjs';
import dayjs from 'dayjs';
import {
  CalendarOutlined,
  ClockCircleOutlined,
  PlayCircleOutlined,
  PlusOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ExclamationCircleOutlined,
  SyncOutlined,
  DeleteOutlined,
  QuestionCircleOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import { ScheduledJob, ApprovalRequest } from '../types/scheduler';
import { Agent } from '../types/agent';
import { Project } from '../types/project';
import { Task } from '../types/task';
import {
  getSchedules,
  toggleSchedule,
  deleteSchedule,
  triggerScheduleNow,
  getAgents,
  getProjects,
  getTasks,
  getPendingApprovals,
} from '../services/api';
import { CronBuilderModal } from '../components/scheduler/CronBuilderModal';
import { ApprovalModal } from '../components/approval/ApprovalModal';

const { Title, Text, Paragraph } = Typography;

export const CalendarView: React.FC = () => {
  const [schedules, setSchedules] = useState<ScheduledJob[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
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

  const fetchData = async () => {
    try {
      setLoading(true);
      const [schedRes, agRes, projRes, taskRes, appRes] = await Promise.all([
        getSchedules().catch(() => ({ data: [] })),
        getAgents().catch(() => ({ data: [] })),
        getProjects().catch(() => ({ data: [] })),
        getTasks().catch(() => ({ data: [] })),
        getPendingApprovals().catch(() => ({ data: [] })),
      ]);

      setSchedules(schedRes.data || []);
      setAgents(agRes.data || []);
      setProjects(projRes.data || []);
      setTasks(taskRes.data || []);
      setPendingApprovals(appRes.data || []);
    } catch (err) {
      console.error('Failed to load scheduler data:', err);
      message.error('Failed to load scheduler data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 10000); // refresh every 10s
    return () => clearInterval(interval);
  }, []);

  const handleToggle = async (job: ScheduledJob, enabled: boolean) => {
    try {
      await toggleSchedule(job.id, enabled);
      message.success(`Schedule ${enabled ? 'enabled' : 'paused'}`);
      fetchData();
    } catch (err) {
      message.error('Failed to toggle schedule state');
    }
  };

  const handleDelete = async (jobId: string) => {
    try {
      await deleteSchedule(jobId);
      message.success('Scheduled job deleted');
      fetchData();
    } catch (err) {
      message.error('Failed to delete schedule');
    }
  };

  const handleTriggerNow = async (jobId: string) => {
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
    const dueJobs = schedules.filter((s) => {
      if (!s.enabled || !s.next_run_at) return false;
      return dayjs(s.next_run_at).format('YYYY-MM-DD') === dateStr;
    });

    // 2. Tasks executed on this day
    const dayTasks = tasks.filter((t) => {
      const createdAt = t.created_at || (t as any).timestamp;
      if (!createdAt) return false;
      return dayjs(createdAt).format('YYYY-MM-DD') === dateStr;
    });

    if (dueJobs.length === 0 && dayTasks.length === 0) return null;

    return (
      <div
        style={{ fontSize: '11px', maxHeight: '72px', overflow: 'hidden' }}
        onClick={(e) => {
          e.stopPropagation();
          setSelectedDate(value);
          setDateModalVisible(true);
        }}
      >
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
            ⏰ {dayjs(j.next_run_at).format('HH:mm')} {j.name}
          </div>
        ))}
        {dayTasks.slice(0, 2).map((t) => {
          const status = String(t.status).toLowerCase();
          const isDone = status === 'completed';
          const isFail = status === 'failed';
          const isRun = status === 'running';

          return (
            <div
              key={t.id}
              style={{
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
            </div>
          );
        })}
        {dayTasks.length > 2 && (
          <div style={{ color: '#8b949e', fontSize: '10px' }}>
            +{dayTasks.length - 2} more...
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
            {record.enabled ? dayjs(nextRun).format('YYYY-MM-DD HH:mm:ss') : 'Paused'}
          </div>
          {record.enabled && (
            <div style={{ fontSize: '11px', color: '#8b949e' }}>
              in {dayjs(nextRun).fromNow(true)}
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
              {dayjs(record.last_run_at).format('MM-DD HH:mm')}
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
              onClick={() => handleTriggerNow(record.id)}
            />
          </Tooltip>
          <Popconfirm
            title="Delete this schedule?"
            onConfirm={() => handleDelete(record.id)}
            okText="Yes"
            cancelText="No"
          >
            <Button
              type="text"
              danger
              icon={<DeleteOutlined style={{ fontSize: '16px' }} />}
            />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div style={{ padding: '24px', background: '#0a0d12', minHeight: '100vh', color: '#e6edf3' }}>
      {/* Top Header */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '20px',
        }}
      >
        <div>
          <Title level={2} style={{ color: '#f3f4f6', margin: 0 }}>
            🗓️ Schedule & Calendar Hub
          </Title>
          <Text type="secondary">
            Manage recurring cron jobs, inspect agent calendar executions, and approve pending agent actions.
          </Text>
        </div>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          size="large"
          onClick={() => setModalVisible(true)}
          style={{ background: '#10b981', borderColor: '#10b981', fontWeight: 600 }}
        >
          New Scheduled Job
        </Button>
      </div>

      {/* KPI Stats Row */}
      <Row gutter={[16, 16]} style={{ marginBottom: '24px' }}>
        <Col xs={24} sm={12} md={6}>
          <Card
            bordered={false}
            style={{ background: '#161b22', border: '1px solid #30363d' }}
          >
            <Statistic
              title={<span style={{ color: '#8b949e' }}>Total Cron Jobs</span>}
              value={schedules.length}
              prefix={<ClockCircleOutlined style={{ color: '#38bdf8' }} />}
              valueStyle={{ color: '#f3f4f6' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card
            bordered={false}
            style={{ background: '#161b22', border: '1px solid #30363d' }}
          >
            <Statistic
              title={<span style={{ color: '#8b949e' }}>Active Schedules</span>}
              value={schedules.filter((s) => s.enabled).length}
              prefix={<ThunderboltOutlined style={{ color: '#4ade80' }} />}
              valueStyle={{ color: '#4ade80' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card
            bordered={false}
            style={{ background: '#161b22', border: '1px solid #30363d' }}
          >
            <Statistic
              title={<span style={{ color: '#8b949e' }}>Active Agents</span>}
              value={agents.length}
              prefix={<CalendarOutlined style={{ color: '#a855f7' }} />}
              valueStyle={{ color: '#c084fc' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card
            bordered={false}
            style={{
              background: pendingApprovals.length > 0 ? 'rgba(245, 158, 11, 0.1)' : '#161b22',
              border:
                pendingApprovals.length > 0 ? '1px solid #f59e0b' : '1px solid #30363d',
            }}
          >
            <Statistic
              title={<span style={{ color: '#8b949e' }}>Action Required / Approvals</span>}
              value={pendingApprovals.length}
              prefix={<QuestionCircleOutlined style={{ color: '#f59e0b' }} />}
              valueStyle={{ color: pendingApprovals.length > 0 ? '#f59e0b' : '#f3f4f6' }}
            />
          </Card>
        </Col>
      </Row>

      {/* Main Tabs */}
      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        type="card"
        items={[
          {
            key: 'calendar',
            label: (
              <span>
                <CalendarOutlined /> Calendar View
              </span>
            ),
            children: (
              <Card
                bordered={false}
                style={{
                  background: '#161b22',
                  border: '1px solid #30363d',
                  borderRadius: '12px',
                  padding: '12px',
                }}
              >
                <Calendar
                  dateCellRender={dateCellRender}
                  style={{ background: 'transparent' }}
                />
              </Card>
            ),
          },
          {
            key: 'schedules',
            label: (
              <span>
                <ClockCircleOutlined /> Scheduled Jobs Registry ({schedules.length})
              </span>
            ),
            children: (
              <Card
                bordered={false}
                style={{
                  background: '#161b22',
                  border: '1px solid #30363d',
                  borderRadius: '12px',
                }}
              >
                <Table
                  dataSource={schedules}
                  columns={columns}
                  rowKey="id"
                  loading={loading}
                  pagination={{ pageSize: 8 }}
                />
              </Card>
            ),
          },
          {
            key: 'approvals',
            label: (
              <span>
                <Badge count={pendingApprovals.length} offset={[8, 0]}>
                  <QuestionCircleOutlined /> Approvals Inbox ({pendingApprovals.length})
                </Badge>
              </span>
            ),
            children: (
              <Card
                bordered={false}
                style={{
                  background: '#161b22',
                  border: '1px solid #30363d',
                  borderRadius: '12px',
                }}
              >
                {pendingApprovals.length === 0 ? (
                  <Empty
                    description={
                      <span style={{ color: '#8b949e' }}>
                        No pending approvals or questions from agents. All systems running autonomously!
                      </span>
                    }
                    style={{ padding: '40px 0' }}
                  />
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                    {pendingApprovals.map((app) => {
                      const reqAgent = agentMap.get(app.requester_agent_id);
                      return (
                        <Card
                          key={app.id}
                          size="small"
                          style={{
                            background: '#0d1117',
                            borderColor: '#30363d',
                            borderRadius: '8px',
                          }}
                        >
                          <div
                            style={{
                              display: 'flex',
                              justifyContent: 'space-between',
                              alignItems: 'center',
                              marginBottom: '8px',
                            }}
                          >
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                              <span style={{ fontSize: '20px' }}>{reqAgent?.avatar || '🤖'}</span>
                              <span style={{ fontWeight: 600, color: '#f3f4f6' }}>
                                {reqAgent?.name || app.requester_agent_id}
                              </span>
                              <Tag color={app.interaction_type === 'QUESTION' ? 'blue' : 'gold'}>
                                {app.interaction_type}
                              </Tag>
                            </div>
                            <Button
                              type="primary"
                              size="small"
                              style={{ background: '#f59e0b', borderColor: '#f59e0b', fontWeight: 600 }}
                              onClick={() => {
                                setSelectedApproval(app);
                                setApprovalModalVisible(true);
                              }}
                            >
                              Review & Respond
                            </Button>
                          </div>
                          <div style={{ fontWeight: 500, color: '#e6edf3', marginBottom: '4px' }}>
                            {app.title}
                          </div>
                          <Paragraph
                            style={{
                              color: '#8b949e',
                              fontSize: '13px',
                              marginBottom: 0,
                              whiteSpace: 'pre-wrap',
                            }}
                          >
                            {app.content}
                          </Paragraph>
                        </Card>
                      );
                    })}
                  </div>
                )}
              </Card>
            ),
          },
        ]}
      />

      {/* Cron Builder Modal */}
      <CronBuilderModal
        visible={modalVisible}
        onClose={() => setModalVisible(false)}
        onSuccess={fetchData}
        agents={agents}
        projects={projects}
      />

      {/* Approval / HITL Modal */}
      <ApprovalModal
        visible={approvalModalVisible}
        request={selectedApproval}
        agent={selectedApproval ? agentMap.get(selectedApproval.requester_agent_id) : null}
        onClose={() => {
          setApprovalModalVisible(false);
          setSelectedApproval(null);
        }}
        onSuccess={fetchData}
      />

      {/* Date Inspection Modal */}
      {selectedDate && (
        <Modal
          title={`Activity & Schedules for ${selectedDate.format('YYYY-MM-DD')}`}
          open={dateModalVisible}
          onCancel={() => setDateModalVisible(false)}
          footer={null}
        >
          <div style={{ maxHeight: '400px', overflowY: 'auto' }}>
            <h4 style={{ color: '#10b981' }}>Scheduled Triggers:</h4>
            {schedules
              .filter(
                (s) =>
                  s.enabled &&
                  s.next_run_at &&
                  dayjs(s.next_run_at).format('YYYY-MM-DD') === selectedDate.format('YYYY-MM-DD')
              )
              .map((s) => (
                <div key={s.id} style={{ marginBottom: '8px' }}>
                  <b>{dayjs(s.next_run_at).format('HH:mm')}</b>: {s.name} ({s.agent_id})
                </div>
              ))}

            <h4 style={{ color: '#38bdf8', marginTop: '16px' }}>Tasks Executed:</h4>
            {tasks
              .filter(
                (t) =>
                  dayjs(t.created_at || (t as any).timestamp).format('YYYY-MM-DD') ===
                  selectedDate.format('YYYY-MM-DD')
              )
              .map((t) => (
                <div key={t.id} style={{ marginBottom: '8px' }}>
                  <b>Task #{t.id}</b> ({t.agent_id}): {String(t.status).toUpperCase()}
                </div>
              ))}
          </div>
        </Modal>
      )}
    </div>
  );
};
export default CalendarView;
