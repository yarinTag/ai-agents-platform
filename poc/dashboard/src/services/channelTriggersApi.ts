import { api } from './httpClient';

export const matchers = ['event_type', 'command', 'mention', 'keyword', 'regex'] as const;
export const triggerFields = ['channel_id', 'event_type', 'message_id', 'sender_id', 'text'] as const;
export type TriggerRule = {
  binding_id: string;
  enabled: boolean;
  matcher: typeof matchers[number];
  pattern: string;
  parameters: Record<string, typeof triggerFields[number]>;
  sender_ids?: string[];
  cooldown_seconds?: number;
  max_runs_per_hour?: number | null;
  relevance?: { instructions: string; minimum_confidence: number } | null;
};
export type TriggerPreview = { matched: boolean; parameters: Record<string, string | null> | null;
  requires_classification?: boolean };
export type TriggerSettings = {
  revision: number;
  rule: TriggerRule | null;
  can_edit: boolean;
  recent_classifications?: Array<{ event_id: string; workflow_revision: number; state: string; reason: string;
    confidence: number | null; model: string | null; provider: string | null; updated_at: number;
    execution_id: string | null }>;
  bindings: { id: string; provider: string; connector_id: string; channel_id: string; channel_name?: string }[];
};

const path = (id: string) => `/api/v1/workflows/${encodeURIComponent(id)}/channel-trigger`;
export const getChannelTrigger = (id: string, signal: AbortSignal) =>
  api.get<TriggerSettings>(path(id), { signal });
export const saveChannelTrigger = (id: string, expectedRevision: number, rule: TriggerRule | null, signal: AbortSignal) =>
  api.put<Pick<TriggerSettings, 'revision' | 'rule'>>(path(id), { expected_revision: expectedRevision, rule }, { signal });
export const previewChannelTrigger = (id: string, rule: TriggerRule, eventType: string, sample: string, sender: string, signal: AbortSignal) =>
  api.post<TriggerPreview>(`${path(id)}/preview`, {
    rule, event: { event_type: eventType, channel_id: 'preview', message_id: 'preview', text: sample, sender_id: sender.trim() || null },
  }, { signal });
