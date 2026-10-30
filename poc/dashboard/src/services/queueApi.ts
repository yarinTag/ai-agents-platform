import { api } from './httpClient';
import type { QueueStatus } from '../types/queue';

export const getQueueStatus = () => api.get<QueueStatus>('/api/v1/queue/status');
export const getDeadLetterQueue = () => api.get<any[]>('/api/v1/queue/dlq');
export const retryDeadLetter = (messageId: string) => api.post(`/api/v1/queue/retry/${messageId}`);

