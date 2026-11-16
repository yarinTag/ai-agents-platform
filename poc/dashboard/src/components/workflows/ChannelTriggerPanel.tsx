import { useEffect, useRef, useState } from 'react';
import { Alert, Button, ConfigProvider, Form, Input, InputNumber, Select, Space, Switch, Typography } from 'antd';
import { isAxiosError } from 'axios';
import { Link } from 'react-router-dom';
import { useTranslation } from '../../i18n';
import { useChannelTriggersText } from '../../i18n/channelTriggers';
import {
  getChannelTrigger, matchers, previewChannelTrigger, saveChannelTrigger, triggerFields,
  type TriggerPreview, type TriggerRule, type TriggerSettings,
} from '../../services/channelTriggersApi';

type Mapping = { name: string; source: typeof triggerFields[number] };
const initial: TriggerRule = { binding_id: '', enabled: false, matcher: 'event_type', pattern: 'MESSAGE', parameters: {} };

export function ChannelTriggerPanel({ workflowId, onSaved }: { workflowId: string; onSaved?: (revision: number) => void }) {
  const t = useChannelTriggersText();
  const { dir, locale } = useTranslation();
  const [data, setData] = useState<TriggerSettings>();
  const [rule, setRule] = useState(initial);
  const [mapping, setMapping] = useState<Mapping[]>([]);
  const [sampleSender, setSampleSender] = useState('');
  const [sample, setSample] = useState('');
  const [eventType, setEventType] = useState('MESSAGE');
  const [preview, setPreview] = useState<TriggerPreview>();
  const [notice, setNotice] = useState<'unavailable' | 'invalid' | 'conflict' | 'saved'>();
  const [reload, setReload] = useState(0);
  const [busy, setBusy] = useState(false);
  const current = useRef<AbortController | undefined>(undefined);
  useEffect(() => {
    const request = new AbortController();
    current.current = request;
    setData(undefined); setNotice(undefined); setPreview(undefined); setBusy(false);
    void getChannelTrigger(workflowId, request.signal).then(({ data: settings }) => {
      if (request.signal.aborted) return;
      setData(settings);
      setRule(settings.rule ?? initial);
      setMapping(Object.entries(settings.rule?.parameters ?? {}).map(([name, source]) => ({ name, source })));
    }).catch(() => { if (!request.signal.aborted) setNotice('unavailable'); });
    return () => request.abort();
  }, [workflowId, reload]);

  const senderPattern = /^(?:[0-9]{1,20}|[UW][A-Z0-9]{2,31})$/;
  const valid = Boolean(rule.binding_id && rule.pattern.trim()) &&
    (rule.sender_ids?.every(sender => senderPattern.test(sender)) ?? true) &&
    (!rule.relevance || Boolean(rule.relevance.instructions.trim())) &&
    mapping.every(({ name }) => /^[A-Za-z][A-Za-z0-9_]{0,63}$/.test(name)) &&
    new Set(mapping.map(({ name }) => name)).size === mapping.length;
  const act = async (operation: 'preview' | 'save' | 'clear') => {
    const request = current.current;
    if (!request || request.signal.aborted || !data?.can_edit || busy || (!valid && operation !== 'clear')) return;
    setBusy(true); setNotice(undefined); setPreview(undefined);
    const next = { ...rule, parameters: Object.fromEntries(mapping.map(({ name, source }) => [name, source])) };
    try {
      if (operation === 'preview') {
        const result = await previewChannelTrigger(workflowId, next, eventType, sample, rule.sender_ids?.length ? sampleSender : '', request.signal);
        if (!request.signal.aborted) setPreview(result.data);
      } else {
        const result = await saveChannelTrigger(workflowId, data.revision, operation === 'clear' ? null : next, request.signal);
        if (request.signal.aborted) return;
        setData({ ...data, ...result.data });
        if (operation === 'clear') { setRule(initial); setMapping([]); }
        setNotice('saved');
        onSaved?.(result.data.revision);
      }
    } catch (error) {
      if (!request.signal.aborted) setNotice(isAxiosError(error) && error.response?.status === 409 ? 'conflict' : 'invalid');
    } finally {
      if (!request.signal.aborted) setBusy(false);
    }
  };
  const updateRule = (changes: Partial<TriggerRule>) => { setPreview(undefined); setRule(value => ({ ...value, ...changes })); };
  const updateMapping = (rows: Mapping[]) => { setPreview(undefined); setMapping(rows); };
  return <ConfigProvider direction={dir}><Space orientation="vertical" style={{ width: '100%' }}>
    {notice && <Alert type={notice === 'saved' ? 'success' : 'warning'} title={t[notice]} showIcon />}
    <Button disabled={busy} onClick={() => setReload(value => value + 1)}>{t.reload}</Button>
    {data && !data.can_edit && <>
      <Typography.Text>{t.readOnly}</Typography.Text>
      {data.rule ? <pre dir="ltr">{JSON.stringify(data.rule, null, 2)}</pre> : <Typography.Text>{t.empty}</Typography.Text>}
    </>}
    {data?.can_edit && <Form layout="vertical" disabled={busy} component="div">
      {!data.bindings.length && <Alert title={t.noBindings} type="info" showIcon />}
      <Form.Item label={t.channel}>
        <Select aria-label={t.channel} value={rule.binding_id || undefined} onChange={binding_id => updateRule({ binding_id })}
          options={data.bindings.map(b => ({ value: b.id, label: `${b.channel_name || b.channel_id} · ${b.provider} · ${b.connector_id}` }))} />
      </Form.Item>
      <Form.Item label={t.enabled}><Switch aria-label={t.enabled} checked={rule.enabled} onChange={enabled => updateRule({ enabled })} /></Form.Item>
      <Form.Item label={t.matcher}>
        <Select aria-label={t.matcher} value={rule.matcher} onChange={matcher => updateRule({ matcher })}
          options={matchers.map(value => ({ value, label: t[value] }))} />
      </Form.Item>
      <Form.Item label={t.pattern} extra={rule.matcher === 'regex' ? t.regexHint : undefined}>
        <Input aria-label={t.pattern} value={rule.pattern} maxLength={160} onChange={event => updateRule({ pattern: event.target.value })} />
      </Form.Item>
      <Form.Item label={t.allowedSenders} extra={t.senderHint}>
        <Select mode="tags" aria-label={t.allowedSenders} value={rule.sender_ids || []}
          maxCount={32} onChange={sender_ids => updateRule({ sender_ids })} />
      </Form.Item>
      <Space wrap>
        <Form.Item label={t.cooldown}>
          <InputNumber aria-label={t.cooldown} min={0} max={86400} precision={0}
            value={rule.cooldown_seconds ?? 0} onChange={value => updateRule({ cooldown_seconds: value ?? 0 })} />
        </Form.Item>
        <Form.Item label={t.hourlyLimit}>
          <InputNumber aria-label={t.hourlyLimit} min={1} max={1000} precision={0}
            value={rule.max_runs_per_hour ?? null} onChange={max_runs_per_hour => updateRule({ max_runs_per_hour })} />
        </Form.Item>
      </Space>
      <Form.Item label={t.relevance} extra={t.relevanceHelp}>
        <Switch aria-label={t.relevance} checked={Boolean(rule.relevance)}
          onChange={enabled => updateRule({ relevance: enabled ? { instructions: '', minimum_confidence: 0.8 } : null })} />
      </Form.Item>
      {rule.relevance && <>
        <Form.Item label={t.criterion}>
          <Input.TextArea aria-label={t.criterion} value={rule.relevance.instructions} maxLength={600}
            onChange={event => updateRule({ relevance: { instructions: event.target.value,
              minimum_confidence: rule.relevance?.minimum_confidence ?? 0.8 } })} />
        </Form.Item>
        <Form.Item label={t.confidence}>
          <InputNumber aria-label={t.confidence} min={0.5} max={1} step={0.05}
            value={rule.relevance.minimum_confidence} onChange={value => {
              if (typeof value === 'number' && value >= 0.5 && value <= 1 && rule.relevance) {
                updateRule({ relevance: { ...rule.relevance, minimum_confidence: value } });
              }
            }} />
        </Form.Item>
      </>}
      {mapping.map((row, index) => <Space key={index} wrap style={{ marginBlockEnd: 8 }}>
        <Input aria-label={`${t.parameter} ${index + 1}`} placeholder={t.parameter} value={row.name}
          onChange={event => updateMapping(mapping.map((item, i) => i === index ? { ...item, name: event.target.value } : item))} />
        <Select aria-label={`${t.source} ${index + 1}`} value={row.source}
          onChange={source => updateMapping(mapping.map((item, i) => i === index ? { ...item, source } : item))}
          options={triggerFields.map(value => ({ value, label: t[value] }))} />
        <Button onClick={() => updateMapping(mapping.filter((_, i) => i !== index))}>{t.remove}</Button>
      </Space>)}
      <Form.Item><Button disabled={busy || mapping.length >= 16} onClick={() => updateMapping([...mapping, { name: '', source: 'text' }])}>{t.add}</Button></Form.Item>
      <Form.Item label={t.event_type}><Input aria-label={t.event_type} value={eventType} maxLength={64}
        onChange={event => { setPreview(undefined); setEventType(event.target.value); }} /></Form.Item>
      {!!rule.sender_ids?.length && <Form.Item label={t.sender_id}>
        <Input aria-label={t.sender_id} value={sampleSender} maxLength={32}
          onChange={event => { setPreview(undefined); setSampleSender(event.target.value); }} />
      </Form.Item>}
      <Form.Item label={t.sample} extra={t.previewHint}>
        <Input.TextArea aria-label={t.sample} value={sample} maxLength={2048} onChange={event => { setPreview(undefined); setSample(event.target.value); }} />
      </Form.Item>
      <Space wrap>
        <Button disabled={!valid || Boolean(rule.sender_ids?.length && !senderPattern.test(sampleSender.trim())) || !/^[A-Z][A-Z0-9_]{0,63}$/.test(eventType)} onClick={() => void act('preview')}>{t.preview}</Button>
        <Button type="primary" disabled={!valid || notice === 'conflict'} onClick={() => void act('save')}>{t.save}</Button>
        {data.rule && <Button danger disabled={notice === 'conflict'} onClick={() => void act('clear')}>{t.clear}</Button>}
      </Space>
    </Form>}
    {preview && <Alert title={preview.requires_classification ? t.relevancePending : preview.matched ? t.match : t.noMatch} type={preview.matched && !preview.requires_classification ? 'success' : 'info'}
      description={preview.matched && <pre dir="ltr">{JSON.stringify(preview.parameters, null, 2)}</pre>} />}
    {!!data?.recent_classifications?.length && <details>
      <summary>{t.recentDecisions}</summary>
      <ul>
        {data.recent_classifications.map(result => <li key={result.event_id} style={{ marginBlock: 6 }}>
          <bdi>{new Date(result.updated_at * 1000).toLocaleString(locale)}</bdi>
          {' · '}{t.decisionStates[result.state] ?? result.state}
          {' · '}{t.decisionReasons[result.reason] ?? result.reason}
          {result.execution_id && <> · <Link to={`/workflows/${encodeURIComponent(workflowId)}/logs?execution=${encodeURIComponent(result.execution_id)}`}>{t.openRun}</Link></>}
        </li>)}
      </ul>
    </details>}
  </Space></ConfigProvider>;
}
