import { useEffect, useRef, useState } from 'react';
import { Alert, Button, ConfigProvider, Form, Input, Select, Space, Switch, Typography } from 'antd';
import { isAxiosError } from 'axios';
import { useTranslation } from '../../i18n';
import { useChannelTriggersText } from '../../i18n/channelTriggers';
import {
  getChannelTrigger, matchers, previewChannelTrigger, saveChannelTrigger, triggerFields,
  type TriggerRule, type TriggerSettings,
} from '../../services/channelTriggersApi';

type Mapping = { name: string; source: typeof triggerFields[number] };
const initial: TriggerRule = { binding_id: '', enabled: false, matcher: 'event_type', pattern: 'MESSAGE', parameters: {} };

export function ChannelTriggerPanel({ workflowId, onSaved }: { workflowId: string; onSaved?: (revision: number) => void }) {
  const t = useChannelTriggersText();
  const { dir } = useTranslation();
  const [data, setData] = useState<TriggerSettings>();
  const [rule, setRule] = useState(initial);
  const [mapping, setMapping] = useState<Mapping[]>([]);
  const [sample, setSample] = useState('');
  const [eventType, setEventType] = useState('MESSAGE');
  const [preview, setPreview] = useState<{ matched: boolean; parameters: Record<string, string | null> | null }>();
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

  const valid = Boolean(rule.binding_id && rule.pattern.trim()) &&
    mapping.every(({ name }) => /^[A-Za-z][A-Za-z0-9_]{0,63}$/.test(name)) &&
    new Set(mapping.map(({ name }) => name)).size === mapping.length;
  const act = async (operation: 'preview' | 'save' | 'clear') => {
    const request = current.current;
    if (!request || request.signal.aborted || !data?.can_edit || busy || (!valid && operation !== 'clear')) return;
    setBusy(true); setNotice(undefined); setPreview(undefined);
    const next = { ...rule, parameters: Object.fromEntries(mapping.map(({ name, source }) => [name, source])) };
    try {
      if (operation === 'preview') {
        const result = await previewChannelTrigger(workflowId, next, eventType, sample, request.signal);
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
      <Form.Item label={t.sample} extra={t.previewHint}>
        <Input.TextArea aria-label={t.sample} value={sample} maxLength={2048} onChange={event => { setPreview(undefined); setSample(event.target.value); }} />
      </Form.Item>
      <Space wrap>
        <Button disabled={!valid || !/^[A-Z][A-Z0-9_]{0,63}$/.test(eventType)} onClick={() => void act('preview')}>{t.preview}</Button>
        <Button type="primary" disabled={!valid || notice === 'conflict'} onClick={() => void act('save')}>{t.save}</Button>
        {data.rule && <Button danger disabled={notice === 'conflict'} onClick={() => void act('clear')}>{t.clear}</Button>}
      </Space>
    </Form>}
    {preview && <Alert title={preview.matched ? t.match : t.noMatch} type={preview.matched ? 'success' : 'info'}
      description={preview.matched && <pre dir="ltr">{JSON.stringify(preview.parameters, null, 2)}</pre>} />}
  </Space></ConfigProvider>;
}
