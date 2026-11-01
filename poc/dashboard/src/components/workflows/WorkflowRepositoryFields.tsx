import { Alert, Input, Select, Space, Typography } from 'antd';
import type { WorkflowChatContext } from '../../types/workflowChat';
import type { RepositoryWorkspaceConfig, WorkflowStep } from './workflowBuilderTypes';
import { useWorkflowChatText } from '../../i18n/workflowChat';

type Catalog = NonNullable<WorkflowChatContext['catalog']>;

export function WorkflowRepositoryFields({ step, catalog, error, loading, onChange }: {
  step: WorkflowStep; catalog: Catalog | null; error: string | null; loading: boolean;
  onChange: (value: Partial<WorkflowStep>) => void;
}) {
  const text = useWorkflowChatText();
  const workspace = step.params?.workspace;
  const mode = workspace?.mode || 'connector';
  const connectors = (catalog?.connectors || []).filter(item => item.provider === 'github');
  const selected = connectors.find(item => item.id === workspace?.connector_id);
  const canWrite = connectors.some(item => ['clone_repository', 'open_pull_request']
    .every(operation => item.workspace_operations?.includes(operation)));
  const updateWorkspace = (changes: Partial<RepositoryWorkspaceConfig>) => {
    if (!workspace) return;
    onChange({ params: { ...step.params, workspace: { ...workspace, ...changes } } });
  };
  const changeMode = (value: 'connector' | 'read' | 'write') => {
    const params = { ...step.params };
    delete params.workspace; delete params.required_outcome;
    if (value === 'connector') { onChange({ params }); return; }
    delete params.authorized_resources; delete params.channel_action;
    delete params.tools; delete params.mcp_tools;
    params.workspace = { connector_id: workspace?.connector_id || '', repository: workspace?.repository || '',
      ref: workspace?.ref || null, mode: value, pr_title: workspace?.pr_title || null };
    if (value === 'write') params.required_outcome = 'pull_request';
    onChange({ mcp_servers: [], params });
  };
  return <Space direction="vertical" style={{ width: '100%', marginBottom: 12 }}>
    <Typography.Text type="secondary">{text.executionMode}</Typography.Text>
    <Select style={{ width: '100%' }} value={mode} loading={loading} onChange={changeMode}
      options={[{ value: 'connector', label: text.connectorMode },
        { value: 'read', label: text.readWorkspace, disabled: !connectors.some(item => item.workspace_operations?.includes('clone_repository')) },
        { value: 'write', label: text.draftPr, disabled: !canWrite }]} />
    {error && <Alert type="warning" message={text.workspaceCatalogError} />}
    {!loading && !canWrite && <Typography.Text type="secondary">{text.workspacePermissionHint}</Typography.Text>}
    {workspace && <>
      <Alert type="info" message={text.workspaceIsolation} />
      <Select style={{ width: '100%' }} value={workspace.connector_id || undefined} placeholder={text.workspaceConnector}
        onChange={connector_id => updateWorkspace({ connector_id, repository: '' })}
        options={connectors.filter(item => item.workspace_operations?.includes('clone_repository') &&
          (mode !== 'write' || item.workspace_operations?.includes('open_pull_request')))
          .map(item => ({ value: item.id, label: item.name }))} />
      <Select style={{ width: '100%' }} value={workspace.repository || undefined} placeholder={text.repositories}
        onChange={repository => updateWorkspace({ repository })}
        options={(selected?.repositories || []).map(value => ({ value, label: value }))} />
      <Input value={workspace.ref || ''} placeholder={text.workspaceRef}
        onChange={event => updateWorkspace({ ref: event.target.value || null })} />
      {workspace.mode === 'write' && <Input value={workspace.pr_title || ''} placeholder={text.workspacePrTitle}
        onChange={event => updateWorkspace({ pr_title: event.target.value || null })} />}
      {catalog?.workspace_readiness && !catalog.workspace_readiness.configured &&
        <Alert type="warning" message={text.workspaceSetupRequired} description={catalog.workspace_readiness.errors.join(' ')} />}
    </>}
  </Space>;
}
