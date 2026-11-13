import { api } from './httpClient';

const base = '/api/v1/governance/external-identities';
const encode = encodeURIComponent;
export type IdentityConnector = { id: string; name: string; provider: string };
export type IdentityLink = { id: string; connector_id: string; provider: string; subject: string; created_at: number };
export type ManagedIdentityLink = IdentityLink & { member_name: string; can_revoke: boolean };
export type IdentityChallenge = { id: string; code: string; provider: string; expires_at: number };
type IdentityStatus = { id: string; subject: string | null; expires_at: number };

export const getIdentityConnectors = (signal: AbortSignal) => api.get<IdentityConnector[]>(base + '/connectors', { signal });
export const getPersonalIdentityLinks = (signal: AbortSignal) => api.get<IdentityLink[]>(base, { signal });
export const issueIdentityChallenge = (connector: string, signal: AbortSignal) =>
  api.post<IdentityChallenge>(base + '/connectors/' + encode(connector) + '/challenges', {}, { signal });
const challengePath = (id: string) => base + '/challenges/' + encode(id);
export const getIdentityChallenge = (id: string, signal: AbortSignal) => api.get<IdentityStatus>(challengePath(id), { signal });
export const confirmIdentityChallenge = (id: string, subject: string, signal: AbortSignal) =>
  api.post(challengePath(id) + '/confirm', { subject }, { signal });
export const unlinkPersonalIdentity = (id: string, signal: AbortSignal) =>
  api.delete(base + '/' + encode(id), { signal });
const managementPath = (department: string) => base + '/departments/' + encode(department) + '/links';
export const getManagedIdentityLinks = (department: string, after: string | undefined, signal: AbortSignal) =>
  api.get<{ links: ManagedIdentityLink[]; next_after: string | null }>(managementPath(department), { params: { after }, signal });
export const revokeManagedIdentity = (department: string, id: string, signal: AbortSignal) =>
  api.delete(managementPath(department) + '/' + encode(id), { signal });
