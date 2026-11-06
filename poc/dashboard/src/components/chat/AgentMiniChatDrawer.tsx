import { usePermissions } from '../../hooks/usePermissions';
import { ResourceWarning } from '../common/ResourceWarning';
import type { AgentMiniChatDrawerProps } from './agentChatTypes';
import React from 'react';
import { Drawer, Input, Button, Tag, Space, Tooltip, Popconfirm, Segmented } from 'antd';
import { SendOutlined, ClearOutlined, SyncOutlined, QuestionCircleOutlined, ThunderboltOutlined, MessageOutlined, PlusOutlined, CrownOutlined } from '@ant-design/icons';



const QUICK_PROMPTS = [
  '📊 Give me a progress report',
  '🧪 Run the test suite',
  '🔍 Review code for edge cases',
  '🚀 What is your execution plan?',
];

import { useAgentChat } from './useAgentChat';
import { AgentChatContent } from './AgentChatContent';

export const AgentMiniChatDrawer: React.FC<AgentMiniChatDrawerProps> = (props) => {
  const { canOperate } = usePermissions();
  const model = useAgentChat(props);
  const {
    agent, visible, onClose, sessions, currentSessionId,
    creatingSession, messages, inputText, setInputText, loading,
    sending, activeTab, setActiveTab, allAgentTasks, getTaskPrompt,
    handleCreateNewSession, handleSelectSession, handleSend, handleClear, activeTask,
    isWaitingInput, supervisorName, supervisorSessionTitle,
  } = model;
  if (!agent) return null;
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
            <Popconfirm disabled={!canOperate} title="Clear conversation history?" onConfirm={handleClear} okText="Yes" cancelText="No">
              <Tooltip title="Clear History">
                <Button type="text" disabled={!canOperate} icon={<ClearOutlined style={{ color: '#8b949e' }} />} />
              </Tooltip>
            </Popconfirm>
          </Space>
        </div>
      }
      placement="right"
      width={640}
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
      <ResourceWarning errors={Object.values(model.resourceErrors)} onRetry={() => model.loadHistory()} />
      {/* Drawer Subheader: Segmented View Navigation & Supervisor Info */}
      <div style={{ background: '#0d1117', borderBottom: '1px solid #21262d', padding: '8px 16px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
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

        {/* Supervisor Session Badge */}
        {supervisorName && (
          <div
            style={{
              padding: '4px 10px',
              background: 'rgba(168, 85, 247, 0.08)',
              border: '1px solid rgba(168, 85, 247, 0.25)',
              borderRadius: '6px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              fontSize: '11px',
              color: '#d8b4fe',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <CrownOutlined style={{ color: '#c084fc' }} />
              <span>
                <strong>Supervisor:</strong> {supervisorName}
              </span>
            </div>
            <Tag color="purple" style={{ margin: 0, fontSize: '10px', lineHeight: '18px' }}>
              Session: {supervisorSessionTitle}
            </Tag>
          </div>
        )}
      </div>

      {/* Session Tabs Bar with + Button */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          padding: '6px 16px',
          background: '#11161d',
          borderBottom: '1px solid #21262d',
          overflowX: 'auto',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flex: 1, overflowX: 'auto', scrollbarWidth: 'none' }}>
          {sessions.map((sess) => {
            const isSelected = currentSessionId ? sess.id === currentSessionId : sess.status === 'ACTIVE';
            const isActive = sess.status === 'ACTIVE';
            return (
              <Button
                key={sess.id}
                size="small"
                type={isSelected ? 'primary' : 'default'}
                disabled={!canOperate} onClick={() => handleSelectSession(sess.id)}
                style={{
                  fontSize: '11px',
                  borderRadius: '5px',
                  background: isSelected ? '#1f6feb' : '#161b22',
                  borderColor: isSelected ? '#388bfd' : '#30363d',
                  color: isSelected ? '#ffffff' : '#c9d1d9',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '5px',
                  whiteSpace: 'nowrap',
                }}
              >
                {isActive ? (
                  <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#3fb950', display: 'inline-block' }} />
                ) : (
                  <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#8b949e', display: 'inline-block' }} />
                )}
                {sess.title || 'Session'}
              </Button>
            );
          })}
        </div>
        <Tooltip title="Start New Session (Closes previous active session)">
          <Button
            size="small"
            icon={<PlusOutlined />}
            loading={creatingSession}
            disabled={!canOperate} onClick={() => handleCreateNewSession()}
            style={{
              borderRadius: '5px',
              background: '#21262d',
              borderColor: '#30363d',
              color: '#58a6ff',
              fontWeight: 600,
              fontSize: '11px',
            }}
          >
            New
          </Button>
        </Tooltip>
      </div>

      {/* Active Task Notification Banner */}
      {activeTask && (
        <div
          style={{
            margin: '8px 16px 0 16px',
            padding: '8px 12px',
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
            <SyncOutlined spin style={{ color: '#38bdf8', fontSize: '15px' }} />
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

      <AgentChatContent model={model} />

      {/* Suggested Quick Prompts */}
      <div
        style={{
          display: 'flex',
          gap: '8px',
          overflowX: 'auto',
          padding: '8px 16px',
          background: '#0d1117',
          borderTop: '1px solid #21262d',
          scrollbarWidth: 'none',
        }}
      >
        {QUICK_PROMPTS.map((qp, idx) => (
          <Button
            key={idx}
            size="small"
            onClick={() => handleSend(qp.replace(/^[^\s]+\s/, ''))}
            disabled={!canOperate || sending}
            style={{
              fontSize: '11px',
              borderRadius: '6px',
              background: '#161b22',
              borderColor: '#30363d',
              color: '#8b949e',
              whiteSpace: 'nowrap',
            }}
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
            disabled={!canOperate}
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder={
              isWaitingInput
                ? `Reply to unblock ${agent.name}... (Press Enter to resume execution)`
                : `Message or dispatch task to ${agent.name}... (Press Enter to send)`
            }
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
            disabled={!canOperate || !inputText.trim()}
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
