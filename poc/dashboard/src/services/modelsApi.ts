import { api } from './httpClient';
import type { DiscoveredModel, ModelTierOption } from '../types/model';

// Models Discovery
export const getAvailableModels = () => api.get<DiscoveredModel[]>('/api/v1/models/');

/** Provider-agnostic capability tiers; ids look like "tier:developer". */
export const getModelTiers = () => api.get<ModelTierOption[]>('/api/v1/models/tiers');
