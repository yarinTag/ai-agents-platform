import React, { useState, useEffect, useRef, useMemo } from 'react';
import {
  Drawer,
  Input,
  Button,
  Tag,
  Typography,
  Card,
  Space,
  Collapse,
  Tooltip,
  Popconfirm,
  message,
  Spin,
  Empty,
  Segmented,
} from 'antd';
import {
  SendOutlined,
  ClearOutlined,
  SyncOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ToolOutlined,
  CodeOutlined,
  QuestionCircleOutlined,
  AlertOutlined,
  BulbOutlined,
  ThunderboltOutlined,
  CopyOutlined,
  ClockCircleOutlined,
  MessageOutlined,
  CheckOutlined,
} from '@ant-design/icons';
import { Agent } from '../../types/agent';
import { Task } from '../../types/task';
import { ChatMessage } from '../../types/chat';
import {
  getChatHistory,
  sendChatMessage,
  clearChatHistory,
  respondToApproval,
  getPendingApprovals,
  getTasks,
} from '../../services/api';
import { ApprovalRequest } from '../../types/scheduler';

const { Text, Paragraph } = Typography;

interface AgentMiniChatDrawerProps {
  agent: Agent | null;
  tasks?: Task[];
  visible: boolean;
  onClose: () => void;
  onTaskDispatched?: () => void;
}

const QUICK_PROMPTS = [
  '📊 Give me a progress report',
  '🧪 Run the test suite',
  '🔍 Review code for edge cases',
  '🚀 What is your execution plan?',
];

export const AgentMiniChatDrawer: React.FC<AgentMiniChatDrawerProps> = ({
  agent,
  tasks = [],
  visible,
  onClose,
  onTaskDispatched,
}) => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [agentTasks, setAgentTasks] = useState<Task[]>([]);
  const [inputText, setInputText] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const [sending, setSending] = useState<boolean>(false);
  const [pendingApproval, setPendingApproval] = useState<ApprovalRequest | null>(null);
  const [approvalResponse, setApprovalResponse] = useState<string>('');
  const [activeTab, setActiveTab] = useState<'chat' | 'tasks'>('chat');
  const [copiedTaskId, setCopiedTaskId] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const loadHistory = async () => {
    if (!agent) return;
    try {
      setLoading(true);
      const [historyRes, appRes, tasksRes] = await Promise.all([
        getChatHistory(agent.id).catch(() => ({ data: { messages: [], tasks: [] } })),
        getPendingApprovals({ agent_id: agent.id }).catch(() => ({ data: [] })),
        getTasks({ agent_id: agent.id }).catch(() => ({ data: [] })),
      ]);

      setMessages(historyRes.data.messages || []);
      const pending = appRes.data || [];
      setPendingApproval(pending.length > 0 ? pending[0] : null);

      const fetchedTasks: Task[] = tasksRes.data || (historyRes.data as any).tasks || [];
      setAgentTasks(fetchedTasks);
    } catch (err) {
      console.error('Failed to load chat history:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (visible && agent) {
      loadHistory();
      const interval = setInterval(loadHistory, 3500); // Polling update
      return () => clearInterval(interval);
    }
  }, [visible, agent]);

  useEffect(() => {
    if (activeTab === 'chat') {
      scrollToBottom();
    }
  }, [messages, pendingApproval, activeTab]);

  const allAgentTasks = useMemo(() => {
    const map = new Map<string, Task>();
    // From tasks prop
    tasks.filter((t) => String(t.agent_id) === String(agent?.id)).forEach((t) => {
      const tid = t.run_id || t.id;
      if (tid) map.set(tid, t);
    });
    // From fetched agent tasks
    agentTasks.forEach((t) => {
      const tid = t.run_id || t.id;
      if (tid) map.set(tid, t);
    });
    return Array.from(map.values()).sort((a, b) => {
      const da = new Date(a.created_at || 0).getTime();
      const db = new Date(b.created_at || 0).getTime();
      return db - da;
    });
  }, [tasks, agentTasks, agent?.id]);

  const getTaskPrompt = (t: Task): string => {
    if (t.prompt) return t.prompt;
    if (typeof t.input_data === 'string') return t.input_data;
    if (t.input_data && typeof t.input_data === 'object') {
      return t.input_data.prompt || t.input_data.task || JSON.stringify(t.input_data);
    }
    return 'Autonomous Task';
  };

  const getTaskResult = (t: Task): string | null => {
    if (t.result) return t.result;
    if (typeof t.output_data === 'string') return t.output_data;
    if (t.output_data && typeof t.output_data === 'object') {
      return t.output_data.result || t.output_data.output || JSON.stringify(t.output_data, null, 2);
    }
    return null;
  };

  const copyToClipboard = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedTaskId(id);
    message.success('Copied output to clipboard');
    setTimeout(() => setCopiedTaskId(null), 2000);
  };

  const handleSend = async (textToSend?: string) => {
    const text = textToSend || inputText.trim();
    if (!text || !agent) return;

    try {
      setSending(true);
      setInputText('');
      const res = await sendChatMessage(agent.id, text);
      if (res.data.user_message) {
        setMessages((prev) => [...prev, res.data.user_message]);
      }
      message.success(`Task dispatched to ${agent.name}`);
      if (onTaskDispatched) onTaskDispatched();
      loadHistory();
    } catch (err: any) {
      message.error(err.response?.data?.detail || 'Failed to send message');
    } finally {
      setSending(false);
    }
  };

  const handleClear = async () => {
    if (!agent) return;
    try {
      await clearChatHistory(agent.id);
      setMessages([]);
      message.success('Chat history cleared');
    } catch (err) {
      message.error('Failed to clear chat');
    }
  };

  const handleApprovalDecision = async (decision: 'approve' | 'reject') => {
    if (!pendingApproval) return;
    try {
      await respondToApproval({
        interaction_id: pendingApproval.id,
        decision,
        response_text: approvalResponse || (decision === 'approve' ? 'Approved in Mini-Chat' : 'Rejected in Mini-Chat'),
        responder: 'OPERATOR_MINI_CHAT',
      });
      message.success(decision === 'approve' ? 'Action approved!' : 'Action rejected');
      setPendingApproval(null);
      setApprovalResponse('');
      loadHistory();
    } catch (err) {
      message.error('Failed to submit approval response');
    }
  };

  if (!agent) return null;

  // Active status determination
  const activeTask = allAgentTasks.find(
    (t) =>
      t.status === 'running' ||
      t.status === 'queued' ||
      t.status === 'waiting_input' ||
      t.status === 'pending_approval'
  );

  const isWaitingInput = pendingApproval !== null || activeTask?.status === 'waiting_input' || activeTask?.status === 'pending_approval';

  return (
    <Drawer
      title={
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span style={{ fontSize: '24px' }}>{agent.avatar || '🤖'}</span>
            <div>
              <div style={{ fontWeight: 600, color: '#f3f4f6', fontSize: '15px' }}>
                {agent.name}
              </div>
              <div style={{ fontSize: '11px', color: '#8b949e' }}>
                {agent.department || 'Engineering'} &bull; {agent.role_type || 'WORKER'}
              </div>
            </div>
          </div>
          <Space>
            {isWaitingInput ? (
              <Tag color="warning" icon={<QuestionCircleOutlined />}>
                ACTION REQUIRED
              </Tag>
            ) : activeTask ? (
              <Tag color="processing" icon={<SyncOutlined spin />}>
                RUNNING
              </Tag>
            ) : (
              <Tag color="success">READY / IDLE</Tag>
            )}
            <Popconfirm title="Clear conversation history?" onConfirm={handleClear} okText="Yes" cancelText="No">
              <Tooltip title="Clear History">
                <Button type="text" icon={<ClearOutlined style={{ color: '#8b949e' }} />} />
              </Tooltip>
            </Popconfirm>
          </Space>
        </div>
      }
      placement="right"
      width={600}
      onClose={onClose}
      open={visible}
      styles={{
        header: { background: '#0d1117', borderBottom: '1px solid #30363d' },
        body: {
          background: '#0a0d12',
          display: 'flex',
          flexDirection: 'column',
          padding: 0,
          overflow: 'hidden',
        },
      }}
    >
      {/* Drawer Subheader: Segmented View Navigation */}
      <div style={{ background: '#0d1117', borderBottom: '1px solid #21262d', padding: '8px 16px' }}>
        <Segmented
          value={activeTab}
          onChange={(val) => setActiveTab(val as 'chat' | 'tasks')}
          block
          options={[
            {
              label: (
                <span style={{ fontSize: '12px' }}>
                  <MessageOutlined style={{ marginRight: '6px' }} />
                  Conversation & Responses ({messages.length})
                </span>
              ),
              value: 'chat',
            },
            {
              label: (
                <span style={{ fontSize: '12px' }}>
                  <ThunderboltOutlined style={{ marginRight: '6px' }} />
                  Task Executions ({allAgentTasks.length})
                </span>
              ),
              value: 'tasks',
            },
          ]}
        />
      </div>

      {/* Active Task Notification Banner */}
      {activeTask && (
        <div
          style={{
            margin: '10px 16px 0 16px',
            padding: '10px 14px',
            background: 'rgba(59, 130, 246, 0.1)',
            border: '1px solid rgba(59, 130, 246, 0.4)',
            borderRadius: '8px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '12px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flex: 1, minWidth: 0 }}>
            <SyncOutlined spin style={{ color: '#38bdf8', fontSize: '16px' }} />
            <div style={{ minWidth: 0, flex: 1 }}>
              <div style={{ color: '#38bdf8', fontWeight: 600, fontSize: '12px' }}>
                Executing Task in Progress
              </div>
              <div
                style={{
                  color: '#e2e8f0',
                  fontSize: '11px',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
              >
                {getTaskPrompt(activeTask)}
              </div>
            </div>
          </div>
          <Tag color="processing">RUNNING</Tag>
        </div>
      )}

      {/* Main View Area */}
      {activeTab === 'chat' ? (
        /* Messages Scroll Area */
        <div
          style={{
            flex: 1,
            overflowY: 'auto',
            padding: '16px 20px',
            display: 'flex',
            flexDirection: 'column',
            gap: '12px',
          }}
        >
          {loading && messages.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '40px 0' }}>
              <Spin tip="Connecting to Agent session & retrieving task outputs..." />
            </div>
          ) : messages.length === 0 && !pendingApproval ? (
            <div style={{ textAlign: 'center', padding: '60px 20px', color: '#6e7681' }}>
              <div style={{ fontSize: '36px', marginBottom: '10px' }}>💬</div>
              <div style={{ fontWeight: 600, color: '#c9d1d9', marginBottom: '4px' }}>
                Direct Workspace with {agent.name}
              </div>
              <div style={{ fontSize: '12px' }}>
                Send a task or prompt below. Any executed task and response will appear right here.
              </div>
            </div>
          ) : (
            messages.map((msg) => {
              const isUser = msg.sender_type === 'USER';
              const isThought = msg.message_type === 'THOUGHT';
              const isTool = msg.message_type === 'TOOL_CALL' || msg.message_type === 'TOOL_RESULT';
              const isTaskExecution = Boolean(msg.metadata?.task_id || msg.task_id);

              if (isThought) {
                return (
                  <Collapse
                    key={msg.id}
                    size="small"
                    style={{
                      background: '#161b22',
                      border: '1px solid #30363d',
                      borderRadius: '8px',
                    }}
                    items={[
                      {
                        key: '1',
                        label: (
                          <span style={{ color: '#a78bfa', fontSize: '12px' }}>
                            <BulbOutlined /> Chain of Thought (Reasoning)
                          </span>
                        ),
                        children: (
                          <div
                            style={{
                              fontSize: '11px',
                              color: '#c9d1d9',
                              fontFamily: 'monospace',
                              whiteSpace: 'pre-wrap',
                            }}
                          >
                            {msg.content}
                          </div>
                        ),
                      },
                    ]}
                  />
                );
              }

              if (isTool) {
                return (
                  <div
                    key={msg.id}
                    style={{
                      background: '#161b22',
                      padding: '8px 12px',
                      borderRadius: '6px',
                      border: '1px solid #30363d',
                      fontSize: '12px',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#38bdf8', fontWeight: 600 }}>
                      <ToolOutlined /> Tool Invocation: {msg.metadata?.tool_name || 'System Command'}
                    </div>
                    <pre
                      style={{
                        background: '#0d1117',
                        padding: '6px 8px',
                        borderRadius: '4px',
                        fontSize: '11px',
                        color: '#a5d6ff',
                        marginTop: '6px',
                        marginBottom: 0,
                        overflowX: 'auto',
                      }}
                    >
                      {msg.content}
                    </pre>
                  </div>
                );
              }

              // Specialized Task Execution Result Card (for Assistant responses)
              if (isTaskExecution && !isUser) {
                const status = (msg.metadata?.status || 'completed').toLowerCase();
                const isCompleted = status === 'completed';
                const isFailed = status === 'failed';
                const prompt = msg.metadata?.prompt;
                const taskId = msg.metadata?.task_id || msg.task_id;

                return (
                  <div
                    key={msg.id}
                    style={{
                      width: '100%',
                      background: isCompleted ? 'rgba(16, 185, 129, 0.06)' : isFailed ? 'rgba(239, 68, 68, 0.06)' : '#161b22',
                      border: `1px solid ${isCompleted ? 'rgba(16, 185, 129, 0.4)' : isFailed ? 'rgba(239, 68, 68, 0.4)' : '#30363d'}`,
                      borderRadius: '10px',
                      padding: '12px 14px',
                      margin: '4px 0',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <Tag
                          color={isCompleted ? 'success' : isFailed ? 'error' : 'processing'}
                          icon={isCompleted ? <CheckCircleOutlined /> : isFailed ? <CloseCircleOutlined /> : <SyncOutlined spin />}
                        >
                          {status.toUpperCase()}
                        </Tag>
                        <span style={{ fontSize: '11px', color: '#8b949e', fontFamily: 'monospace' }}>
                          {taskId}
                        </span>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{ fontSize: '10px', color: '#8b949e' }}>
                          {new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </span>
                        <Tooltip title="Copy Task Response">
                          <Button
                            type="text"
                            size="small"
                            icon={copiedTaskId === msg.id ? <CheckOutlined style={{ color: '#10b981' }} /> : <CopyOutlined style={{ color: '#8b949e' }} />}
                            onClick={() => copyToClipboard(msg.content, msg.id)}
                          />
                        </Tooltip>
                      </div>
                    </div>

                    {prompt && (
                      <div
                        style={{
                          background: '#0d1117',
                          padding: '6px 10px',
                          borderRadius: '6px',
                          fontSize: '12px',
                          color: '#cbd5e1',
                          marginBottom: '8px',
                          borderLeft: '3px solid #3b82f6',
                        }}
                      >
                        <span style={{ color: '#93c5fd', fontWeight: 600 }}>Task Prompt: </span>
                        {prompt}
                      </div>
                    )}

                    <div style={{ color: '#f3f4f6', fontSize: '13px', lineHeight: '1.5', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                      <div style={{ color: isCompleted ? '#34d399' : '#f87171', fontWeight: 600, fontSize: '11px', marginBottom: '4px' }}>
                        {isCompleted ? '⚡ Execution Output / Agent Response:' : '❌ Execution Error:'}
                      </div>
                      <div
                        style={{
                          background: '#090d13',
                          padding: '10px 12px',
                          borderRadius: '6px',
                          border: '1px solid #21262d',
                          fontFamily: 'Consolas, monospace',
                          fontSize: '12px',
                          maxHeight: '260px',
                          overflowY: 'auto',
                          color: isCompleted ? '#e6edf3' : '#fca5a5',
                        }}
                      >
                        {msg.content}
                      </div>
                    </div>
                  </div>
                );
              }

              return (
                <div
                  key={msg.id}
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: isUser ? 'flex-end' : 'flex-start',
                  }}
                >
                  <div
                    style={{
                      fontSize: '10px',
                      color: '#8b949e',
                      marginBottom: '3px',
                      padding: '0 4px',
                    }}
                  >
                    {isUser ? 'You' : agent.name} &bull; {new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </div>
                  <div
                    style={{
                      maxWidth: '85%',
                      padding: '10px 14px',
                      borderRadius: isUser ? '16px 16px 2px 16px' : '16px 16px 16px 2px',
                      background: isUser ? '#1e3a8a' : '#161b22',
                      border: isUser ? '1px solid #2563eb' : '1px solid #30363d',
                      color: '#f3f4f6',
                      fontSize: '13px',
                      lineHeight: '1.5',
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-word',
                    }}
                  >
                    {msg.content}
                  </div>
                </div>
              );
            })
          )}

          {/* In-Chat Interactive Approval Card (When agent asks question or seeks permission) */}
          {pendingApproval && (
            <Card
              style={{
                background: 'rgba(245, 158, 11, 0.08)',
                border: '1px solid #f59e0b',
                borderRadius: '10px',
                marginTop: '8px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#f59e0b', fontWeight: 600, marginBottom: '6px' }}>
                <AlertOutlined />
                <span>
                  {pendingApproval.interaction_type === 'QUESTION' ? 'Agent Question / Clarification' : 'Action Approval Required'}
                </span>
              </div>
              <div style={{ fontWeight: 500, color: '#f3f4f6', fontSize: '13px', marginBottom: '4px' }}>
                {pendingApproval.title}
              </div>
              <div style={{ fontSize: '12px', color: '#d1d5db', marginBottom: '12px', whiteSpace: 'pre-wrap' }}>
                {pendingApproval.content}
              </div>
              <Input.TextArea
                rows={2}
                value={approvalResponse}
                onChange={(e) => setApprovalResponse(e.target.value)}
                placeholder="Type your answer or decision note..."
                style={{ background: '#0d1117', color: '#fff', borderColor: '#30363d', marginBottom: '10px' }}
              />
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
                <Button danger size="small" icon={<CloseCircleOutlined />} onClick={() => handleApprovalDecision('reject')}>
                  Reject
                </Button>
                <Button
                  type="primary"
                  size="small"
                  icon={<CheckCircleOutlined />}
                  style={{ background: '#238636', borderColor: '#238636' }}
                  onClick={() => handleApprovalDecision('approve')}
                >
                  Submit & Resume
                </Button>
              </div>
            </Card>
          )}

          <div ref={messagesEndRef} />
        </div>
      ) : (
        /* Tasks & Executions Tab Area */
        <div
          style={{
            flex: 1,
            overflowY: 'auto',
            padding: '16px 20px',
            display: 'flex',
            flexDirection: 'column',
            gap: '12px',
          }}
        >
          {allAgentTasks.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '60px 20px', color: '#6e7681' }}>
              <Empty description={`No tasks dispatched to ${agent.name} yet.`} />
            </div>
          ) : (
            allAgentTasks.map((t) => {
              const tid = t.run_id || t.id;
              const status = (t.status || 'queued').toLowerCase();
              const isCompleted = status === 'completed';
              const isFailed = status === 'failed';
              const isRunning = status === 'running' || status === 'queued';
              const prompt = getTaskPrompt(t);
              const result = getTaskResult(t);

              return (
                <Card
                  key={tid}
                  size="small"
                  style={{
                    background: isCompleted ? 'rgba(16, 185, 129, 0.05)' : isFailed ? 'rgba(239, 68, 68, 0.05)' : '#161b22',
                    border: `1px solid ${isCompleted ? 'rgba(16, 185, 129, 0.4)' : isFailed ? 'rgba(239, 68, 68, 0.4)' : '#30363d'}`,
                    borderRadius: '8px',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <Tag
                        color={isCompleted ? 'success' : isFailed ? 'error' : isRunning ? 'processing' : 'default'}
                        icon={isCompleted ? <CheckCircleOutlined /> : isFailed ? <CloseCircleOutlined /> : isRunning ? <SyncOutlined spin /> : undefined}
                      >
                        {status.toUpperCase()}
                      </Tag>
                      <span style={{ fontSize: '11px', color: '#8b949e', fontFamily: 'monospace' }}>
                        {tid}
                      </span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span style={{ fontSize: '11px', color: '#8b949e' }}>
                        <ClockCircleOutlined style={{ marginRight: '4px' }} />
                        {new Date(t.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </span>
                      {result && (
                        <Tooltip title="Copy Task Response">
                          <Button
                            type="text"
                            size="small"
                            icon={copiedTaskId === tid ? <CheckOutlined style={{ color: '#10b981' }} /> : <CopyOutlined style={{ color: '#8b949e' }} />}
                            onClick={() => copyToClipboard(result, tid)}
                          />
                        </Tooltip>
                      )}
                    </div>
                  </div>

                  <div
                    style={{
                      background: '#0d1117',
                      padding: '8px 10px',
                      borderRadius: '6px',
                      fontSize: '12px',
                      color: '#cbd5e1',
                      marginBottom: '8px',
                      borderLeft: '3px solid #3b82f6',
                    }}
                  >
                    <span style={{ color: '#93c5fd', fontWeight: 600 }}>Prompt: </span>
                    {prompt}
                  </div>

                  {result ? (
                    <div>
                      <div style={{ color: '#34d399', fontWeight: 600, fontSize: '11px', marginBottom: '4px' }}>
                        ⚡ Agent Execution Response:
                      </div>
                      <div
                        style={{
                          background: '#090d13',
                          padding: '8px 12px',
                          borderRadius: '6px',
                          border: '1px solid #21262d',
                          fontFamily: 'Consolas, monospace',
                          fontSize: '12px',
                          color: '#e6edf3',
                          maxHeight: '220px',
                          overflowY: 'auto',
                          whiteSpace: 'pre-wrap',
                        }}
                      >
                        {result}
                      </div>
                    </div>
                  ) : t.error ? (
                    <div>
                      <div style={{ color: '#f87171', fontWeight: 600, fontSize: '11px', marginBottom: '4px' }}>
                        ❌ Execution Error:
                      </div>
                      <div
                        style={{
                          background: '#090d13',
                          padding: '8px 12px',
                          borderRadius: '6px',
                          border: '1px solid #ef4444',
                          fontFamily: 'Consolas, monospace',
                          fontSize: '12px',
                          color: '#fca5a5',
                          whiteSpace: 'pre-wrap',
                        }}
                      >
                        {t.error}
                      </div>
                    </div>
                  ) : isRunning ? (
                    <div style={{ color: '#38bdf8', fontSize: '12px', display: 'flex', alignItems: 'center', gap: '6px', padding: '6px 0' }}>
                      <SyncOutlined spin /> Task is currently executing... Response will update live.
                    </div>
                  ) : null}
                </Card>
              );
            })
          )}
        </div>
      )}

      {/* Quick Prompts Bar */}
      <div
        style={{
          padding: '8px 16px',
          background: '#0d1117',
          borderTop: '1px solid #21262d',
          display: 'flex',
          gap: '8px',
          overflowX: 'auto',
          whiteSpace: 'nowrap',
        }}
      >
        {QUICK_PROMPTS.map((qp, idx) => (
          <Button
            key={idx}
            size="small"
            style={{
              fontSize: '11px',
              background: '#161b22',
              borderColor: '#30363d',
              color: '#8b949e',
              borderRadius: '12px',
            }}
            onClick={() => handleSend(qp)}
          >
            {qp}
          </Button>
        ))}
      </div>

      {/* Input Footer */}
      <div
        style={{
          padding: '12px 16px',
          background: '#0d1117',
          borderTop: '1px solid #30363d',
        }}
      >
        <div style={{ display: 'flex', gap: '8px', alignItems: 'flex-end' }}>
          <Input.TextArea
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder={`Message or dispatch task to ${agent.name}... (Press Enter to send)`}
            autoSize={{ minRows: 1, maxRows: 4 }}
            style={{
              background: '#161b22',
              color: '#f3f4f6',
              borderColor: '#30363d',
              borderRadius: '8px',
              resize: 'none',
            }}
          />
          <Button
            type="primary"
            icon={<SendOutlined />}
            loading={sending}
            disabled={!inputText.trim()}
            onClick={() => handleSend()}
            style={{
              background: '#2563eb',
              borderColor: '#2563eb',
              height: '38px',
              borderRadius: '8px',
            }}
          />
        </div>
      </div>
    </Drawer>
  );
};
export default AgentMiniChatDrawer;
