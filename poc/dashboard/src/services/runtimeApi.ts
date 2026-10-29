import { api } from './httpClient';
import type { RuntimeSetupState, RuntimeSelectionDto } from '../types/runtime';

// Runtime providers (first-run setup)
export const getRuntimeSetupState = () => api.get<RuntimeSetupState>('/api/v1/runtimes/');
export const redetectRuntimeProviders = () => api.post<RuntimeSetupState>('/api/v1/runtimes/detect');
export const selectRuntimeProvider = (data: RuntimeSelectionDto) =>
  api.put<RuntimeSetupState>('/api/v1/runtimes/selection', data);
