import { Link } from 'react-router-dom';
import { Tag } from 'antd';
import type { Task } from '../types/task';
import type { WorkflowExecution } from '../types/mcp';

const statusColors: Record<string, string> = {
  COMPLETED: 'success', FAILED: 'error', RUNNING: 'processing',
  QUEUED: 'default', CANCELLED: 'default', WAITING_APPROVAL: 'warning',
};
const statusColor = (status: string) => statusColors[status.toUpperCase()] || 'default';

function Timing({ start, end }: { start?: string | null; end?: string | null }) {
  const startMs = start ? Date.parse(start) : NaN;
  const endMs = end ? Date.parse(end) : NaN;
  const time = (value?: string | null) => value && Number.isFinite(Date.parse(value))
    ? new Date(value).toLocaleString() : 'Unavailable';
  return <div style={{ fontSize: 12, color: '#8b949e' }}>
    Start: {time(start)} · End: {time(end)}
    {Number.isFinite(startMs) && Number.isFinite(endMs) && endMs >= startMs
      ? ` · Duration: ${Math.round((endMs - startMs) / 1000)}s` : ''}
  </div>;
}

export function CalendarRun({ task, execution, compact = false }: {
  task?: Task; execution?: WorkflowExecution; compact?: boolean;
}) {
  const workflowId = execution?.workflow_id || task?.workflow_id;
  const executionId = execution?.id || task?.workflow_execution_id;
  const logs = workflowId && executionId
    ? `/workflows/${encodeURIComponent(workflowId)}/logs?execution=${encodeURIComponent(executionId)}` : null;
  const status = execution?.status || task?.status || 'UNKNOWN';
  const trigger = execution?.trigger_type;
  return <div style={{ marginBottom: compact ? 2 : 12 }} onClick={event => event.stopPropagation()}>
    {task && <Link to={`/tasks?taskId=${encodeURIComponent(task.id)}`}>Task #{task.id}</Link>}
    {logs && <Link to={logs} title={`Open workflow execution ${executionId} logs`}>
      {task ? ' · Workflow logs' : `Workflow run #${executionId}`}
    </Link>}
    <Tag color={statusColor(status)}>{status.toUpperCase()}</Tag>
    {!compact && <>
      {task && <span> ({task.agent_id})</span>}
      <Tag>{trigger ? (trigger.toUpperCase() === 'CRON' ? 'Scheduled (cron)' : trigger) : 'Trigger unavailable'}</Tag>
      <Timing start={execution?.started_at || task?.started_at} end={execution?.completed_at || task?.ended_at} />
    </>}
  </div>;
}
