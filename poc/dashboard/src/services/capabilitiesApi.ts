import { api } from './httpClient';
import type { CapabilityReport } from '../types/capabilities';

/** Availability metadata is informational; it never grants authorization. */
export const getPlatformCapabilities = (signal?: AbortSignal) =>
  api.get<CapabilityReport>('/api/v1/capabilities', { signal });
