export type CapabilityState =
  | 'DISABLED'
  | 'STARTING'
  | 'READY'
  | 'DEGRADED'
  | 'UNAVAILABLE'
  | 'STOPPING';

export interface CapabilityStatus {
  state: CapabilityState;
  reason: string | null;
}

export interface CapabilityReport {
  capabilities: Record<string, CapabilityStatus>;
}
