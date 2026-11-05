import React from 'react';
import { Alert, Select, Space, Typography } from 'antd';
import type { ExecutionBackend, ExecutionBackendDescriptor } from '../../types/workflowSettings';
import { useWorkflowSettingsText } from '../../i18n/workflowSettings';

interface Props {
  value: ExecutionBackend;
  onChange: (value: ExecutionBackend) => void;
  backends: ExecutionBackendDescriptor[];
  disabled: boolean;
}

/** Capability inventory comes from the server, never from browser binary detection. */
export const WorkflowBackendSelect: React.FC<Props> = ({ value, onChange, backends, disabled }) => {
  const text = useWorkflowSettingsText();
  const selected = backends.find(backend => backend.id === value);
  const options = backends.length ? backends.map(backend => ({
    value: backend.id,
    label: backend.name + (!backend.implemented ? ` · ${text.backendPending}` : backend.configured === false ? ` · ${text.backendSetupNeeded}` : ''),
    disabled: !backend.implemented || backend.configured === false,
  })) : [{ value: 'direct_api', label: 'Direct API', disabled: false }];
  if (!options.some(option => option.value === value)) {
    options.push({ value, label: `${value} · ${text.unlistedModel}`, disabled: true });
  }
  return <Space direction="vertical" style={{ width: '100%' }}>
    <Typography.Title level={5} style={{ margin: 0 }}>{text.backendSection}</Typography.Title>
    <Typography.Text type="secondary">{text.backendHelp}</Typography.Text>
    <Select<ExecutionBackend> value={value} onChange={onChange} options={options}
      disabled={disabled} style={{ width: '100%' }} />
    {value !== 'direct_api' && (!selected?.implemented || selected.configured === false) && <Alert type="warning" showIcon
      message={text.backendBlocked} description={text.backendBlockedHelp} />}
  </Space>;
};
