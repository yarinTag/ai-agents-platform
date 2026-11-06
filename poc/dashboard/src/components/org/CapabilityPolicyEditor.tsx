import React, { useState } from 'react';
import { Alert, Button, Drawer, Form, Select, Space, Typography } from 'antd';
import type { CapabilityDescriptor, PolicyDocument, PolicyEffect, PolicyRecord, PolicyRule } from '../../types/governance';
import type { GovernanceText } from '../../i18n/governance';
import CapabilityPolicyRules from './CapabilityPolicyRules';

export default function CapabilityPolicyEditor({ record, isAdmin, capabilities, text, onClose, onSave }: {
  record: PolicyRecord; isAdmin: boolean; capabilities: CapabilityDescriptor[]; text: GovernanceText;
  onClose: () => void; onSave: (document: PolicyDocument) => Promise<'saved' | 'conflict' | 'unavailable' | 'error'>;
}) {
  const [draft, setDraft] = useState<PolicyDocument>(() => structuredClone(record.document));
  const [selected, setSelected] = useState<string>();
  const [resources, setResources] = useState<string[]>([]);
  const [effect, setEffect] = useState<PolicyEffect>('deny');
  const [editing, setEditing] = useState<PolicyRule>();
  const [reviewing, setReviewing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<'conflict' | 'unavailable' | 'error'>();
  const options = record.resource_options || [];
  const optionKey = (index: number) => String(index);
  const option = selected === undefined ? undefined : options[Number(selected)];
  const originalIds = new Set(record.document.rules.map(rule => rule.id));
  const editable = (rule: PolicyRule) => isAdmin || !originalIds.has(rule.id);
  const changed = JSON.stringify(draft) !== JSON.stringify(record.document);
  const locked = saving || error === 'conflict' || error === 'unavailable';
  const reset = () => { setSelected(undefined); setResources([]); setEffect('deny'); setEditing(undefined); };
  const apply = () => {
    if (!option || !resources.length || !resources.every(id => option.resource_ids.includes(id))) return;
    const rule: PolicyRule = { user_ids: [], agent_ids: [], workflow_ids: [], branches: [], not_before: null, expires_at: null,
      ...editing, id: editing?.id || `rule_${crypto.randomUUID().replace(/-/g, '')}`, capability_version: 1,
      connector_id: option.connector_id, capability_id: option.capability_id, resource_type: option.resource_type,
      resource_ids: resources, effect };
    setDraft(previous => ({ ...previous, rules: editing ? previous.rules.map(old => old.id === editing.id ? rule : old) : [...previous.rules, rule] }));
    setError(undefined); reset();
  };
  const edit = (rule: PolicyRule) => {
    const index = options.findIndex(value => value.connector_id === rule.connector_id && value.capability_id === rule.capability_id);
    setEditing(rule); setSelected(index < 0 ? undefined : optionKey(index)); setResources(rule.resource_ids); setEffect(rule.effect);
  };
  const save = async () => {
    if (locked || !changed) return;
    setSaving(true); setError(undefined);
    try {
      const result = await onSave(draft);
      if (result !== 'saved') setError(result);
    } catch { setError('error'); }
    finally { setSaving(false); }
  };
  const elevated = draft.rules.some(rule => rule.effect === 'allow' && capabilities.some(cap => cap.id === rule.capability_id && cap.effect !== 'read')
    && JSON.stringify(rule) !== JSON.stringify(record.document.rules.find(old => old.id === rule.id)));
  return <Drawer open title={<Space wrap><span>{text.editTitle} · {record.scope_type === 'organization' ? text.organizationPolicy : text.departmentPolicy}</span>
    <bdi dir="ltr">{record.scope_id}</bdi></Space>} width="min(1050px, 100vw)" onClose={() => { if (!saving) onClose(); }}
    maskClosable={!saving} closable={!saving} extra={<TagRevision text={text} revision={record.revision} />}>
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      <Alert type="info" showIcon message={text.ceiling} description={isAdmin ? text.conditional : text.managerHint} />
      {error && <Alert role="alert" type="error" showIcon message={error === 'conflict' ? text.conflict : error === 'unavailable' ? text.unavailable : text.saveError} />}
      {reviewing ? <>
        <Alert type="info" message={text.reviewHint} />
        {elevated && <Alert type="warning" showIcon message={text.writeWarning} />}
        <Typography.Title level={5}>{text.before} · {record.document.default === 'inherit' ? text.inherit : text.defaultDeny}</Typography.Title>
        <CapabilityPolicyRules rules={record.document.rules} text={text} />
        <Typography.Title level={5}>{text.after} · {draft.default === 'inherit' ? text.inherit : text.defaultDeny}</Typography.Title>
        <CapabilityPolicyRules rules={draft.rules} text={text} />
        <Space><Button disabled={locked} onClick={() => setReviewing(false)}>{text.back}</Button>
          <Button type="primary" loading={saving} disabled={locked || !changed} onClick={() => void save()}>{text.confirm}</Button></Space>
      </> : <>
        <Form layout="vertical" disabled={locked}>
          <Form.Item label={text.defaultPolicy}>
            <Select aria-label={text.defaultPolicy} disabled={!isAdmin || locked} value={draft.default}
              options={[{ value: 'inherit', label: text.inherit }, { value: 'deny', label: text.defaultDeny }]}
              onChange={value => setDraft(previous => ({ ...previous, default: value }))} />
          </Form.Item>
        </Form>
        <CapabilityPolicyRules rules={draft.rules} text={text} editable={rule => !locked && editable(rule)} onEdit={edit}
          onRemove={rule => setDraft(previous => ({ ...previous, rules: previous.rules.filter(old => old.id !== rule.id) }))} />
        {!options.length ? <Alert type="info" message={text.noOptions} /> : <Form layout="vertical" disabled={locked}>
          <Typography.Title level={5}>{editing ? text.change : text.add}</Typography.Title>
          <Form.Item label={text.capability} required>
            <Select showSearch aria-label={text.capability} value={selected} optionFilterProp="label"
              options={options.map((value, index) => ({ value: optionKey(index), label: `${value.connector_name} · ${value.capability_id}` }))}
              onChange={value => { setSelected(value); setResources([]); }} />
          </Form.Item>
          <Form.Item label={text.resource} required>
            <Select mode="multiple" aria-label={text.resource} value={resources} disabled={!option || locked}
              options={(option?.resource_ids || []).map(id => ({ value: id, label: <bdi dir="ltr">{id}</bdi> }))} onChange={setResources} />
          </Form.Item>
          <Form.Item label={text.effect}>
            <Select aria-label={text.effect} value={effect} onChange={setEffect}
              options={(isAdmin ? ['allow', 'deny', 'require_approval'] as const : ['deny', 'require_approval'] as const).map(value => ({ value, label: text[value] }))} />
          </Form.Item>
          <Typography.Paragraph type="secondary">{text.preserveConstraints}</Typography.Paragraph>
          <Space><Button disabled={locked || !option || !resources.length || draft.rules.length >= 200 && !editing} onClick={apply}>{text.addRule}</Button>
            {(editing || selected !== undefined) && <Button disabled={locked} onClick={reset}>{text.cancel}</Button>}</Space>
        </Form>}
        <Button type="primary" disabled={!changed || locked || !!editing || !!selected} onClick={() => setReviewing(true)}>{text.review}</Button>
      </>}
    </Space>
  </Drawer>;
}

function TagRevision({ text, revision }: { text: GovernanceText; revision: number }) {
  return <Typography.Text>{text.revision} {revision}</Typography.Text>;
}
