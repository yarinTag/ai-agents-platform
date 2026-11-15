import { useEffect, useState } from 'react';
import axios from 'axios';
import { getWorkflow, getWorkflowExecution, getWorkflowExecutions } from '../services/workflowsApi';
import type { PlatformWorkflow, WorkflowExecution } from '../types/mcp';

type Snapshot = {
  scope: string;
  workflow: PlatformWorkflow;
  runs: WorkflowExecution[];
  execution: WorkflowExecution | null;
};
const isActive = (run: WorkflowExecution) =>
  ['PENDING', 'QUEUED', 'RUNNING', 'WAITING_APPROVAL'].includes(run.status);

export function useWorkflowLogData(workflowId: string | undefined, selectedId: string | null) {
  const scope = JSON.stringify([workflowId, selectedId]);
  const [snapshot, setSnapshot] = useState<Snapshot>();
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    if (!workflowId) return;
    const request = new AbortController();
    const { signal } = request;
    let workflow: PlatformWorkflow | undefined;
    let executionId = selectedId;
    let timer: number | undefined;
    let shouldRefresh = true;
    setLoading(true);
    setError('');

    const load = async () => {
      try {
        const [metadata, history] = await Promise.all([
          workflow ? Promise.resolve(workflow) : getWorkflow(workflowId, signal).then(({ data }) => data),
          getWorkflowExecutions(workflowId, 200, undefined, signal),
        ]);
        workflow = metadata;
        executionId ??= history.data[0]?.id ?? null;
        const execution = executionId ? (await getWorkflowExecution(executionId, signal)).data : null;
        if (execution && execution.workflow_id !== workflowId) throw new Error('Execution does not belong to this workflow');
        if (signal.aborted) return;
        setSnapshot({ scope, workflow, runs: history.data, execution });
        setError('');
        shouldRefresh = history.data.some(isActive) || Boolean(execution && isActive(execution));
      } catch (cause: unknown) {
        if (signal.aborted) return;
        const detail = axios.isAxiosError(cause) ? cause.response?.data?.detail : null;
        setError(typeof detail === 'string' ? detail : cause instanceof Error ? cause.message : 'Unable to load workflow logs');
      } finally {
        if (!signal.aborted) {
          setLoading(false);
          if (shouldRefresh) timer = window.setTimeout(() => void load(), 10_000);
        }
      }
    };

    void load();
    return () => {
      request.abort();
      window.clearTimeout(timer);
    };
  }, [workflowId, selectedId, scope, revision]);

  const sameScope = snapshot?.scope === scope;
  return {
    workflow: sameScope ? snapshot.workflow : null,
    runs: sameScope ? snapshot.runs : [],
    execution: sameScope ? snapshot.execution : null,
    error,
    loading,
    refresh: () => setRevision(value => value + 1),
  };
}
