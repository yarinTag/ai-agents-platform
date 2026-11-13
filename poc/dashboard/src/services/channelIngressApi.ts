import { api } from './httpClient';

export type IngressProvider = string;

export interface IngressEvent {
  id: string;
  provider: IngressProvider;
  event_type: string;
  status: string;
  received_at: number;
  processing_ms: number | null;
}

export interface IngressFailure {
  code: string;
  occurred_at: number;
}

export interface IngressChecks {
  https_configured: boolean;
  secret_configured: boolean;
  connector_connected: boolean;
}

export interface IngressDiagnostics extends IngressChecks {
  provider: IngressProvider;
  webhook_url: string | null;
  ssl_status: 'UNVERIFIED';
  last_verified_at: number | null;
  recent_events: IngressEvent[];
  recent_failures: IngressFailure[];
  dropped_failures: number;
}

export interface IngressTest {
  status: 'READY' | 'BLOCKED';
  checks: IngressChecks & { storage_ready: boolean };
  tls_status: 'VALID' | 'INVALID' | 'UNVERIFIED';
  live_request: boolean;
}

const path = (connectorId: string) => `/api/v1/governance/channel-ingress/${encodeURIComponent(connectorId)}`;
export const getIngressDiagnostics = (connectorId: string, signal: AbortSignal) =>
  api.get<IngressDiagnostics>(`${path(connectorId)}/diagnostics`, { signal });
export const testIngressConfiguration = (connectorId: string, signal: AbortSignal, verifyTls = false) =>
  api.post<IngressTest>(`${path(connectorId)}/test`, verifyTls ? { verify_tls: true } : undefined, { signal });
