import type { WarRoomModalProps } from './warRoomTypes';
import { useState, useEffect } from 'react';
import { Tag, message as antMessage } from 'antd';

import { getWarRoomSessions, createWarRoomSession, getWarRoomSession, sendWarRoomMessage, synthesizeWarRoomPlan } from '../../services/api';
import { WarRoomSession, WarRoomDetail, WarRoomMessageType } from '../../types/collab';


export function useWarRoom({ open, onClose, agents, projectId }: WarRoomModalProps) {
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

  return {
    open, onClose, agents, projectId, sessions,
    setSessions, loading, setLoading, activeSessionId, setActiveSessionId,
    sessionDetail, setSessionDetail, detailLoading, setDetailLoading, newTitle,
    setNewTitle, newTopic, setNewTopic, newModerator, setNewModerator,
    newParticipants, setNewParticipants, submittingSession, setSubmittingSession, msgAgentId,
    setMsgAgentId, msgType, setMsgType, msgContent, setMsgContent,
    sendingMsg, setSendingMsg, synthesizing, setSynthesizing, customPlan,
    setCustomPlan, showSynthInput, setShowSynthInput, fetchSessions, fetchSessionDetail,
    handleCreateSession, handleSendMessage, handleSynthesize, getStatusTag, getMessageTypeTag,
  };
}
