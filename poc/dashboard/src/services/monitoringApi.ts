import { api } from './httpClient';
import type { ActivityEvent } from '../types/flow';

// System Stats & Real-Time Monitoring
export const getSystemStats = () => api.get('/api/v1/events/system/stats');
export const getSystemHealth = () => api.get('/api/v1/events/system/health');
export const getRecentActivity = (limit = 25, executionScope: 'all' | 'office' | 'workflow' = 'all') => api.get<{ activity: ActivityEvent[]; timestamp: string }>(`/api/v1/events/system/recent-activity?limit=${limit}&execution_scope=${executionScope}`);
