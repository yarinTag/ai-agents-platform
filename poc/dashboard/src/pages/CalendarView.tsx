import { Typography } from 'antd';
import { ResourceSection } from './ResourceSection';
import React from 'react';
import { Calendar, Badge, Card, Row, Col, Statistic, Button, Table, Tag, Tabs, Empty, Modal } from 'antd';
import { calendarDay } from './calendarDates';
import { CalendarOutlined, ClockCircleOutlined, PlusOutlined, QuestionCircleOutlined, ThunderboltOutlined } from '@ant-design/icons';
import { Task } from '../types/task';
import { CronBuilderModal } from '../components/scheduler/CronBuilderModal';
import { ApprovalModal } from '../components/approval/ApprovalModal';

import { useCalendarViewPage } from './useCalendarViewPage';

const { Title, Paragraph } = Typography;

export const CalendarView: React.FC = () => {
  const model = useCalendarViewPage();
  const {
    schedules,
    resourceErrors,
    agents,
    projects,
    tasks,
    pendingApprovals,
    loading,
    modalVisible,
    setModalVisible,
    activeTab,
    setActiveTab,
    selectedApproval,
    setSelectedApproval,
    approvalModalVisible,
    setApprovalModalVisible,
    selectedDate,
    dateModalVisible,
    setDateModalVisible,
    fetchData,
    agentMap,
    dateCellRender,
    columns,
  } = model;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', width: '100%' }}>
      {/* Top Header */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <div>
          <Title level={2} style={{ color: '#f0f6fc', margin: 0, fontWeight: 700 }}>
            🗓️ Schedule & Calendar Hub
          </Title>
          <div style={{ color: '#8b949e', fontSize: '13px', marginTop: '4px' }}>
            Manage recurring cron jobs, inspect agent calendar executions, and approve pending agent actions.
          </div>
        </div>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          size="large"
          disabled={loading || Boolean(resourceErrors.schedules || resourceErrors.agents || resourceErrors.projects)}
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
              value={resourceErrors.schedules ? 'Unavailable' : schedules.length}
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
              value={resourceErrors.schedules ? 'Unavailable' : schedules.filter((s) => s.enabled).length}
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
              value={resourceErrors.agents ? 'Unavailable' : agents.length}
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
              value={resourceErrors.approvals ? 'Unavailable' : pendingApprovals.length}
              prefix={<QuestionCircleOutlined style={{ color: '#f59e0b' }} />}
              valueStyle={{ color: pendingApprovals.length > 0 ? '#f59e0b' : '#f3f4f6' }}
            />
          </Card>
        </Col>
      </Row>

      <ResourceSection error={resourceErrors.schedules} onRetry={fetchData}><span /></ResourceSection>
      <ResourceSection error={resourceErrors.tasks} onRetry={fetchData}><span /></ResourceSection>
      <ResourceSection error={resourceErrors.agents || resourceErrors.projects} onRetry={fetchData}><span /></ResourceSection>
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
                <ResourceSection error={resourceErrors.schedules} onRetry={fetchData}>
                <Table
                  dataSource={schedules}
                  columns={columns}
                  rowKey="id"
                  loading={loading}
                  pagination={{ pageSize: 8 }}
                  scroll={{ x: 900 }}
                />
                </ResourceSection>
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
                <ResourceSection error={resourceErrors.approvals} onRetry={fetchData}>
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
                </ResourceSection>
              </Card>
            ),
          },
        ]}
      />

      {/* Cron Builder Modal */}
      <CronBuilderModal
        visible={modalVisible && !resourceErrors.schedules && !resourceErrors.agents && !resourceErrors.projects}
        onClose={() => setModalVisible(false)}
        onSuccess={fetchData}
        agents={agents}
        projects={projects}
      />

      {/* Approval / HITL Modal */}
      <ApprovalModal
        visible={approvalModalVisible && !resourceErrors.approvals}
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
                  calendarDay(s.next_run_at).format('YYYY-MM-DD') === selectedDate.format('YYYY-MM-DD')
              )
              .map((s) => (
                <div key={s.id} style={{ marginBottom: '8px' }}>
                  <b>{calendarDay(s.next_run_at).format('HH:mm')}</b>: {s.name} ({s.agent_id})
                </div>
              ))}

            <h4 style={{ color: '#38bdf8', marginTop: '16px' }}>Tasks Executed:</h4>
            {tasks
              .filter(
                (t) =>
                  calendarDay(t.created_at || (t as any).timestamp).format('YYYY-MM-DD') ===
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
