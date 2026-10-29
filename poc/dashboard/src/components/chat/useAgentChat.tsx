import type { AgentMiniChatDrawerProps } from './agentChatTypes';
import { useState, useEffect, useRef, useMemo } from 'react';
import { message } from 'antd';

import { Task } from '../../types/task';
import { ChatMessage, AgentSession } from '../../types/chat';
import { getChatHistory, sendChatMessage, clearChatHistory, respondToApproval, getPendingApprovals, getTasks, getAgentSessions, createAgentSession, activateAgentSession } from '../../services/api';
import { ApprovalRequest } from '../../types/scheduler';


export function useAgentChat({ agent, tasks = [], visible, onClose, onTaskDispatched }: AgentMiniChatDrawerProps) {
  const [sessions, setSessions] = useState<AgentSession[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [creatingSession, setCreatingSession] = useState<boolean>(false);
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

  const [resourceErrors, setResourceErrors] = useState<Record<string, string | null>>({});
  const requestGeneration = useRef(0);
  const selectedSession = useRef(currentSessionId);
  const currentAgent = useRef(agent?.id);
  const drawerVisible = useRef(visible);
  selectedSession.current = currentSessionId;
  currentAgent.current = agent?.id;
  drawerVisible.current = visible;

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const loadHistory = async (targetSessionId?: string | null) => {
    if (!agent) return;
    const sessionToLoad = targetSessionId !== undefined ? targetSessionId : selectedSession.current;
    const requestId = ++requestGeneration.current;
    const agentId = agent.id;
    const current = () => requestId === requestGeneration.current && currentAgent.current === agentId && drawerVisible.current;
    try {
      setLoading(true);
      const responses = await Promise.allSettled([
        getChatHistory(agent.id, sessionToLoad),
        getPendingApprovals({ agent_id: agent.id }),
        getTasks({ agent_id: agent.id }),
        getAgentSessions(agent.id),
      ]);
      if (!current()) return;
      const labels = ['Conversation history', 'Approvals', 'Task history', 'Sessions'];
      setResourceErrors(Object.fromEntries(responses.map((result, index) => [
        labels[index], result.status === 'rejected' ? `${labels[index]} is unavailable. Retry this section.` : null,
      ])));
      const historyRes = responses[0].status === 'fulfilled' ? responses[0].value : null;
      const appRes = responses[1].status === 'fulfilled' ? responses[1].value : null;
      const tasksRes = responses[2].status === 'fulfilled' ? responses[2].value : null;
      const sessionsRes = responses[3].status === 'fulfilled' ? responses[3].value : null;

      const sessList: AgentSession[] = sessionsRes?.data?.sessions || [];
      setSessions(sessList);

      let resolvedSessionId = sessionToLoad;
      if (!resolvedSessionId && sessList.length > 0) {
        const activeSess = sessList.find((s) => s.status === 'ACTIVE') || sessList[0];
        resolvedSessionId = activeSess.id;
        setCurrentSessionId(resolvedSessionId);
      }

      const rawMessages = historyRes?.data?.messages || [];
      const seenMsgIds = new Set<string>();
      const seenContentKeys = new Set<string>();
      const dedupedMessages = rawMessages.filter((m) => {
        if (!m.id || seenMsgIds.has(m.id)) return false;
        seenMsgIds.add(m.id);
        const contentKey = `${m.sender_type}_${m.task_id || ''}_${m.content}`;
        if (m.sender_type === 'USER' && seenContentKeys.has(contentKey)) return false;
        seenContentKeys.add(contentKey);
        return true;
      });
      setMessages(dedupedMessages);

      const pending = appRes?.data || [];
      setPendingApproval(pending.length > 0 ? pending[0] : null);

      const fetchedTasks: Task[] = tasksRes?.data || historyRes?.data?.tasks || [];
      setAgentTasks(fetchedTasks);
    } catch (err) {
      console.error('Failed to load chat history:', err);
    } finally {
      if (current()) setLoading(false);
    }
  };

  useEffect(() => {
    if (visible && agent) {
      loadHistory();
      const interval = setInterval(() => {
        loadHistory();
      }, 3500);
      return () => { clearInterval(interval); requestGeneration.current += 1; };
    } else {
      setCurrentSessionId(null);
    }
  }, [visible, agent]);

  useEffect(() => {
    if (activeTab === 'chat') {
      scrollToBottom();
    }
  }, [messages, pendingApproval, activeTab]);

  const allAgentTasks = useMemo(() => {
    const map = new Map<string, Task>();
    tasks.filter((t) => String(t.agent_id) === String(agent?.id)).forEach((t) => {
      const tid = t.run_id || t.id;
      if (tid) map.set(tid, t);
    });
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

  const handleCreateNewSession = async (customTaskId?: string, customTitle?: string) => {
    if (!agent) return;
    try {
      setCreatingSession(true);
      const nextNum = sessions.length + 1;
      const title = customTitle || (customTaskId ? `Execution ${customTaskId.slice(-6)}` : `Session ${nextNum}`);
      const res = await createAgentSession(agent.id, {
        title,
        task_id: customTaskId || null,
      });
      const newSess = res.data.session;
      message.success(`Closed old session and started new: ${newSess.title}`);
      setCurrentSessionId(newSess.id);
      setMessages([]);
      await loadHistory(newSess.id);
    } catch (err: any) {
      message.error(err.response?.data?.detail || 'Failed to create new session');
    } finally {
      setCreatingSession(false);
    }
  };

  const handleSelectSession = async (sessionId: string) => {
    if (!agent) return;
    requestGeneration.current += 1;
    selectedSession.current = sessionId;
    setCurrentSessionId(sessionId);
    try {
      await activateAgentSession(agent!.id, sessionId);
      setSessions((prev) =>
        prev.map((s) => ({
          ...s,
          status: s.id === sessionId ? 'ACTIVE' : 'CLOSED',
        }))
      );
    } catch (err) {
      console.warn('Could not activate session on backend:', err);
    }
    loadHistory(sessionId);
  };

  const handleOpenTaskInSession = async (task: Task) => {
    const tid = task.run_id || task.id;
    const existing = sessions.find((s) => s.task_id === tid);
    if (existing) {
      await handleSelectSession(existing.id);
      setActiveTab('chat');
    } else {
      await handleCreateNewSession(tid, `Execution ${tid.slice(-6)}`);
      setActiveTab('chat');
    }
  };

  const handleSend = async (textToSend?: string) => {
    const text = textToSend || inputText.trim();
    if (!text || !agent) return;
    if (resourceErrors['Conversation history'] || resourceErrors.Sessions) {
      message.error('Conversation resources are unavailable. Retry before sending.');
      return;
    }

    try {
      setSending(true);
      setInputText('');
      const res = await sendChatMessage(agent.id, text, null, currentSessionId);
      if (res.data.user_message) {
        setMessages((prev) => {
          if (prev.some((m) => m.id === res.data.user_message.id)) return prev;
          return [...prev, res.data.user_message];
        });
      }
      if (res.data.status === 'resumed_task') {
        message.success(`Resumed execution for ${agent.name}`);
      } else {
        message.success(`Task dispatched to ${agent.name}`);
      }
      if (onTaskDispatched) onTaskDispatched();
      loadHistory(currentSessionId);
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
      loadHistory(currentSessionId);
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
      loadHistory(currentSessionId);
    } catch (err) {
      message.error('Failed to submit approval response');
    }
  };

  const activeTask = allAgentTasks.find(
    (t) =>
      t.status === 'running' ||
      t.status === 'queued' ||
      t.status === 'waiting_input' ||
      t.status === 'pending_approval'
  );

  const isWaitingInput = pendingApproval !== null || activeTask?.status === 'waiting_input' || activeTask?.status === 'pending_approval';

  const currentSession = sessions.find((s) => s.id === currentSessionId) || sessions.find((s) => s.status === 'ACTIVE') || sessions[0];
  const supervisorName = currentSession?.supervisor_agent_name || (agent?.parent_id ? `Supervisor (${agent.parent_id})` : null);
  const supervisorSessionTitle = currentSession?.supervisor_session_title || 'Active Session';

  return {
    resourceErrors,
    agent, tasks, visible, onClose, onTaskDispatched,
    sessions, setSessions, currentSessionId, setCurrentSessionId, creatingSession,
    setCreatingSession, messages, setMessages, agentTasks, setAgentTasks,
    inputText, setInputText, loading, setLoading, sending,
    setSending, pendingApproval, setPendingApproval, approvalResponse, setApprovalResponse,
    activeTab, setActiveTab, copiedTaskId, setCopiedTaskId, messagesEndRef,
    scrollToBottom, loadHistory, allAgentTasks, getTaskPrompt, getTaskResult,
    copyToClipboard, handleCreateNewSession, handleSelectSession, handleOpenTaskInSession, handleSend,
    handleClear, handleApprovalDecision, activeTask, isWaitingInput, currentSession,
    supervisorName, supervisorSessionTitle,
  };
}
