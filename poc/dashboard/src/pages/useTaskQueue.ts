import { useCallback, useEffect, useState } from 'react';
import { message } from 'antd';
import { getQueueStatus, getDeadLetterQueue, retryDeadLetter } from '../services/api';
import type { QueueStatus } from '../services/api';

export const useTaskQueue = (onTaskRetried: () => void) => {
  const [queueStatus, setQueueStatus] = useState<QueueStatus | null>(null);
  const [queueError, setQueueError] = useState(false);
  const [dlqVisible, setDlqVisible] = useState(false);
  const [dlqItems, setDlqItems] = useState<any[]>([]);
  const [loadingDlq, setLoadingDlq] = useState(false);
  const [dlqError, setDlqError] = useState(false);

  const fetchQueueMetrics = useCallback(async () => {
    try {
      const response = await getQueueStatus();
      setQueueStatus(response.data);
      setQueueError(false);
    } catch {
      setQueueError(true);
    }
  }, []);

  const fetchDlqItems = async () => {
    setLoadingDlq(true);
    try {
      const response = await getDeadLetterQueue();
      setDlqItems(response.data || []);
      setDlqError(false);
    } catch {
      setDlqError(true);
    } finally {
      setLoadingDlq(false);
    }
  };

  const handleRetryDlqItem = async (messageId: string) => {
    try {
      await retryDeadLetter(messageId);
      message.success(`Message ${messageId} re-queued successfully!`);
      fetchDlqItems();
      fetchQueueMetrics();
      onTaskRetried();
    } catch {
      message.error(`Failed to retry message ${messageId}`);
    }
  };

  useEffect(() => {
    fetchQueueMetrics();
    const interval = setInterval(fetchQueueMetrics, 5000);
    return () => clearInterval(interval);
  }, [fetchQueueMetrics]);

  return {
    queueStatus, queueError, dlqVisible, setDlqVisible, dlqItems, loadingDlq,
    dlqError, fetchQueueMetrics, fetchDlqItems, handleRetryDlqItem,
  };
};
