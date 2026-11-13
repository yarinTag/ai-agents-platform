import { api } from './httpClient';

export const channelUses = ['send_notifications', 'trigger_workflows', 'approve_decisions'] as const;
export type ChannelUses = Record<typeof channelUses[number], boolean>;
export type ChannelIdentity = { connector_id: string; provider: string; channel_id: string };
export type ChannelCatalog = {
  providers: Record<string, { label: string; configurable_uses: typeof channelUses[number][]; runtime_supported_uses: typeof channelUses[number][] }>;
  connectors: { id: string; name: string; provider: string; status: string; channel_ids: string[]; channel_labels: Record<string, string> }[];
};
export type ChannelBinding = ChannelIdentity & {
  id: string;
  department_id: string | null;
  channel_name?: string | null;
  revision: number;
  uses: ChannelUses;
};

const base = '/api/v1/governance/channel-bindings';
const scope = (department: string | null) => ({ department_id: department ?? undefined });
export const getChannelCatalog = (department: string | null, signal: AbortSignal) =>
  api.get<ChannelCatalog>(`${base}/catalog`, { params: scope(department), signal });
export const listChannelBindings = (department: string | null, after: string | undefined, signal: AbortSignal) =>
  api.get<{ bindings: ChannelBinding[]; next_after: string | null }>(base, {
    params: { ...scope(department), after }, signal,
  });
export const createChannelBinding = (department: string | null, identity: ChannelIdentity, uses: ChannelUses, signal: AbortSignal) =>
  api.post<ChannelBinding>(base, { ...identity, department_id: department, uses }, { signal });
export const replaceChannelUses = (binding: ChannelBinding, uses: ChannelUses, signal: AbortSignal) =>
  api.put<ChannelBinding>(`${base}/${encodeURIComponent(binding.id)}/uses`, {
    expected_revision: binding.revision, uses,
  }, { params: scope(binding.department_id), signal });
export const removeChannelBinding = (binding: ChannelBinding, signal: AbortSignal) =>
  api.delete(`${base}/${encodeURIComponent(binding.id)}`, {
    params: { ...scope(binding.department_id), expected_revision: binding.revision }, signal,
  });
