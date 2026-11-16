import { ChannelApprovalFields } from './ChannelApprovalFields';
import { useChannelApprovalsText } from '../../i18n/channelApprovals';
import { Checkbox, Form, InputNumber, Popconfirm, Select, Button } from 'antd';
import { useDagApprovalsText } from '../../i18n/dagApprovals';
import type { DagApprovalPolicy, WorkflowStep } from './workflowBuilderTypes';

const roles = ['OPERATOR', 'MANAGER', 'ORG_ADMIN'] as const;
const defaults: DagApprovalPolicy = { approver_roles: ['MANAGER', 'ORG_ADMIN'], timeout_seconds: 86400, quorum: 1 };

export function DagApprovalFields({ step, onChange, department }: {
  step: WorkflowStep;
  department?: string | null;
  onChange: (patch: Partial<WorkflowStep>) => void;
}) {
  const channelText = useChannelApprovalsText();
  const t = useDagApprovalsText();
  const policy = step.params?.dag_approval;
  const update = (patch: Partial<DagApprovalPolicy>) => {
    onChange({ params: { dag_approval: { ...defaults, ...policy, ...patch } } });
  };
  const canConvert = !step.mcp_servers?.length && !Object.keys(step.params ?? {}).length;
  return <Form.Item extra={!policy && !canConvert ? t.removeTools : undefined}>
    {!policy && <Checkbox checked={false} disabled={!canConvert}
      onChange={() => onChange({ params: { dag_approval: defaults } })}>{t.barrier}</Checkbox>}
    {policy && <Popconfirm title={channelText.remove} onConfirm={() => onChange({ params: {} })}>
      <Button danger type="text">{channelText.remove}</Button>
    </Popconfirm>}
    {policy && <>
      <Form.Item label={t.roles}>
        <Select mode="multiple" aria-label={t.roles} value={policy.approver_roles ?? defaults.approver_roles}
          options={roles.map(role => ({ value: role, label: role }))}
          onChange={approver_roles => { if (approver_roles.length) update({ approver_roles }); }} />
      </Form.Item>
      <Form.Item label={t.timeout}>
        <InputNumber aria-label={t.timeout} min={60} max={259200} precision={0} value={policy.timeout_seconds ?? defaults.timeout_seconds}
          onChange={timeout_seconds => { if (timeout_seconds && timeout_seconds >= 60 && timeout_seconds <= 259200) update({ timeout_seconds }); }} />
      </Form.Item>
      <Form.Item label={t.quorum}>
        <InputNumber aria-label={t.quorum} min={1} max={10} precision={0} value={policy.quorum ?? defaults.quorum}
          onChange={quorum => { if (quorum && quorum >= 1 && quorum <= 10) update({ quorum }); }} />
      </Form.Item>
      <ChannelApprovalFields key={department ?? ''} department={department} step={step} policy={policy} onChange={update} />
    </>}
  </Form.Item>;
}
