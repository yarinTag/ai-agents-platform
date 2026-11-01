import { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { useSearchParams } from 'react-router-dom';
import * as api from '../../services/api';
import { useTranslation } from '../../i18n';
import { useWorkflowChatText } from '../../i18n/workflowChat';
import type { ChatWorkflow, WorkflowChatContext, WorkflowChatJob, WorkflowChatMessage, WorkflowChatRequest } from '../../types/workflowChat';

export function useWorkflowChat(onCreated: () => void) {
  const text = useWorkflowChatText();
  const { locale } = useTranslation();
  const [search, setSearch] = useSearchParams();
  const recoveryId = search.get('workflowChat');
  const [recovering, setRecovering] = useState(!!recoveryId);
  const [connectionError, setConnectionError] = useState('');
  const [context, setContext] = useState<WorkflowChatContext | null>(null);
  const [department, setDepartment] = useState('');
  const [messages, setMessages] = useState<WorkflowChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [job, setJob] = useState<WorkflowChatJob | null>(null);
  const [workflow, setWorkflow] = useState<ChatWorkflow | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [revision, setRevision] = useState(0);
  const alive = useRef(true);
  const base = useRef<WorkflowChatMessage[]>([]);
  const request = useRef<{ body: string; value: WorkflowChatRequest } | null>(null);
  const active = job?.status === 'GENERATING';
  const working = busy || active || recovering || (!!recoveryId && recoveryId !== job?.id);
  const failure = (e: unknown, transient = false) => {
    if (!alive.current) return;
    let explanation = text.error;
    if (axios.isAxiosError(e)) {
      const detail = e.response?.data?.detail;
      if (!e.response) explanation = e.code === 'ECONNABORTED' ? text.timeout : text.connection;
      else if (typeof detail === 'string') explanation = detail;
      else if (Array.isArray(detail)) explanation = detail.slice(0, 3)
        .map((item: { loc?: Array<string | number>; msg?: string }) => `${item.loc?.join('.') || ''}: ${item.msg || text.error}`).join(' · ');
      else explanation = detail?.message || text.httpError.replace('{status}', String(e.response.status));
    }
    if (transient) setConnectionError(explanation); else setError(explanation);
  };
  useEffect(() => {
    if (!recoveryId || recoveryId === job?.id) { setRecovering(false); return; }
    let cancelled = false;
    setRecovering(true);
    api.getWorkflowChat(recoveryId).then(({ data }) => {
      if (cancelled) return;
      base.current = data.messages; setDepartment(data.department_id); setJob(data);
      setMessages([...data.messages, ...(data.result ? [{ role: 'assistant' as const, content: data.result.message }] : [])]);
      setWorkflow(data.result?.workflow || data.previous_workflow || null);
      setError(data.error || ''); setConnectionError('');
    }).catch(e => {
      if (cancelled) return;
      failure(e, true);
      if (axios.isAxiosError(e) && [401, 403, 404].includes(e.response?.status || 0)) {
        setSearch(previous => { const next = new URLSearchParams(previous); next.delete('workflowChat'); return next; }, { replace: true });
      }
    })
      .finally(() => { if (!cancelled) setRecovering(false); });
    return () => { cancelled = true; };
  }, [recoveryId, revision]);

  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  useEffect(() => {
    const changed = () => setRevision(n => n + 1);
    window.addEventListener('platform:runtime-changed', changed);
    return () => window.removeEventListener('platform:runtime-changed', changed);
  }, []);
  useEffect(() => {
    let cancelled = false;
    setLoading(true); setContext(null);
    api.getWorkflowChatContext(department || undefined).then(({ data }) => {
      if (cancelled) return;
      setContext(data);
      if (!recoveryId || recoveryId === job?.id) setConnectionError('');
      if (!department && data.departments.length) setDepartment(previous => previous || data.departments[0].id);
    }).catch(e => { if (!cancelled) failure(e, true); }).finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [department, revision]);
  useEffect(() => {
    if (!job?.id || job.status !== 'GENERATING') return;
    const jobId = job.id;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const { data } = await api.getWorkflowChat(jobId);
        if (cancelled) return;
        setJob(data); setConnectionError('');
        if (data.status === 'GENERATING') timer = setTimeout(poll, 1500);
        else {
          if (data.result) {
            setMessages([...base.current, { role: 'assistant', content: data.result.message }]);
            if (data.result.workflow) setWorkflow(data.result.workflow);
          }
          if (data.error) setError(data.error);
          setRevision(n => n + 1);
        }
      } catch (e) {
        if (cancelled) return;
        failure(e, true);
        if (axios.isAxiosError(e) && [401, 403, 404].includes(e.response?.status || 0)) {
          setWorkflow(null); setMessages([]); setJob(null); return;
        }
        timer = setTimeout(poll, 4000);
      }
    };
    void poll();
    return () => { cancelled = true; clearTimeout(timer); };
  }, [job?.id, job?.status]);

  const send = async () => {
    if (working || loading || !input.trim() || !department || !context?.selection) return;
    const history: WorkflowChatMessage[] = [...messages.slice(-19), { role: 'user', content: input.trim() }];
    const body = { department_id: department, messages: history, previous_workflow: workflow, locale };
    const serialized = JSON.stringify(body);
    if (request.current?.body !== serialized) request.current = {
      body: serialized, value: { ...body, request_id: crypto.randomUUID() },
    };
    const outgoing = request.current?.value;
    if (!outgoing) return;
    setBusy(true); setError('');
    try {
      const { data } = await api.startWorkflowChat(outgoing);
      if (!alive.current) return;
      base.current = history; setMessages(history); setJob(data); setInput(''); setConnectionError('');
      setSearch(previous => { const next = new URLSearchParams(previous); next.set('workflowChat', data.id); return next; }, { replace: true });
      if (data.result) {
        setMessages([...history, { role: 'assistant', content: data.result.message }]);
        if (data.result.workflow) setWorkflow(data.result.workflow);
      }
      if (data.error) setError(data.error);
    } catch (e) { failure(e); }
    finally { if (alive.current) setBusy(false); }
  };
  const stop = async () => {
    if (!job || !active) return true;
    setBusy(true);
    try { const { data } = await api.cancelWorkflowChat(job.id); if (alive.current) setJob(data); return true; }
    catch (e) { failure(e); return false; }
    finally { if (alive.current) setBusy(false); }
  };
  const reset = () => {
    if (working) return;
    setMessages([]); setJob(null); setWorkflow(null); setInput(''); setError(''); setConnectionError(''); request.current = null;
    setSearch(previous => { const next = new URLSearchParams(previous); next.delete('workflowChat'); return next; }, { replace: true });
  };
  const create = async () => {
    if (!job || working || !job.result?.ready) return;
    setBusy(true); setError('');
    try {
      const { data } = await api.createWorkflowFromChat(job.id);
      if (!alive.current) return;
      setJob({ ...job, status: 'CREATED', workflow_id: data.id }); onCreated();
    } catch (e) { failure(e); setRevision(n => n + 1); }
    finally { if (alive.current) setBusy(false); }
  };
  return { text, context, department, setDepartment, messages, input, setInput, job, workflow, error: error || connectionError,
    working, submitting: busy, loading, active, send, stop, reset, create, refresh: () => setRevision(n => n + 1) };
}
