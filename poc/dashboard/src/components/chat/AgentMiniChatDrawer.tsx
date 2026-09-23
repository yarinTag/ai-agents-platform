import React, { useState, useEffect, useRef } from 'react';
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
  const [inputText, setInputText] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const [sending, setSending] = useState<boolean>(false);
  const [pendingApproval, setPendingApproval] = useState<ApprovalRequest | null>(null);
  const [approvalResponse, setApprovalResponse] = useState<string>('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const loadHistory = async () => {
    if (!agent) return;
    try {
      setLoading(true);
      const [historyRes, appRes] = await Promise.all([
        getChatHistory(agent.id).catch(() => ({ data: { messages: [] } })),
        getPendingApprovals({ agent_id: agent.id }).catch(() => ({ data: [] })),
      ]);

      setMessages(historyRes.data.messages || []);
      const pending = appRes.data || [];
      setPendingApproval(pending.length > 0 ? pending[0] : null);
    } catch (err) {
      console.error('Failed to load chat history:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (visible && agent) {
      loadHistory();
      const interval = setInterval(loadHistory, 4000); // Polling update
      return () => clearInterval(interval);
    }
  }, [visible, agent]);

  useEffect(() => {
    scrollToBottom();
  }, [messages, pendingApproval]);

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
      message.success('Message sent to agent');
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
  const activeTask = tasks.find(
    (t) => String(t.agent_id) === String(agent.id) &&
      (t.status === 'running' || t.status === 'queued' || t.status === 'waiting_input' || t.status === 'pending_approval')
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
      width={560}
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
      {/* Messages Scroll Area */}
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
            <Spin tip="Connecting to Agent session..." />
          </div>
        ) : messages.length === 0 && !pendingApproval ? (
          <div style={{ textAlign: 'center', padding: '60px 20px', color: '#6e7681' }}>
            <div style={{ fontSize: '36px', marginBottom: '10px' }}>💬</div>
            <div style={{ fontWeight: 600, color: '#c9d1d9', marginBottom: '4px' }}>
              Direct Chat with {agent.name}
            </div>
            <div style={{ fontSize: '12px' }}>
              Send an instruction, question, or task prompt to start collaborating.
            </div>
          </div>
        ) : (
          messages.map((msg) => {
            const isUser = msg.sender_type === 'USER';
            const isThought = msg.message_type === 'THOUGHT';
            const isTool = msg.message_type === 'TOOL_CALL' || msg.message_type === 'TOOL_RESULT';

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
            placeholder={`Message ${agent.name}... (Press Enter to send)`}
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
