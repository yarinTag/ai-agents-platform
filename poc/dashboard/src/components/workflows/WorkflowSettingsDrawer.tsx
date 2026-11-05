import React, { useCallback, useEffect, useState } from 'react';
import { Alert, Button, Divider, Drawer, Empty, Flex, Segmented, Select, Spin, Tag, Typography, message, theme } from 'antd';
import { CloudServerOutlined, GlobalOutlined, LockOutlined, RobotOutlined, SaveOutlined } from '@ant-design/icons';
import { getWorkflowSettings, updateWorkflowSettings } from '../../services/api';
import type { PlatformWorkflow } from '../../types/mcp';
import {
  WORKFLOW_MACHINE_SIZES,
  type WorkflowMachineSize,
  type ExecutionBackend,
  type WorkflowSecretSummary,
  type WorkflowSettingsResponse,
  type WorkflowSettingsValues,
} from '../../types/workflowSettings';
import { formatWorkflowSettingsText as fill, useWorkflowSettingsText } from '../../i18n/workflowSettings';
import { useRequestGeneration } from '../../hooks/useRequestGeneration';
import { WorkflowBackendSelect } from './WorkflowBackendSelect';
import { WorkflowModelSelect } from './WorkflowModelSelect';
import { WorkflowSecretsSection } from './WorkflowSecretsSection';
import {
  type ApiFailure, describeApiFailure, formatMemory, fromModelValue, isValidHost, normalizeHosts, toModelValue,
} from './workflowSettingsRules';

interface WorkflowSettingsDrawerProps {
  workflow: Pick<PlatformWorkflow, 'id' | 'name'>;
  onClose: () => void;
  /** Called after settings are saved (the workflow revision changed). */
  onSaved?: () => void;
}

type SaveProblem = { kind: 'conflict' } | { kind: 'error'; message: string } | null;

const sameHosts = (left: readonly string[], right: readonly string[]) =>
  left.length === right.length && left.every((host, index) => host === right[index]);

export const WorkflowSettingsDrawer: React.FC<WorkflowSettingsDrawerProps> = ({ workflow, onClose, onSaved }) => {
  const text = useWorkflowSettingsText();
  const { token } = theme.useToken();
  const [data, setData] = useState<WorkflowSettingsResponse | null>(null);
  const [baseline, setBaseline] = useState<WorkflowSettingsValues | null>(null);
  const [backend, setBackend] = useState<ExecutionBackend>('direct_api');
  const [model, setModel] = useState<string>(toModelValue(null));
  const [machineSize, setMachineSize] = useState<WorkflowMachineSize>('medium');
  const [hosts, setHosts] = useState<string[]>([]);
  const [secrets, setSecrets] = useState<WorkflowSecretSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadFailure, setLoadFailure] = useState<ApiFailure | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveProblem, setSaveProblem] = useState<SaveProblem>(null);
  const loads = useRequestGeneration();
  const saves = useRequestGeneration();

  /** Replace all local state with the server's view (initial load, reload after 409, successful save). */
  const apply = useCallback((response: WorkflowSettingsResponse) => {
    const settings: WorkflowSettingsValues = {
      execution_backend: response.settings.execution_backend ?? 'direct_api',
      model: response.settings.model ?? null,
      machine_size: response.settings.machine_size,
      network_allowlist: normalizeHosts(response.settings.network_allowlist ?? []),
    };
    setData(response);
    setBaseline(settings);
    setBackend(settings.execution_backend ?? 'direct_api');
    setModel(toModelValue(settings.model));
    setMachineSize(settings.machine_size);
    setHosts(settings.network_allowlist);
    setSecrets(response.secrets ?? []);
    setSaveProblem(null);
  }, []);

  const load = useCallback(async () => {
    const current = loads.begin();
    setLoading(true);
    setLoadFailure(null);
    try {
      const response = await getWorkflowSettings(workflow.id);
      if (current()) apply(response.data);
    } catch (cause: unknown) {
      if (current()) setLoadFailure(describeApiFailure(cause));
    } finally {
      if (current()) setLoading(false);
    }
  }, [workflow.id, apply, loads.begin]);

  useEffect(() => {
    void load();
    return () => { loads.invalidate(); saves.invalidate(); };
  }, [load, loads.invalidate, saves.invalidate]);

  const canManage = Boolean(data?.can_manage);
  const maxHosts = data?.max_allowed_hosts ?? 0;
  const invalidHosts = hosts.filter(host => !isValidHost(host));
  const tooManyHosts = maxHosts > 0 && hosts.length > maxHosts;
  // null and "default" both mean platform default, so compare normalized model values.
  const dirty = baseline !== null && (
    fromModelValue(model) !== fromModelValue(toModelValue(baseline.model))
    || backend !== (baseline.execution_backend ?? 'direct_api')
    || machineSize !== baseline.machine_size
    || !sameHosts(hosts, baseline.network_allowlist)
  );
  // A stored invalid configuration can be repaired by saving the (default) values shown.
  // After a 409 the stale revision would conflict again, so saving waits for an explicit reload.
  const canSave = canManage && !loading && !saving && (dirty || Boolean(data?.settings_error))
    && invalidHosts.length === 0 && !tooManyHosts && saveProblem?.kind !== 'conflict';

  const save = async () => {
    if (!data || !canSave) return;
    const current = saves.begin();
    setSaving(true);
    setSaveProblem(null);
    try {
      const response = await updateWorkflowSettings(workflow.id, {
        settings: { execution_backend: backend, model: fromModelValue(model), machine_size: machineSize, network_allowlist: hosts },
        expected_revision: data.revision,
      });
      if (!current()) return;
      apply(response.data);
      message.success(text.saved);
      onSaved?.();
    } catch (cause: unknown) {
      if (!current()) return;
      const failure = describeApiFailure(cause);
      // On every failure the edited values stay in the form.
      if (failure.status === 409) setSaveProblem({ kind: 'conflict' });
      else if (failure.status === 403) setSaveProblem({ kind: 'error', message: failure.detail || text.forbidden });
      else if (failure.status === 400 || failure.status === 422) {
        setSaveProblem({ kind: 'error', message: fill(text.invalid, { detail: failure.detail || text.saveFailed }) });
      } else setSaveProblem({ kind: 'error', message: failure.detail || text.saveFailed });
    } finally {
      if (current()) setSaving(false);
    }
  };

  const sectionTitle = (icon: React.ReactNode, title: string) => (
    <Typography.Title level={5} style={{ margin: 0 }}>{icon} {title}</Typography.Title>
  );
  const helpText = (content: string) => (
    <Typography.Text type="secondary" style={{ fontSize: token.fontSizeSM }}>{content}</Typography.Text>
  );

  const machineOptions = WORKFLOW_MACHINE_SIZES.map(size => {
    const spec = data?.machine_sizes?.[size];
    return {
      value: size,
      label: (
        <div style={{ padding: `${token.paddingXXS}px 0` }}>
          <div>{text[size]}</div>
          {spec && helpText(fill(text.machineSpec, { cpus: spec.cpus, memory: formatMemory(spec.memory), pids: spec.pids }))}
        </div>
      ),
    };
  });

  const renderBody = () => {
    if (!data) {
      if (loading) return <Flex justify="center" style={{ padding: token.paddingLG }}><Spin /></Flex>;
      if (loadFailure) {
        return (
          <Alert type="error" showIcon message={loadFailure.detail || text.loadFailed}
            action={<Button size="small" onClick={() => void load()}>{text.retry}</Button>} />
        );
      }
      return <Empty />;
    }
    return (
      <Flex vertical gap={token.marginMD}>
        <Typography.Text type="secondary">{text.intro}</Typography.Text>
        {loadFailure && (
          <Alert type="error" showIcon message={loadFailure.detail || text.loadFailed}
            action={<Button size="small" onClick={() => void load()}>{text.retry}</Button>} />
        )}
        {!canManage && <Alert type="info" showIcon message={text.readOnlyTitle} description={text.readOnly} />}
        {data.settings_error && (
          <Alert type="warning" showIcon message={text.settingsErrorTitle}
            description={<><div>{text.settingsErrorHelp}</div><Typography.Text code>{data.settings_error}</Typography.Text></>} />
        )}

        <WorkflowBackendSelect value={backend} onChange={setBackend}
          backends={data.execution_backends ?? []} disabled={!canManage || saving} />
        <Flex vertical gap={token.marginXS}>
          {sectionTitle(<RobotOutlined />, text.modelSection)}
          {helpText(text.modelHelp)}
          <WorkflowModelSelect value={model} onChange={setModel} text={text} disabled={!canManage || saving} />
        </Flex>

        <Flex vertical gap={token.marginXS}>
          {sectionTitle(<CloudServerOutlined />, text.machineSection)}
          {helpText(text.machineHelp)}
          <Segmented
            block
            value={machineSize}
            options={machineOptions}
            disabled={!canManage || saving}
            onChange={value => setMachineSize(value as WorkflowMachineSize)}
          />
        </Flex>

        <Flex vertical gap={token.marginXS}>
          {sectionTitle(<GlobalOutlined />, text.networkSection)}
          {helpText(text.networkHelp)}
          <Select
            mode="tags"
            value={hosts}
            onChange={(next: string[]) => setHosts(normalizeHosts(next))}
            tokenSeparators={[',', ' ', '\n']}
            maxCount={maxHosts > 0 ? maxHosts : undefined}
            options={[]}
            notFoundContent={null}
            placeholder={canManage ? text.networkPlaceholder : text.noNetwork}
            disabled={!canManage || saving}
            status={invalidHosts.length || tooManyHosts ? 'error' : undefined}
            tagRender={({ label, value, closable, onClose: closeTag }) => (
              <Tag
                color={isValidHost(String(value)) ? undefined : 'error'}
                closable={closable}
                onClose={closeTag}
                onMouseDown={event => { event.preventDefault(); event.stopPropagation(); }}
                style={{ marginInlineEnd: token.marginXXS }}
              >
                {label}
              </Tag>
            )}
            style={{ width: '100%' }}
          />
          <Flex justify="space-between" wrap="wrap" gap={token.marginXS}>
            {helpText(hosts.length ? fill(text.networkCount, { count: hosts.length, max: maxHosts }) : text.noNetwork)}
            {invalidHosts.length > 0 && (
              <Typography.Text type="danger" style={{ fontSize: token.fontSizeSM }}>
                {fill(text.invalidHosts, { hosts: invalidHosts.join(', ') })}
              </Typography.Text>
            )}
            {tooManyHosts && (
              <Typography.Text type="danger" style={{ fontSize: token.fontSizeSM }}>
                {fill(text.tooManyHosts, { max: maxHosts })}
              </Typography.Text>
            )}
          </Flex>
        </Flex>

        {saveProblem?.kind === 'conflict' && (
          <Alert type="warning" showIcon message={text.conflictTitle} description={text.conflict}
            action={<Button size="small" onClick={() => void load()} loading={loading}>{text.reload}</Button>} />
        )}
        {saveProblem?.kind === 'error' && <Alert type="error" showIcon message={saveProblem.message} />}
        {canManage && (
          <Flex align="center" gap={token.marginSM} wrap="wrap">
            <Button type="primary" icon={<SaveOutlined />} loading={saving} disabled={!canSave} onClick={() => void save()}>
              {text.save}
            </Button>
            {dirty && <Tag color="gold">{text.unsaved}</Tag>}
          </Flex>
        )}

        <Divider style={{ margin: 0 }} />
        <Flex vertical gap={token.marginXS}>
          {sectionTitle(<LockOutlined />, text.secretsSection)}
          <WorkflowSecretsSection
            workflowId={workflow.id}
            secrets={secrets}
            canManage={canManage}
            text={text}
            onSaved={saved => setSecrets(previous => {
              const others = previous.filter(secret => secret.name !== saved.name);
              return [...others, saved].sort((left, right) => left.name.localeCompare(right.name));
            })}
            onDeleted={name => setSecrets(previous => previous.filter(secret => secret.name !== name))}
          />
        </Flex>
      </Flex>
    );
  };

  return (
    <Drawer
      open
      size="large"
      onClose={onClose}
      title={fill(text.title, { name: workflow.name })}
      extra={data ? <Tag>{fill(text.revision, { revision: data.revision })}</Tag> : null}
    >
      {renderBody()}
    </Drawer>
  );
};

export default WorkflowSettingsDrawer;
