import { Input, Button, Tag, Card, Collapse, Tooltip, Spin, Empty } from 'antd';
import { SyncOutlined, CheckCircleOutlined, CloseCircleOutlined, ToolOutlined, AlertOutlined, BulbOutlined, CopyOutlined, ClockCircleOutlined, MessageOutlined, CheckOutlined } from '@ant-design/icons';


import type { useAgentChat } from './useAgentChat';

export function AgentChatContent({ model }: { model: ReturnType<typeof useAgentChat> }) {
  const {
    agent, messages, loading, pendingApproval, approvalResponse,
    setApprovalResponse, activeTab, copiedTaskId, messagesEndRef, allAgentTasks,
    getTaskPrompt, getTaskResult, copyToClipboard, handleOpenTaskInSession, handleApprovalDecision,
    currentSession,
  } = model;
  if (!agent) return null;
  return (<>
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
                {currentSession?.title || 'Direct Workspace'} &bull; {agent.name}
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
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px',
                      marginBottom: '4px',
                      fontSize: '11px',
                      color: '#8b949e',
                    }}
                  >
                    <span>{isUser ? 'Operator (You)' : agent.name}</span>
                    <span>&bull;</span>
                    <span>{new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                  </div>
                  <div
                    style={{
                      maxWidth: '85%',
                      padding: '10px 14px',
                      borderRadius: isUser ? '14px 14px 2px 14px' : '14px 14px 14px 2px',
                      background: isUser ? '#1f6feb' : '#161b22',
                      color: isUser ? '#ffffff' : '#f3f4f6',
                      border: isUser ? '1px solid #388bfd' : '1px solid #30363d',
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

          {/* In-Chat Interactive Approval Card */}
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
                      <Tooltip title="Open this execution in a chat session tab">
                        <Button
                          type="primary"
                          ghost
                          size="small"
                          icon={<MessageOutlined />}
                          onClick={() => handleOpenTaskInSession(t)}
                          style={{ fontSize: '11px', height: '24px' }}
                        >
                          Chat Tab
                        </Button>
                      </Tooltip>
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
                          border: '1px solid #21262d',
                          fontFamily: 'Consolas, monospace',
                          fontSize: '12px',
                          color: '#fca5a5',
                          maxHeight: '220px',
                          overflowY: 'auto',
                          whiteSpace: 'pre-wrap',
                        }}
                      >
                        {t.error}
                      </div>
                    </div>
                  ) : isRunning ? (
                    <div style={{ fontSize: '12px', color: '#93c5fd', display: 'flex', alignItems: 'center', gap: '6px', padding: '6px 0' }}>
                      <SyncOutlined spin /> Claude Code runtime process active...
                    </div>
                  ) : null}
                </Card>
              );
            })
          )}
        </div>
      )}
  </>);
}
