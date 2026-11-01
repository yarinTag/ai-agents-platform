import React, { useEffect, useRef, useState } from 'react';
import { Button, Card, Flex, Form, Input, Popconfirm, Radio, Table, Tag, Tooltip, Typography, message, theme } from 'antd';
import type { TableColumnsType } from 'antd';
import { DeleteOutlined, KeyOutlined, SwapOutlined } from '@ant-design/icons';
import { deleteWorkflowSecret, putWorkflowSecret } from '../../services/api';
import type { WorkflowSecretKind, WorkflowSecretSummary, WorkflowSecretWriteRequest } from '../../types/workflowSettings';
import { formatWorkflowSettingsText as fill, type WorkflowSettingsText } from '../../i18n/workflowSettings';
import {
  MAX_EXTERNAL_REF_LENGTH, MAX_SECRET_VALUE_BYTES, describeApiFailure, formatTimestamp, isSecretArn,
  secretNameProblem, secretValueBytes,
} from './workflowSettingsRules';

interface WorkflowSecretsSectionProps {
  workflowId: string;
  secrets: WorkflowSecretSummary[];
  canManage: boolean;
  text: WorkflowSettingsText;
  onSaved: (secret: WorkflowSecretSummary) => void;
  onDeleted: (name: string) => void;
}

interface SecretFormValues {
  name?: string;
  kind: WorkflowSecretKind;
  /** Write-only. Held only by the form store while typing and cleared after every submit. */
  value?: string;
  external_ref?: string;
}

const INITIAL_VALUES: SecretFormValues = { kind: 'encrypted' };

/** Secret metadata table plus a write-only add/replace form. Secret values are never displayed or retained. */
export const WorkflowSecretsSection: React.FC<WorkflowSecretsSectionProps> = ({
  workflowId, secrets, canManage, text, onSaved, onDeleted,
}) => {
  const { token } = theme.useToken();
  const [form] = Form.useForm<SecretFormValues>();
  const kind = Form.useWatch('kind', form) ?? 'encrypted';
  const typedName = (Form.useWatch('name', form) ?? '').trim();
  const [replacing, setReplacing] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState<string[]>([]);
  // Writes are independent (several rows can be deleted at once), so only unmount suppresses updates.
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);

  const clearValue = () => form.setFieldsValue({ value: undefined });

  const resetForm = () => {
    form.resetFields();
    setReplacing(null);
  };

  const startReplace = (secret: WorkflowSecretSummary) => {
    setReplacing(secret.name);
    form.setFieldsValue({
      name: secret.name,
      kind: secret.kind,
      value: undefined,
      external_ref: secret.kind === 'external' ? secret.external_ref ?? undefined : undefined,
    });
  };

  /** Called by Form onFinish, i.e. only after every field rule passed. */
  const submit = async (values: SecretFormValues) => {
    if (saving) return;
    const name = (values.name ?? '').trim();
    const body: WorkflowSecretWriteRequest = values.kind === 'external'
      ? { external_ref: (values.external_ref ?? '').trim() }
      : { value: values.value ?? '' };
    clearValue(); // The value leaves the form as soon as it is submitted, whatever the outcome.
    setSaving(true);
    try {
      const response = await putWorkflowSecret(workflowId, name, body);
      if (!mounted.current) return;
      onSaved(response.data);
      message.success(fill(text.secretSaved, { name: response.data.name }));
      resetForm();
    } catch (cause: unknown) {
      if (!mounted.current) return;
      const failure = describeApiFailure(cause);
      if (failure.status === 503) message.error(fill(text.notConfigured, { detail: failure.detail || text.secretFailed }));
      else message.error(failure.detail || text.secretFailed);
    } finally {
      if (mounted.current) setSaving(false);
    }
  };

  const remove = async (name: string) => {
    setDeleting(previous => [...previous, name]);
    try {
      await deleteWorkflowSecret(workflowId, name);
      if (!mounted.current) return;
      onDeleted(name);
      if (replacing === name) resetForm();
      message.success(fill(text.deleted, { name }));
    } catch (cause: unknown) {
      if (mounted.current) message.error(describeApiFailure(cause).detail || text.deleteFailed);
    } finally {
      if (mounted.current) setDeleting(previous => previous.filter(item => item !== name));
    }
  };

  const columns: TableColumnsType<WorkflowSecretSummary> = [
    {
      title: text.colName,
      dataIndex: 'name',
      key: 'name',
      render: (name: string) => <Typography.Text code>{name}</Typography.Text>,
    },
    {
      title: text.colKind,
      dataIndex: 'kind',
      key: 'kind',
      render: (secretKind: WorkflowSecretKind) => (
        <Tag color={secretKind === 'external' ? 'purple' : 'blue'}>
          {secretKind === 'external' ? text.kindExternal : text.kindEncrypted}
        </Tag>
      ),
    },
    {
      title: text.colSource,
      key: 'source',
      render: (_: unknown, secret: WorkflowSecretSummary) => secret.kind === 'external' && secret.external_ref
        ? <Typography.Text ellipsis={{ tooltip: secret.external_ref }} style={{ maxWidth: 220 }}>{secret.external_ref}</Typography.Text>
        : <Typography.Text type="secondary">{text.hiddenValue}</Typography.Text>,
    },
    {
      title: text.colUpdated,
      dataIndex: 'updated_at',
      key: 'updated_at',
      render: (updatedAt: string, secret: WorkflowSecretSummary) => (
        <Tooltip title={secret.created_by || undefined}>
          <Typography.Text type="secondary">{formatTimestamp(updatedAt)}</Typography.Text>
        </Tooltip>
      ),
    },
    ...(canManage ? [{
      title: text.colActions,
      key: 'actions',
      render: (_: unknown, secret: WorkflowSecretSummary) => (
        <div style={{ display: 'flex', gap: '8px' }}>
          <Button size="small" icon={<SwapOutlined />} onClick={() => startReplace(secret)}>{text.replace}</Button>
          <Popconfirm
            title={fill(text.deleteConfirm, { name: secret.name })}
            description={text.deleteHelp}
            okText={text.delete}
            cancelText={text.cancel}
            okButtonProps={{ danger: true }}
            onConfirm={() => remove(secret.name)}
          >
            <Button size="small" danger icon={<DeleteOutlined />} loading={deleting.includes(secret.name)}
              aria-label={text.delete} />
          </Popconfirm>
        </div>
      ),
    }] : []),
  ];

  const nameExists = !replacing && Boolean(typedName) && secrets.some(secret => secret.name === typedName);

  return (
    <Flex vertical gap={token.marginSM}>
      <Typography.Text type="secondary">{text.secretsHelp}</Typography.Text>
      <Table<WorkflowSecretSummary>
        size="small"
        rowKey="name"
        dataSource={secrets}
        columns={columns}
        pagination={false}
        locale={{ emptyText: text.noSecrets }}
      />
      {canManage && (
        <Card size="small" title={<span><KeyOutlined /> {replacing ? fill(text.replaceTitle, { name: replacing }) : text.addTitle}</span>}
          extra={replacing ? <Button size="small" onClick={resetForm}>{text.cancel}</Button> : null}>
          <Form<SecretFormValues> form={form} layout="vertical" initialValues={INITIAL_VALUES} autoComplete="off"
            onFinish={values => { void submit(values); }}>
            <Form.Item
              name="name"
              label={text.nameLabel}
              normalize={(input: string | undefined) => (input ?? '').toUpperCase()}
              extra={nameExists ? text.nameExists : undefined}
              rules={[{
                validator: async (_rule, input: string | undefined) => {
                  const candidate = (input ?? '').trim();
                  if (!candidate) throw new Error(text.nameRequired);
                  const problem = secretNameProblem(candidate);
                  if (problem === 'format') throw new Error(text.nameInvalid);
                  if (problem === 'reserved') throw new Error(text.nameReserved);
                },
              }]}
            >
              <Input placeholder={text.namePlaceholder} disabled={Boolean(replacing)} maxLength={64} autoComplete="off"
                spellCheck={false} />
            </Form.Item>
            <Form.Item name="kind" label={text.typeLabel}>
              <Radio.Group
                optionType="button"
                options={[
                  { value: 'encrypted', label: text.typeEncrypted },
                  { value: 'external', label: text.typeExternal },
                ]}
              />
            </Form.Item>
            {kind === 'encrypted' ? (
              <Form.Item
                key="value"
                name="value"
                preserve={false}
                label={text.valueLabel}
                extra={text.valueHelp}
                rules={[{
                  validator: async (_rule, input: string | undefined) => {
                    if (!input) throw new Error(text.valueRequired);
                    if (secretValueBytes(input) > MAX_SECRET_VALUE_BYTES) {
                      throw new Error(fill(text.valueTooLong, { max: MAX_SECRET_VALUE_BYTES }));
                    }
                  },
                }]}
              >
                {/* new-password + ignore hints keep browsers/password managers from autofilling or saving it. */}
                <Input.Password placeholder={text.valuePlaceholder} autoComplete="new-password" visibilityToggle={false}
                  spellCheck={false} data-lpignore="true" data-1p-ignore="true" data-bwignore="true" />
              </Form.Item>
            ) : (
              <Form.Item
                key="external_ref"
                name="external_ref"
                preserve={false}
                label={text.arnLabel}
                extra={text.arnHelp}
                rules={[{
                  validator: async (_rule, input: string | undefined) => {
                    if (!isSecretArn((input ?? '').trim())) throw new Error(text.arnInvalid);
                  },
                }]}
              >
                <Input placeholder={text.arnPlaceholder} maxLength={MAX_EXTERNAL_REF_LENGTH} autoComplete="off"
                  spellCheck={false} />
              </Form.Item>
            )}
            <Button type="primary" htmlType="submit" loading={saving} icon={<KeyOutlined />}>{text.saveSecret}</Button>
          </Form>
        </Card>
      )}
    </Flex>
  );
};
