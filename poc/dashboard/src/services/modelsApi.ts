import { api } from './httpClient';
import type { DiscoveredModel } from '../types/model';

// Models Discovery
export const getAvailableModels = () => api.get<DiscoveredModel[]>('/api/v1/models/');
