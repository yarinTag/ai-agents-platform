import { Alert, Space, Tag, Typography } from 'antd';
import type { WorkflowStep } from './workflowBuilderTypes';
import { usePrGovernanceText } from '../../i18n/prGovernance';
import { useTranslation } from '../../i18n';
import { record } from './PrEvidence';

/** Presentation of saved declarations, never a policy decision or implicit grant. */
export function PrPermissionSummary({ step }: { step: WorkflowStep }) {
  const text = usePrGovernanceText();
  const { dir } = useTranslation();
  const params = step.params || {};
  const refs = Array.isArray(params.authorized_resources) ? params.authorized_resources.map(record) : [];
  const raw = params.tools || params.mcp_tools || [];
  const tools = [...new Set([...refs.map(r => r.tool_name), ...(Array.isArray(raw) ? raw : [raw])])]
    .filter((v): v is string => typeof v === 'string' && /pull_request/.test(v));
  const workspace = params.workspace;
  const gate = record(params.human_approval);
  if (!tools.length && !workspace && !refs.some(r => typeof r.repository === 'string') && !Object.keys(gate).length) return null;
  const label = (name: string) => name === 'open_pull_request' ? text.draft : name === 'review_pull_request' ? text.review :
    name === 'comment_pull_request' ? text.comment : name === 'merge_pull_request' ? text.merge : text.read;
  const requirements = (name: string) => name === 'get_pull_request_review' ?
    ['get_pull_request', 'get_pull_request_diff', 'get_pull_request_checks'] :
    ['get_pull_request_diff', 'get_pull_request_checks'].includes(name) ? ['get_pull_request'] : [];
  return <div dir={dir} style={{ marginBlock: 12 }}>
    <Typography.Text strong>{text.permissions}</Typography.Text>
    <Typography.Paragraph type="secondary">{text.scopeHelp}</Typography.Paragraph>
    {workspace && <div><Tag>{workspace.mode === 'write' ? text.draft : text.read}</Tag><bdi dir="ltr">{workspace.connector_id} · {workspace.repository}</bdi>
      <div><code dir="ltr">{workspace.mode === 'write' ? 'clone_repository + open_pull_request' : 'clone_repository'}</code></div></div>}
    {tools.map(tool => <div key={tool}><Tag>{label(tool)}</Tag><code dir="ltr">{[tool, ...requirements(tool)].join(' + ')}</code>
      <Space wrap>{refs.filter(r => !r.tool_name || r.tool_name === tool).map((r, i) =>
        <Typography.Text key={i}><bdi dir="ltr">{String(r.connector_id || '')} · {String(r.repository || '')}</bdi></Typography.Text>)}</Space></div>)}
    {!tools.length && !workspace && <Typography.Paragraph>{text.implicit}</Typography.Paragraph>}
    {gate.merge_after_approval === true && <div><Tag color="orange">{text.merge}</Tag><code dir="ltr">get_pull_request_review + get_pull_request + get_pull_request_diff + get_pull_request_checks + merge_pull_request</code></div>}
    <Alert type="info" message={text.mergeHelp} />
  </div>;
}
