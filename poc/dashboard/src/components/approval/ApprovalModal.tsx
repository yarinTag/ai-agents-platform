import React, { useState } from 'react';
import {
  Modal,
  Button,
  Input,
  Tag,
  Typography,
  Space,
  Card,
  message,
  Divider,
} from 'antd';
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  QuestionCircleOutlined,
  AlertOutlined,
  SafetyCertificateOutlined,
  RobotOutlined,
} from '@ant-design/icons';
import { ApprovalRequest, ApprovalResponseDto } from '../../types/scheduler';
import { Agent } from '../../types/agent';
import { respondToApproval } from '../../services/api';

const { Text, Paragraph } = Typography;

interface ApprovalModalProps {
  visible: boolean;
  request: ApprovalRequest | null;
  agent?: Agent | null;
  onClose: () => void;
  onSuccess: () => void;
}

export const ApprovalModal: React.FC<ApprovalModalProps> = ({
  visible,
  request,
  agent,
  onClose,
  onSuccess,
}) => {
  const [responseText, setResponseText] = useState<string>('');
  const [submitting, setSubmitting] = useState<boolean>(false);

  if (!request) return null;

  const isQuestion = request.interaction_type === 'QUESTION';

  const handleRespond = async (decision: 'approve' | 'reject') => {
    if (isQuestion && decision === 'approve' && !responseText.trim()) {
      message.error('Please provide an answer to the agent\'s question.');
      return;
    }

    try {
      setSubmitting(true);
      const dto: ApprovalResponseDto = {
        interaction_id: request.id,
        decision,
        response_text: responseText.trim() || (decision === 'approve' ? 'Approved by operator' : 'Rejected by operator'),
        responder: 'HUMAN_OPERATOR',
      };

      await respondToApproval(dto);
      message.success(
        decision === 'approve'
          ? 'Response delivered & agent task resumed!'
          : 'Action rejected. Task halted.'
      );
      setResponseText('');
      onSuccess();
      onClose();
    } catch (err: any) {
      console.error('Failed to submit approval resolution:', err);
      message.error(err.response?.data?.detail || 'Failed to submit response');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      title={
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {isQuestion ? (
            <QuestionCircleOutlined style={{ color: '#3b82f6', fontSize: '20px' }} />
          ) : (
            <AlertOutlined style={{ color: '#f59e0b', fontSize: '20px' }} />
          )}
          <span>
            {isQuestion ? 'Agent Clarification Question' : 'Manager / Operator Approval Required'}
          </span>
        </div>
      }
      open={visible}
      onCancel={onClose}
      footer={null}
      width={600}
      styles={{
        header: { borderBottom: '1px solid #30363d' },
        body: { padding: '20px' },
      }}
    >
      {/* Agent details */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          background: '#161b22',
          padding: '12px 16px',
          borderRadius: '8px',
          border: '1px solid #30363d',
          marginBottom: '16px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span style={{ fontSize: '24px' }}>{agent?.avatar || '🤖'}</span>
          <div>
            <div style={{ fontWeight: 600, color: '#f3f4f6' }}>
              {agent?.name || request.requester_agent_id}
            </div>
            <div style={{ fontSize: '11px', color: '#8b949e' }}>
              Task #{request.task_id} &bull; {agent?.department || 'Engineering'}
            </div>
          </div>
        </div>
        <Tag color={isQuestion ? 'blue' : 'gold'}>
          {request.interaction_type.replace('_', ' ')}
        </Tag>
      </div>

      {/* Question or action content */}
      <Card
        size="small"
        style={{
          background: '#0d1117',
          borderColor: '#30363d',
          marginBottom: '16px',
        }}
      >
        <div style={{ fontWeight: 600, color: '#e6edf3', marginBottom: '8px', fontSize: '14px' }}>
          {request.title}
        </div>
        <Paragraph
          style={{
            color: '#c9d1d9',
            fontSize: '13px',
            marginBottom: '0',
            whiteSpace: 'pre-wrap',
            background: 'rgba(255, 255, 255, 0.03)',
            padding: '10px',
            borderRadius: '6px',
            border: '1px solid rgba(255, 255, 255, 0.05)',
          }}
        >
          {request.content}
        </Paragraph>
      </Card>

      {/* Response input */}
      <div style={{ marginBottom: '20px' }}>
        <Text style={{ display: 'block', marginBottom: '8px', fontWeight: 600, color: '#e6edf3' }}>
          {isQuestion ? 'Your Answer / Clarification Instructions:' : 'Decision Notes (Optional for approval, required for rejection):'}
        </Text>
        <Input.TextArea
          rows={3}
          value={responseText}
          onChange={(e) => setResponseText(e.target.value)}
          placeholder={
            isQuestion
              ? 'e.g. Yes, use Fetch API instead of Axios, and ensure typescript types are updated.'
              : 'e.g. Approved with condition that backup is taken first.'
          }
          style={{ background: '#0d1117', borderColor: '#30363d', color: '#fff' }}
        />
      </div>

      {/* Action buttons */}
      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
        <Button onClick={onClose} disabled={submitting}>
          Cancel
        </Button>
        <Button
          danger
          icon={<CloseCircleOutlined />}
          loading={submitting}
          onClick={() => handleRespond('reject')}
        >
          Reject Action
        </Button>
        <Button
          type="primary"
          icon={<CheckCircleOutlined />}
          loading={submitting}
          onClick={() => handleRespond('approve')}
          style={{ background: '#238636', borderColor: '#238636' }}
        >
          {isQuestion ? 'Submit Answer & Resume' : 'Approve & Resume'}
        </Button>
      </div>
    </Modal>
  );
};
