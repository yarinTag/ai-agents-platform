import React, { useState, useEffect } from 'react';
import {
  Modal,
  Tabs,
  Card,
  Button,
  Input,
  Select,
  Tag,
  List,
  Typography,
  Space,
  Badge,
  Avatar,
  message as antMessage,
  Spin,
  Alert,
  Divider,
} from 'antd';
import {
  TeamOutlined,
  CheckCircleOutlined,
  MessageOutlined,
  SendOutlined,
  BulbOutlined,
  RocketOutlined,
  PlusOutlined,
} from '@ant-design/icons';
import {
  getWarRoomSessions,
  createWarRoomSession,
  getWarRoomSession,
  sendWarRoomMessage,
  synthesizeWarRoomPlan,
} from '../../services/api';
import { WarRoomSession, WarRoomDetail, WarRoomMessageType } from '../../types/collab';

const { Text, Title, Paragraph } = Typography;
const { TextArea } = Input;
const { Option } = Select;

interface WarRoomModalProps {
  open: boolean;
  onClose: () => void;
  agents: any[];
  projectId?: string;
}

export const WarRoomModal: React.FC<WarRoomModalProps> = ({
  open,
  onClose,
  agents,
  projectId,
}) => {
  const [sessions, setSessions] = useState<WarRoomSession[]>([]);
  const [loading, setLoading] = useState(false);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [sessionDetail, setSessionDetail] = useState<WarRoomDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  // New session form
  const [newTitle, setNewTitle] = useState('');
  const [newTopic, setNewTopic] = useState('');
  const [newModerator, setNewModerator] = useState<string>('');
  const [newParticipants, setNewParticipants] = useState<string[]>([]);
  const [submittingSession, setSubmittingSession] = useState(false);

  // New message form
  const [msgAgentId, setMsgAgentId] = useState<string>('');
  const [msgType, setMsgType] = useState<WarRoomMessageType>('PROPOSAL');
  const [msgContent, setMsgContent] = useState('');
  const [sendingMsg, setSendingMsg] = useState(false);

  // Synthesis
  const [synthesizing, setSynthesizing] = useState(false);
  const [customPlan, setCustomPlan] = useState('');
  const [showSynthInput, setShowSynthInput] = useState(false);

  const fetchSessions = async () => {
    try {
      setLoading(true);
      const res = await getWarRoomSessions(projectId);
      setSessions(res.data);
      if (res.data.length > 0 && !activeSessionId) {
        setActiveSessionId(res.data[0].id);
      }
    } catch (err) {
      antMessage.error('Failed to load war room sessions');
    } finally {
      setLoading(false);
    }
  };

  const fetchSessionDetail = async (id: string) => {
    try {
      setDetailLoading(true);
      const res = await getWarRoomSession(id);
      setSessionDetail(res.data);
      if (res.data.session.participant_agent_ids.length > 0 && !msgAgentId) {
        setMsgAgentId(res.data.session.participant_agent_ids[0]);
      }
    } catch (err) {
      antMessage.error('Failed to load session details');
    } finally {
      setDetailLoading(false);
    }
  };

  useEffect(() => {
    if (open) {
      fetchSessions();
      if (agents.length > 0) {
        if (!newModerator) setNewModerator(agents[0].id);
        if (newParticipants.length === 0) {
          setNewParticipants(agents.slice(0, 3).map((a) => a.id));
        }
      }
    }
  }, [open]);

  useEffect(() => {
    if (activeSessionId) {
      fetchSessionDetail(activeSessionId);
    }
  }, [activeSessionId]);

  const handleCreateSession = async () => {
    if (!newTitle.trim() || !newTopic.trim() || !newModerator) {
      antMessage.warning('Please enter title, topic and choose a moderator');
      return;
    }
    try {
      setSubmittingSession(true);
      const res = await createWarRoomSession({
        title: newTitle,
        topic: newTopic,
        project_id: projectId,
        moderator_agent_id: newModerator,
        participant_agent_ids: newParticipants,
      });
      antMessage.success('War Room session initiated!');
      setNewTitle('');
      setNewTopic('');
      await fetchSessions();
      setActiveSessionId(res.data.id);
    } catch (err) {
      antMessage.error('Failed to initiate session');
    } finally {
      setSubmittingSession(false);
    }
  };

  const handleSendMessage = async () => {
    if (!activeSessionId || !msgContent.trim() || !msgAgentId) return;
    try {
      setSendingMsg(true);
      const round = sessionDetail ? Math.floor(sessionDetail.messages.length / 3) + 1 : 1;
      await sendWarRoomMessage(activeSessionId, {
        agent_id: msgAgentId,
        round_number: round,
        message_type: msgType,
        content: msgContent.trim(),
      });
      setMsgContent('');
      await fetchSessionDetail(activeSessionId);
    } catch (err) {
      antMessage.error('Failed to send deliberation message');
    } finally {
      setSendingMsg(false);
    }
  };

  const handleSynthesize = async () => {
    if (!activeSessionId) return;
    try {
      setSynthesizing(true);
      let plan = customPlan.trim();
      if (!plan && sessionDetail) {
        const proposals = sessionDetail.messages.filter((m) => m.message_type === 'PROPOSAL');
        plan = `Consensus Strategy: ${proposals.map((p) => p.content).join('; ')}. Approved by ${sessionDetail.session.moderator_agent_id}.`;
      }
      await synthesizeWarRoomPlan(activeSessionId, plan);
      antMessage.success('Consensus synthesized and locked!');
      setShowSynthInput(false);
      setCustomPlan('');
      await fetchSessionDetail(activeSessionId);
      await fetchSessions();
    } catch (err) {
      antMessage.error('Failed to synthesize plan');
    } finally {
      setSynthesizing(false);
    }
  };

  const getStatusTag = (status: string) => {
    switch (status) {
      case 'DEBATING':
        return <Tag color="processing">⚡ Deliberating</Tag>;
      case 'CONSENSUS_REACHED':
        return <Tag color="success">✓ Consensus Reached</Tag>;
      case 'EXECUTING':
        return <Tag color="blue">🚀 Executing</Tag>;
      default:
        return <Tag color="default">{status}</Tag>;
    }
  };

  const getMessageTypeTag = (type: string) => {
    switch (type) {
      case 'PROPOSAL':
        return <Tag color="blue">💡 Proposal</Tag>;
      case 'CRITIQUE':
        return <Tag color="orange">⚠️ Critique</Tag>;
      case 'CONSENSUS_VOTE':
        return <Tag color="green">👍 Agreement</Tag>;
      case 'SUMMARY':
        return <Tag color="purple">📋 Summary</Tag>;
      default:
        return <Tag>{type}</Tag>;
    }
  };

  return (
    <Modal
      open={open}
      onCancel={onClose}
      width={1000}
      footer={null}
      zIndex={1050}
      title={
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <TeamOutlined style={{ color: '#6366f1', fontSize: '20px' }} />
          <span>Multi-Agent War Room & Deliberation Council</span>
        </div>
      }
    >
      <div style={{ display: 'flex', gap: '20px', minHeight: '520px', maxHeight: '70vh' }}>
        {/* Left Sidebar: Session List + New Button */}
        <div
          style={{
            width: '280px',
            borderRight: '1px solid #30363d',
            paddingRight: '12px',
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          <div style={{ marginBottom: '12px' }}>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              block
              style={{ background: '#6366f1', borderColor: '#6366f1' }}
              onClick={() => setActiveSessionId(null)}
            >
              New Deliberation
            </Button>
          </div>

          <Text strong style={{ fontSize: '12px', color: '#8c8c8c', marginBottom: '8px' }}>
            ACTIVE CONFERENCES ({sessions.length})
          </Text>

          {loading ? (
            <div style={{ textAlign: 'center', padding: '24px' }}>
              <Spin />
            </div>
          ) : (
            <List
              dataSource={sessions}
              style={{ overflowY: 'auto', flex: 1 }}
              renderItem={(s) => (
                <List.Item
                  onClick={() => setActiveSessionId(s.id)}
                  style={{
                    padding: '10px',
                    borderRadius: '8px',
                    cursor: 'pointer',
                    background: activeSessionId === s.id ? '#f5f3ff' : 'transparent',
                    border: activeSessionId === s.id ? '1px solid #c7d2fe' : '1px solid transparent',
                    marginBottom: '6px',
                    display: 'block',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <Text strong style={{ fontSize: '13px', color: '#1f2937' }} ellipsis>
                      {s.title}
                    </Text>
                  </div>
                  <div style={{ marginTop: '4px', fontSize: '11px', color: '#6b7280' }} className="line-clamp-2">
                    {s.topic}
                  </div>
                  <div style={{ marginTop: '6px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    {getStatusTag(s.status)}
                    <Text type="secondary" style={{ fontSize: '10px' }}>
                      {s.participant_agent_ids.length} agents
                    </Text>
                  </div>
                </List.Item>
              )}
            />
          )}
        </div>

        {/* Right Content: Session View or New Session Form */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflowY: 'auto' }}>
          {!activeSessionId ? (
            /* New Session Creation Form */
            <div style={{ padding: '8px' }}>
              <Title level={4}>🏛️ Convene New War Room</Title>
              <Paragraph type="secondary">
                Assemble a roundtable of specialized agents to debate architecture, critique approaches, and synthesize an execution plan before launching tasks.
              </Paragraph>

              <div style={{ marginTop: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
                <div>
                  <Text strong>Session Title</Text>
                  <Input
                    placeholder="e.g. Migration to Distributed SQLite or Redis Caching"
                    value={newTitle}
                    onChange={(e) => setNewTitle(e.target.value)}
                    style={{ marginTop: '4px' }}
                  />
                </div>

                <div>
                  <Text strong>Deliberation Topic / Mission</Text>
                  <TextArea
                    rows={3}
                    placeholder="Describe the challenge, tradeoffs to analyze, and constraints..."
                    value={newTopic}
                    onChange={(e) => setNewTopic(e.target.value)}
                    style={{ marginTop: '4px' }}
                  />
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                  <div>
                    <Text strong>Council Moderator (Lead Agent)</Text>
                    <Select
                      style={{ width: '100%', marginTop: '4px' }}
                      value={newModerator}
                      onChange={setNewModerator}
                    >
                      {agents.map((a) => (
                        <Option key={a.id} value={a.id}>
                          {a.name || a.id}
                        </Option>
                      ))}
                    </Select>
                  </div>

                  <div>
                    <Text strong>Participant Agents</Text>
                    <Select
                      mode="multiple"
                      style={{ width: '100%', marginTop: '4px' }}
                      value={newParticipants}
                      onChange={setNewParticipants}
                      placeholder="Select 2+ agents"
                    >
                      {agents.map((a) => (
                        <Option key={a.id} value={a.id}>
                          {a.name || a.id}
                        </Option>
                      ))}
                    </Select>
                  </div>
                </div>

                <Button
                  type="primary"
                  size="large"
                  icon={<TeamOutlined />}
                  loading={submittingSession}
                  onClick={handleCreateSession}
                  style={{ marginTop: '16px', background: '#6366f1', borderColor: '#6366f1' }}
                >
                  Convene Council & Open Floor
                </Button>
              </div>
            </div>
          ) : detailLoading || !sessionDetail ? (
            <div style={{ textAlign: 'center', padding: '60px' }}>
              <Spin size="large" />
            </div>
          ) : (
            /* Active Session View */
            <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
              {/* Header */}
              <div style={{ borderBottom: '1px solid #f0f0f0', paddingBottom: '12px', marginBottom: '12px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <div>
                    <Title level={4} style={{ margin: 0 }}>
                      {sessionDetail.session.title}
                    </Title>
                    <Paragraph type="secondary" style={{ margin: '4px 0 0 0', fontSize: '13px' }}>
                      {sessionDetail.session.topic}
                    </Paragraph>
                  </div>
                  <div>{getStatusTag(sessionDetail.session.status)}</div>
                </div>

                {/* Participants badge row */}
                <div style={{ marginTop: '8px', display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                  <Text type="secondary" style={{ fontSize: '11px' }}>Participants:</Text>
                  <Tag color="purple">👑 Moderator: {sessionDetail.session.moderator_agent_id}</Tag>
                  {sessionDetail.session.participant_agent_ids.map((id) => (
                    <Tag key={id} color="geekblue">
                      🤖 {id}
                    </Tag>
                  ))}
                </div>
              </div>

              {/* Synthesized Plan Card if Consensus Reached */}
              {sessionDetail.session.synthesized_plan && (
                <Alert
                  type="success"
                  showIcon
                  icon={<CheckCircleOutlined />}
                  message={<Text strong>Consensus Execution Plan</Text>}
                  description={
                    <div style={{ whiteSpace: 'pre-wrap', marginTop: '4px', fontSize: '13px' }}>
                      {sessionDetail.session.synthesized_plan}
                    </div>
                  }
                  style={{ marginBottom: '12px' }}
                />
              )}

              {/* Dialogue Transcript */}
              <div
                style={{
                  flex: 1,
                  overflowY: 'auto',
                  border: '1px solid #f0f0f0',
                  borderRadius: '8px',
                  padding: '12px',
                  background: '#fafafa',
                  marginBottom: '12px',
                }}
              >
                {sessionDetail.messages.length === 0 ? (
                  <div style={{ textAlign: 'center', color: '#9ca3af', padding: '30px 0' }}>
                    <MessageOutlined style={{ fontSize: '24px', marginBottom: '8px' }} />
                    <div>Floor is open. Begin the roundtable debate with a proposal below!</div>
                  </div>
                ) : (
                  <List
                    dataSource={sessionDetail.messages}
                    renderItem={(msg) => (
                      <div
                        style={{
                          marginBottom: '10px',
                          background: '#fff',
                          padding: '10px 14px',
                          borderRadius: '8px',
                          boxShadow: '0 1px 2px rgba(0,0,0,0.05)',
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                          <Space>
                            <Avatar size="small" style={{ background: '#6366f1' }}>
                              {msg.agent_id.substring(0, 2).toUpperCase()}
                            </Avatar>
                            <Text strong style={{ fontSize: '12px' }}>
                              {msg.agent_id}
                            </Text>
                            <Tag style={{ fontSize: '10px' }}>Round {msg.round_number}</Tag>
                            {getMessageTypeTag(msg.message_type)}
                          </Space>
                          <Text type="secondary" style={{ fontSize: '10px' }}>
                            {new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                          </Text>
                        </div>
                        <div style={{ fontSize: '13px', color: '#374151', whiteSpace: 'pre-wrap', lineHeight: '1.5' }}>
                          {msg.content}
                        </div>
                      </div>
                    )}
                  />
                )}
              </div>

              {/* Action & Message Input Bar */}
              {sessionDetail.session.status === 'DEBATING' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <div style={{ display: 'flex', gap: '8px' }}>
                    <Select
                      style={{ width: '180px' }}
                      value={msgAgentId}
                      onChange={setMsgAgentId}
                      placeholder="Speaking Agent"
                    >
                      {sessionDetail.session.participant_agent_ids.map((id) => (
                        <Option key={id} value={id}>
                          🤖 {id}
                        </Option>
                      ))}
                    </Select>

                    <Select
                      style={{ width: '150px' }}
                      value={msgType}
                      onChange={(val) => setMsgType(val as WarRoomMessageType)}
                    >
                      <Option value="PROPOSAL">💡 Proposal</Option>
                      <Option value="CRITIQUE">⚠️ Critique</Option>
                      <Option value="CONSENSUS_VOTE">👍 Agreement</Option>
                      <Option value="SUMMARY">📋 Summary</Option>
                    </Select>

                    <Button
                      icon={<BulbOutlined />}
                      onClick={() => setShowSynthInput(!showSynthInput)}
                      style={{ borderColor: '#10b981', color: '#059669' }}
                    >
                      Synthesize Consensus
                    </Button>
                  </div>

                  {showSynthInput && (
                    <div style={{ background: '#ecfdf5', padding: '10px', borderRadius: '8px', border: '1px solid #a7f3d0' }}>
                      <Text strong style={{ color: '#065f46' }}>Consensus Plan Formulation</Text>
                      <TextArea
                        rows={2}
                        value={customPlan}
                        onChange={(e) => setCustomPlan(e.target.value)}
                        placeholder="Leave blank to auto-summarize from proposals, or enter customized agreement..."
                        style={{ marginTop: '6px' }}
                      />
                      <Button
                        type="primary"
                        size="small"
                        icon={<CheckCircleOutlined />}
                        loading={synthesizing}
                        onClick={handleSynthesize}
                        style={{ marginTop: '6px', background: '#059669', borderColor: '#059669' }}
                      >
                        Lock Consensus & Finalize Plan
                      </Button>
                    </div>
                  )}

                  <div style={{ display: 'flex', gap: '8px' }}>
                    <TextArea
                      rows={2}
                      placeholder={`Enter ${msgAgentId}'s statement or counter-argument...`}
                      value={msgContent}
                      onChange={(e) => setMsgContent(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' && !e.shiftKey) {
                          e.preventDefault();
                          handleSendMessage();
                        }
                      }}
                    />
                    <Button
                      type="primary"
                      icon={<SendOutlined />}
                      loading={sendingMsg}
                      onClick={handleSendMessage}
                      style={{ height: 'auto', background: '#6366f1', borderColor: '#6366f1' }}
                    >
                      Submit
                    </Button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </Modal>
  );
};

export default WarRoomModal;
