import { PrResultEvidence } from './PrEvidence';
import React, { useState } from 'react';
import { Button, Space, Tag, Typography } from 'antd';
import { asCostSummary, formatCost } from '../../services/workflowCosts';

const { Text } = Typography;
type RuntimeEvent = Record<string, unknown>;

const preStyle: React.CSSProperties = { whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', maxHeight: 320, overflow: 'auto', fontSize: 12, margin: '4px 0 0' };
const asRecord = (value: unknown): RuntimeEvent => (value && typeof value === 'object' ? value as RuntimeEvent : {});
const clip = (value: string, limit = 160) => (value.length > limit ? `${value.slice(0, limit)}…` : value);
const text = (value: unknown) => (typeof value === 'string' ? value : value == null ? '' : JSON.stringify(value));

/** Runtime event kinds emitted by the CLI stream, the Direct API worker and the executor. */
export enum EventKind {
  Stderr = 'stderr',
  Raw = 'raw',
  Error = 'error',
  Result = 'result',
  ToolUse = 'tool_use',
  ToolResult = 'tool_result',
  Assistant = 'assistant',
  ReasoningSummary = 'reasoning_summary',
  Usage = 'usage',
  User = 'user',
  System = 'system',
  ExecutionBackend = 'execution_backend',
  CompletionValidation = 'completion_validation',
  ConversationTransport = 'conversation_transport',
  EndOfOutput = 'end_of_output',
  Unknown = 'event',
}

const KNOWN_KINDS = new Set<string>(Object.values(EventKind));
const toKind = (value: unknown): EventKind =>
  (typeof value === 'string' && KNOWN_KINDS.has(value) ? value as EventKind : EventKind.Unknown);

const COLORS: Partial<Record<EventKind, string>> = {
  [EventKind.Error]: 'error', [EventKind.Stderr]: 'warning', [EventKind.Result]: 'success',
  [EventKind.ToolUse]: 'processing', [EventKind.ToolResult]: 'cyan', [EventKind.Assistant]: 'purple',
  [EventKind.ReasoningSummary]: 'geekblue',
  [EventKind.Usage]: 'gold',
  [EventKind.CompletionValidation]: 'warning',
};

interface EventDescription { kind: EventKind; label: string; summary: string; detail?: string }

/** Long text is clipped for the row; the full text is offered only when clipping lost something. */
const withDetail = (kind: EventKind, label: string, full: string, limit = 160): EventDescription => ({
  kind, label, summary: clip(full.split('\n')[0] || '', limit),
  detail: full.includes('\n') || full.length > limit ? full : undefined,
});

const messageText = (event: RuntimeEvent) => {
  const parts = asRecord(event.message).content;
  if (!Array.isArray(parts)) return '';
  return parts.map(part => {
    const item = asRecord(part);
    switch (item.type) {
      case 'text': return text(item.text);
      case 'tool_use': return `→ ${text(item.name)}`;
      case 'tool_result': return `← ${clip(text(item.content), 80)}`;
      default: return '';
    }
  }).filter(Boolean).join(' ');
};

/** One-line summary plus optional full text for each runtime event shape the runners emit. */
export const describeEvent = (event: RuntimeEvent): EventDescription => {
  const kind = toKind(event.type);
  // Unrecognized types keep their own label so new runtime events stay identifiable.
  const label = kind === EventKind.Unknown ? String(event.type || EventKind.Unknown) : kind;
  switch (kind) {
    case EventKind.Usage:
      return withDetail(kind, 'Usage & cost',
        `Call ${text(event.turn)}: ${text(event.input_tokens)} input / ${text(event.output_tokens)} output tokens · ${event.cost_usd == null ? 'Price unavailable' : '$' + Number(event.cost_usd).toFixed(6)} (${text(event.source)})\n` +
        `Run: ${formatCost(asCostSummary(event.cost_summary))}\nSession total: ${formatCost(asCostSummary(event.session_cost_summary))}`);
    case EventKind.ReasoningSummary:
      return withDetail(kind, 'Reasoning summary', event.status === 'available'
        ? text(event.content) : 'The provider did not return a visible reasoning summary for this turn.');
    case EventKind.Stderr:
    case EventKind.Raw:
      return withDetail(kind, label, text(event.content));
    case EventKind.Error:
      return withDetail(kind, label, text(asRecord(event.error).message) || 'Unknown error');
    case EventKind.Result: {
      const reported = event.total_cost_usd;
      const summary = asCostSummary(event.cost_summary);
      const cost = summary ? ` · ${formatCost(summary)}` : typeof reported === 'number' ? ` · $${reported.toFixed(6)}` : '';
      const shown = event.is_error ? EventKind.Error : kind;  // Failed results read as errors.
      const described = withDetail(shown, shown, text(event.result));
      return { ...described, summary: described.summary + cost };
    }
    case EventKind.ToolUse: {
      const input = text(event.input);
      return { kind, label, summary: `${text(event.name)} ${clip(input, 120)}`, detail: input.length > 120 ? input : undefined };
    }
    case EventKind.ToolResult:
      return withDetail(kind, label, text(event.content));
    case EventKind.Assistant:
    case EventKind.User:
      return withDetail(kind, label, messageText(event) || kind);
    case EventKind.ConversationTransport:
      return withDetail(kind, 'Conversation transport',
        `${text(event.mode)} · ${text(event.messages_sent)} messages · ${text(event.request_bytes)} bytes${event.reason ? ' · ' + text(event.reason) : ''}`);
    case EventKind.CompletionValidation:
      return withDetail(kind, 'Completion validation',
        `${text(event.error_code)} · attempt ${text(event.attempt)}: ${text(event.message)}\n${text(event.candidate_preview)}`);
    case EventKind.ExecutionBackend:
      return { kind, label: 'Execution engine', summary: `${text(event.backend)} · ${text(event.transport)}` };
    case EventKind.System:
      return { kind, label, summary: event.session_id ? `session ${text(event.session_id)}` : text(event.subtype) || label };
    case EventKind.EndOfOutput:
      return { kind, label, summary: 'Process output ended' };
    case EventKind.Unknown:
      return { kind, label, summary: clip(JSON.stringify(event)) };
    default: {
      const unhandled: never = kind;
      return { kind: EventKind.Unknown, label: String(unhandled), summary: clip(JSON.stringify(event)) };
    }
  }
};

const EventRow: React.FC<{ event: RuntimeEvent }> = ({ event }) => {
  const [open, setOpen] = useState<'none' | 'detail' | 'raw'>('none');
  const { kind, label, summary, detail } = describeEvent(event);
  const time = typeof event._timestamp === 'number' ? new Date(event._timestamp * 1000).toLocaleTimeString() : '';
  return <div style={{ padding: '4px 0', borderBottom: '1px solid rgba(128,128,128,0.15)' }}>
    <Space size={6} align="start" style={{ width: '100%' }}>
      <Text type="secondary" style={{ fontFamily: 'monospace', fontSize: 11, minWidth: 72, display: 'inline-block' }}>{time}</Text>
      <Tag color={COLORS[kind] || 'default'} style={{ marginInlineEnd: 0 }}>{label}</Tag>
      <Text style={{ fontSize: 12, overflowWrap: 'anywhere' }}>{summary}</Text>
      {detail && <Button size="small" type="link" onClick={() => setOpen(open === 'detail' ? 'none' : 'detail')}>{open === 'detail' ? 'Less' : 'More'}</Button>}
      <Button size="small" type="link" onClick={() => setOpen(open === 'raw' ? 'none' : 'raw')}>{open === 'raw' ? 'Hide JSON' : 'JSON'}</Button>
    </Space>
    {kind === EventKind.ToolResult && <PrResultEvidence value={event.content} />}
    {open === 'detail' && <pre style={preStyle}>{detail}</pre>}
    {open === 'raw' && <pre style={preStyle}>{JSON.stringify(event, null, 2)}</pre>}
  </div>;
};

export const StepEventTimeline: React.FC<{ events: RuntimeEvent[] }> = ({ events }) => {
  if (!events.length) return <Text type="secondary">No runtime events captured for this step.</Text>;
  return <div style={{ maxHeight: 420, overflow: 'auto' }}>
    {events.map((event, index) => <EventRow key={index} event={event} />)}
  </div>;
};

export default StepEventTimeline;
