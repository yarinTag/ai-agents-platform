import { api } from './httpClient';
import type { CapabilityCatalog, CapabilityDescriptor, PolicyDocument, PolicyRecord } from '../types/governance';

const base = '/api/v1/governance';
export const getGovernanceCapabilities = (signal?: AbortSignal) =>
  api.get<{ capabilities: CapabilityDescriptor[] }>(`${base}/capabilities`, { signal });
export const getGovernanceCatalog = (departmentId: string, signal?: AbortSignal) =>
  api.get<CapabilityCatalog>(`${base}/departments/${encodeURIComponent(departmentId)}/catalog`, { signal });
const policyPath = (departmentId: string | null) => departmentId
  ? `${base}/departments/${encodeURIComponent(departmentId)}/policy` : `${base}/organization/policy`;
export const getCapabilityPolicy = (departmentId: string | null, signal?: AbortSignal) =>
  api.get<PolicyRecord>(policyPath(departmentId), { signal });
export const updateCapabilityPolicy = (departmentId: string | null, document: PolicyDocument,
  expectedRevision: number, signal?: AbortSignal) =>
  api.put<PolicyRecord>(policyPath(departmentId), { ...document, expected_revision: expectedRevision }, { signal });
export const getCapabilityPolicyHistory = (departmentId: string, signal?: AbortSignal) =>
  api.get<{ revisions: PolicyRecord[] }>(`${policyPath(departmentId)}/history`, { signal });
