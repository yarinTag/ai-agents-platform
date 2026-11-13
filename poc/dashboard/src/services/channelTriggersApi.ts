import { api } from './httpClient';

export const matchers = ['event_type', 'command', 'mention', 'keyword', 'regex'] as const;
export const triggerFields = ['channel_id', 'event_type', 'message_id', 'sender_id', 'text'] as const;
export type TriggerRule = {
  binding_id: string;
  enabled: boolean;
  matcher: typeof matchers[number];
  pattern: string;
  parameters: Record<string, typeof triggerFields[number]>;
};
export type TriggerSettings = {
  revision: number;
  rule: TriggerRule | null;
  can_edit: boolean;
  bindings: { id: string; provider: string; connector_id: string; channel_id: string; channel_name?: string }[];
};

const path = (id: string) => `/api/v1/workflows/${encodeURIComponent(id)}/channel-trigger`;
export const getChannelTrigger = (id: string, signal: AbortSignal) =>
  api.get<TriggerSettings>(path(id), { signal });
export const saveChannelTrigger = (id: string, expectedRevision: number, rule: TriggerRule | null, signal: AbortSignal) =>
  api.put<Pick<TriggerSettings, 'revision' | 'rule'>>(path(id), { expected_revision: expectedRevision, rule }, { signal });
export const previewChannelTrigger = (id: string, rule: TriggerRule, eventType: string, sample: string, signal: AbortSignal) =>
  api.post<{ matched: boolean; parameters: Record<string, string | null> | null }>(`${path(id)}/preview`, {
    rule, event: { event_type: eventType, channel_id: 'preview', message_id: 'preview', text: sample },
  }, { signal });
