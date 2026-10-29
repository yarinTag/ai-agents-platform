import React, { useEffect, useRef, useState } from 'react';
import { Alert, Button, Card, Collapse, Input, Select, Space, Spin, Tag, Typography } from 'antd';
import axios from 'axios';
import { useSearchParams } from 'react-router-dom';
import { useTranslation } from '../i18n';
import * as api from '../services/api';
import type { AssistantCatalog, AssistantContext, AssistantDraft, AssistantErrorBody, AssistantGeneration,
  AssistantMessage, GenerationRequest, ProposalValidation, WorkflowProposal, WorkflowArtifact } from '../types/assistant';

const active = (job: AssistantGeneration | null) => !!job && ['QUEUED', 'RUNNING'].includes(job.status);
const errorText = (error: unknown, fallback: string) => {
  if (axios.isAxiosError<AssistantErrorBody>(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === 'string') return detail;
    if (detail && !Array.isArray(detail)) return detail.message || detail.code || fallback;
  }
  return fallback;
};

export default function WorkflowAssistantPage() {
  const { t, locale, dir } = useTranslation();
  const [search, setSearch] = useSearchParams();
  const jobId = search.get('generation');
  const [context, setContext] = useState<AssistantContext | null>(null);
  const [department, setDepartment] = useState('');
  const [modelChoice, setModelChoice] = useState('');
  const [artifact, setArtifact] = useState<Partial<WorkflowArtifact> | null>(null);
  const [schemaYaml, setSchemaYaml] = useState('');
  const [catalog, setCatalog] = useState<AssistantCatalog | null>(null);
  const [drafts, setDrafts] = useState<AssistantDraft[]>([]);
  const [source, setSource] = useState<{ id: string; revision: number } | null>(null);
  const [messages, setMessages] = useState<AssistantMessage[]>([]);
  const [intent, setIntent] = useState('');
  const [input, setInput] = useState('');
  const [job, setJob] = useState<AssistantGeneration | null>(null);
  const [proposal, setProposal] = useState<WorkflowProposal | null>(null);
  const [validation, setValidation] = useState<ProposalValidation | null>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const [history, setHistory] = useState<Array<{ revision: number; actor_label: string; created_at: string; snapshot: { proposal: WorkflowProposal; status: string; definition_yaml?: string | null } }>>([]);
  const requestKey = useRef({ body: '', key: '' });
  const epoch = useRef(0);
  const working = busy || active(job) || !!(jobId && !job);
  const stale = !!source && drafts.some(d => d.id === source.id && d.revision !== source.revision);
  const write = !!catalog?.can_write_drafts && !!context?.supports_generation;
  const clear = () => {
    epoch.current += 1;
    setJob(null); setMessages([]); setIntent(''); setProposal(null); setValidation(null);
    setArtifact(null); setSource(null); setError(''); setNotice(''); setInput(''); setSearch({}, { replace: true });
  };
  useEffect(() => {
    let cancelled = false;
    api.getAssistantContext().then(({ data }) => {
      if (!cancelled) { setContext(data); setDepartment(old => old || data.departments[0]?.id || '');
        setModelChoice(old => data.authoring_models.some(m => `${m.provider_id}:${m.model_id}` === old)
          ? old : data.authoring_models[0] ? `${data.authoring_models[0].provider_id}:${data.authoring_models[0].model_id}` : ''); }
    }).catch(e => { if (!cancelled) setError(errorText(e, t('assistant.error'))); });
    api.getAssistantWorkflowSchema().then(({ data }) => { if (!cancelled) setSchemaYaml(data.yaml_schema); })
      .catch(e => { if (!cancelled) setError(errorText(e, t('assistant.error'))); });
    return () => { cancelled = true; };
  }, [t]);
  useEffect(() => {
    if (!department) return;
    let cancelled = false;
    setCatalog(null); setDrafts([]);
    Promise.all([api.getAssistantCatalog(department), api.getAssistantDrafts(department)])
      .then(([c, d]) => {
        if (cancelled) return;
        setCatalog(c.data); setDrafts(d.data);
      }).catch(e => { if (!cancelled) { clear(); setError(errorText(e, t('assistant.error'))); } });
    return () => { cancelled = true; };
    // clear resets private state on an authorization failure; it is not an effect dependency.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [department, refresh, t]);
  useEffect(() => {
    if (!jobId) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const { data } = await api.getAssistantGeneration(jobId);
        if (cancelled) return;
        setJob(data); setDepartment(data.department_id);
        if (data.request.provider_id !== 'legacy') setModelChoice(`${data.request.provider_id}:${data.request.model_id}`);
        setArtifact(data.result);
        setIntent(data.request.intent_text || data.request.messages[0]?.content || '');
        setMessages([...data.request.messages, ...(data.result ? [{ role: 'assistant' as const, content: data.result.assistant_message }] : [])]);
        setProposal(data.result?.proposal || null); setValidation(data.result?.validation || null);
        setSource(data.saved_draft_id && data.saved_draft_revision
          ? { id: data.saved_draft_id, revision: data.saved_draft_revision }
          : data.request.draft_id && data.request.expected_draft_revision
            ? { id: data.request.draft_id, revision: data.request.expected_draft_revision } : null);
        if (data.error_message) setError(data.error_message);
        if (active(data)) timer = setTimeout(poll, 1500);
        else setRefresh(n => n + 1);
      } catch (e) {
        if (cancelled) return;
        if (axios.isAxiosError(e) && [403, 404].includes(e.response?.status || 0)) {
          setJob(null); setMessages([]); setProposal(null); setValidation(null); setSource(null); setArtifact(null);
          setSearch({}, { replace: true });
          setError(errorText(e, t('assistant.error')));
          return;
        }
        setError(errorText(e, t('assistant.error')));
        timer = setTimeout(poll, 5000);
      }
    };
    void poll();
    return () => { cancelled = true; clearTimeout(timer); };
  }, [jobId, t]);

  useEffect(() => {
    setHistory([]);
    if (!source) return;
    let cancelled = false;
    api.getAssistantDraftHistory(source.id).then(({ data }) => {
      if (!cancelled) setHistory(data);
    }).catch(e => { if (!cancelled) setError(errorText(e, t('assistant.error'))); });
    return () => { cancelled = true; };
  }, [source?.id, source?.revision, refresh, t]);

  const loadDraft = async (id: string) => {
    const version = ++epoch.current;
    setBusy(true); setError('');
    try {
      const { data } = await api.getAssistantDraft(id);
      if (version !== epoch.current) return;
      clear(); setDepartment(data.department_id); setProposal(data.proposal); setValidation(data.validation);
      setArtifact(data); setIntent(data.intent_text); setSource({ id: data.id, revision: data.revision });
      setRefresh(n => n + 1);
    } catch (e) { setError(errorText(e, t('assistant.error'))); }
    finally { setBusy(false); }
  };
  const send = async () => {
    if (!input.trim() || !modelChoice || working || !write || stale) return;
    const selected = context?.authoring_models.find(m => `${m.provider_id}:${m.model_id}` === modelChoice);
    if (!selected) { setError(t('assistant.noModels')); return; }
    const request: GenerationRequest = { department_id: department, model_id: selected.model_id, provider_id: selected.provider_id, locale,
      intent_text: intent || input.trim(), messages: [...messages.slice(-19), { role: 'user', content: input.trim() }],
      ...(proposal ? { previous_proposal: proposal } : {}),
      ...(source ? { draft_id: source.id, expected_draft_revision: source.revision } : {}) };
    const body = JSON.stringify(request);
    if (requestKey.current.body !== body) requestKey.current = { body, key: crypto.randomUUID() };
    setBusy(true); setError(''); setNotice('');
    try {
      const { data } = await api.createAssistantGeneration(request, requestKey.current.key);
      setJob(data); setMessages(request.messages); setIntent(request.intent_text); setInput('');
      setProposal(null); setValidation(null); setArtifact(null); setSearch({ generation: data.id }, { replace: true });
    } catch (e) { setError(errorText(e, t('assistant.error'))); }
    finally { setBusy(false); }
  };
  const save = async () => {
    if (!job || !proposal || working || stale) return;
    setBusy(true); setError('');
    try {
      const { data } = await api.saveAssistantGeneration(job.id, !validation?.valid);
      setSource({ id: data.id, revision: data.revision }); setValidation(data.validation); setArtifact(data);
      setJob({ ...job, saved_draft_id: data.id, saved_draft_revision: data.revision });
      setNotice(t('assistant.saved', { revision: data.revision })); setRefresh(n => n + 1);
    } catch (e) { setError(errorText(e, t('assistant.error'))); setRefresh(n => n + 1); }
    finally { setBusy(false); }
  };

  return <div dir={dir} style={{ padding: 24, maxWidth: 1400, margin: '0 auto', width: '100%' }}>
    <Typography.Title level={2}>{t('assistant.title')}</Typography.Title>
    <Typography.Paragraph type="secondary">{t('assistant.intro')}</Typography.Paragraph>
    {error && <Alert type="error" showIcon message={error} style={{ marginBottom: 16 }} />}
    {notice && <Alert type="success" showIcon message={notice} style={{ marginBottom: 16 }} />}
    {context && !context.supports_generation && <Alert type="warning" message={t('assistant.unavailable')} />}
    <Space wrap style={{ marginBlock: 16 }}>
      <Select aria-label={t('assistant.department')} placeholder={t('assistant.department')} value={department || undefined}
        disabled={working} style={{ width: 220 }} options={context?.departments.map(d => ({ value: d.id, label: d.name }))}
        onChange={id => { clear(); setDepartment(id); }} />
      <Select aria-label={t('assistant.model')} placeholder={t('assistant.model')} value={modelChoice || undefined}
        disabled={working} style={{ minWidth: 260 }} options={context?.authoring_models.map(m => ({ value: `${m.provider_id}:${m.model_id}`, label: `${m.name} · ${m.provider_id}` }))} onChange={setModelChoice} />
      <Select aria-label={t('assistant.drafts')} placeholder={t('assistant.drafts')} value={source?.id}
        disabled={working} style={{ minWidth: 230 }} options={drafts.map(d => ({ value: d.id, label: `${d.proposal.name} · v${d.revision}` }))}
        onChange={id => void loadDraft(id)} />
      <Button disabled={working} onClick={clear}>{t('assistant.new')}</Button>
      <Button disabled={working} onClick={() => setRefresh(n => n + 1)}>{t('assistant.refresh')}</Button>
    </Space>
    {!context || (!catalog && !!department) ? <Spin /> : null}
    {catalog && !catalog.can_write_drafts && <Alert type="info" message={t('assistant.readOnly')} />}
    {context && !context.authoring_models.length && <Alert type="warning" message={t('assistant.noModels')} />}
    {catalog && !catalog.agents.length && <Alert type="info" message={t('assistant.noAgents')} />}
    {stale && <Alert type="warning" message={t('assistant.stale')} action={<Button disabled={working} onClick={() => source && void loadDraft(source.id)}>{t('assistant.reload')}</Button>} />}
    {catalog && <Collapse style={{ marginBlock: 16 }} items={[{ key: 'resources', label: t('assistant.resources'), children: <>
      {catalog.connectors.map(c => <Card size="small" key={c.id} style={{ marginBottom: 8 }} title={<>{c.name} <Tag>{c.available ? 'CONNECTED' : 'UNAVAILABLE'}</Tag></>}>
        <div dir="ltr">{[...c.tools.map(tool => tool.name), ...c.repositories, ...c.channels].map(item => <Tag key={item}>{item}</Tag>)}</div>
      </Card>)}
      {catalog.limitations.map(item => <Typography.Paragraph key={item} type="secondary">{item}</Typography.Paragraph>)}
    </> }]} />}
    {!!schemaYaml && <Collapse style={{ marginBottom: 16 }} items={[{ key: 'schema', label: t('assistant.yamlSchema'), children: <pre dir="ltr" style={{ maxHeight: 350, overflow: 'auto' }}>{schemaYaml}</pre> }]} />}
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 400px), 1fr))', gap: 20 }}>
      <Card title={t('assistant.title')}>
        {!messages.length && <Typography.Paragraph type="secondary">{t('assistant.empty')}</Typography.Paragraph>}
        <div style={{ maxHeight: 500, overflowY: 'auto', marginBottom: 16 }} aria-live="polite">
          {messages.map((message, i) => <Card size="small" key={i} style={{ marginBottom: 10, background: message.role === 'user' ? '#10251f' : undefined }}>
            <Typography.Text strong>{message.role === 'user' ? t('common.you') : t('assistant.title')}</Typography.Text>
            <div style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{message.content}</div>
          </Card>)}
        </div>
        {job?.result?.questions?.length ? <Alert type="info" message={t('assistant.questions')} description={<ul>{job.result.questions.map(q => <li key={q}>{q}</li>)}</ul>} style={{ marginBottom: 16 }} /> : null}
        <Input.TextArea aria-label={t('assistant.message')} value={input} onChange={e => setInput(e.target.value)} maxLength={8000}
          autoSize={{ minRows: 4, maxRows: 10 }} placeholder={t('assistant.message')} disabled={working || !write || stale} />
        <Space wrap style={{ marginTop: 12 }}>
          <Button type="primary" loading={working} disabled={!input.trim() || !modelChoice || !write || stale} onClick={() => void send()}>{t('assistant.send')}</Button>
          {active(job) && <Button onClick={async () => {
            try { if (job) setJob((await api.cancelAssistantGeneration(job.id)).data); }
            catch (e) { setError(errorText(e, t('assistant.error'))); }
          }}>{t('assistant.stop')}</Button>}
          {job && <Tag>{job.status}</Tag>}
        </Space>
        {!!job?.tool_calls.length && <div dir="ltr" style={{ marginTop: 12 }}>{job.tool_calls.map((call, i) => <Tag key={i}>MCP · {call.tool_name}</Tag>)}</div>}
        {job && <Typography.Paragraph type="secondary" style={{ marginTop: 12 }}>
          {job.model} · {t('assistant.tokens')}: {job.input_tokens + job.output_tokens} · {t('assistant.cost')}: {job.cost_usd == null ? t('assistant.unknown') : `$${job.cost_usd.toFixed(4)}`} {job.cost_source}
        </Typography.Paragraph>}
      </Card>
      <Card title={t('assistant.proposal')} extra={source && <Tag>v{source.revision}</Tag>}>
        {proposal && <>
          <Typography.Title level={4}>{proposal.name}</Typography.Title>
          <Typography.Paragraph>{proposal.description}</Typography.Paragraph>
          <Tag>{proposal.trigger.kind}</Tag>
          <Typography.Paragraph style={{ overflowWrap: 'anywhere' }}>{[proposal.trigger.repository, proposal.trigger.channel_id, proposal.trigger.event, proposal.trigger.cron_expression].filter(Boolean).join(' · ')}</Typography.Paragraph>
          {proposal.steps.map(step => <Card size="small" key={step.key} style={{ marginBlock: 10 }} title={`${step.name} · ${catalog?.agents.find(a => a.id === step.agent_id)?.name || step.agent_id}`}>
            <div>{step.prompt_template}</div>
            {!!step.depends_on.length && <div>{t('assistant.dependencies')}: {step.depends_on.join(', ')}</div>}
            <div dir="ltr">{[...step.tools.map(v => `${v.connector_id}/${v.tool_name}`), ...step.repositories.map(v => v.repository), ...step.channels.map(v => v.channel_id), ...step.skills].map(v => <Tag key={v}>{v}</Tag>)}</div>
            {step.requires_approval && <Tag color="orange">{t('assistant.approval')}</Tag>}
          </Card>)}
          {proposal.unresolved_requirements.map(item => <Alert key={item} type="warning" message={item} style={{ marginBlock: 8 }} />)}
          {validation && <Alert type={validation.valid ? 'success' : 'warning'} message={validation.status}
            description={validation.errors.map((e, i) => <div key={i}><code>{e.code} · {e.path}</code>: {e.message}</div>)} />}
          <Space wrap style={{ marginBlock: 12 }}>
            <Button disabled={working} onClick={async () => {
              setBusy(true);
              try {
                if (artifact?.definition_yaml) {
                  const { data } = await api.validateAssistantYaml(department, artifact.definition_yaml);
                  setValidation(data.validation); setArtifact(data);
                } else setValidation((await api.validateAssistantProposal(department, proposal)).data);
              }
              catch (e) { setError(errorText(e, t('assistant.error'))); }
              finally { setBusy(false); }
            }}>{t('assistant.validate')}</Button>
            <Button type={validation?.valid ? 'primary' : 'default'} disabled={working || !write || stale || job?.status !== 'COMPLETED' || !!job.saved_draft_id || !validation}
              onClick={() => void save()}>{t(validation?.valid ? 'assistant.save' : 'assistant.saveBlocked')}</Button>
          </Space>
          {!!history.length && <Collapse style={{ marginBottom: 12 }} items={[{ key: 'history', label: t('assistant.history'), children: history.map(h => <Collapse key={h.revision} items={[{ key: String(h.revision), label: `v${h.revision} · ${h.actor_label} · ${h.created_at} · ${h.snapshot.status}`, children: <pre dir="ltr" style={{ maxHeight: 300, overflow: 'auto' }}>{h.snapshot.definition_yaml || JSON.stringify(h.snapshot.proposal, null, 2)}</pre> }]} />) }]} />}
          {artifact?.yaml_error && <Alert type="warning" message={artifact.yaml_error} />}
          {artifact?.definition_yaml && <>
            <Button style={{ marginBlock: 12 }} onClick={() => {
              const blob = new Blob([artifact.definition_yaml || ''], { type: 'application/yaml;charset=utf-8' });
              const url = URL.createObjectURL(blob); const link = document.createElement('a');
              link.href = url; link.download = 'workflow-draft.yaml'; link.click(); URL.revokeObjectURL(url);
            }}>{t('assistant.downloadYaml')}</Button>
            <Typography.Paragraph type="secondary">{t('assistant.yamlDraft')}</Typography.Paragraph>
            <pre dir="ltr" style={{ maxHeight: 500, overflow: 'auto', background: '#0d1117', padding: 12 }}>{artifact.definition_yaml}</pre>
          </>}
          <Collapse items={[{ key: 'json' , label: t('assistant.json'), children: <pre dir="ltr" style={{ maxHeight: 400, overflow: 'auto' }}>{JSON.stringify(proposal, null, 2)}</pre> }]} />
        </>}
      </Card>
    </div>
  </div>;
}
