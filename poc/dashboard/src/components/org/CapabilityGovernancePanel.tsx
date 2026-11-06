import React, { useEffect, useRef, useState } from 'react';
import { Alert, Button, Card, Collapse, ConfigProvider, Descriptions, Empty, Space, Spin, Table, Tabs, Typography } from 'antd';
import axios from 'axios';
import { useAuth } from '../../context/AuthContext';
import { usePermissions } from '../../hooks/usePermissions';
import { useGovernanceText } from '../../i18n/governance';
import { useTranslation } from '../../i18n';
import { getCapabilityPolicy, getCapabilityPolicyHistory, getGovernanceCapabilities, getGovernanceCatalog, updateCapabilityPolicy } from '../../services/governanceApi';
import type { CapabilityCatalog, CapabilityDescriptor, PolicyDocument, PolicyRecord } from '../../types/governance';
import CapabilityAccessTable from './CapabilityAccessTable';
import CapabilityPolicyEditor from './CapabilityPolicyEditor';
import CapabilityPolicyRules from './CapabilityPolicyRules';

export default function CapabilityGovernancePanel() {
  const { organization, user, activeDepartmentId, departments } = useAuth();
  const permissions = usePermissions();
  const text = useGovernanceText();
  const { dir } = useTranslation();
  const department = departments.find(value => (value.id || value.department_id) === activeDepartmentId);
  if (!activeDepartmentId || !permissions.canRead || !organization || !user) {
    return <Alert type="info" showIcon message={text.title} description={text.selectDepartment} />;
  }
  // Remount clears drafts, errors and pending previews synchronously on scope/role change.
  const scope = JSON.stringify([organization.id, user.id, user.role, activeDepartmentId, permissions.rank]);
  return <ConfigProvider direction={dir}><ScopedGovernance key={scope} departmentId={activeDepartmentId} departmentName={department?.name || activeDepartmentId}
    organizationName={organization.name} role={permissions.isAdmin ? 'ORG_ADMIN' : permissions.rank === 3 ? 'MANAGER' : permissions.rank === 2 ? 'OPERATOR' : 'MEMBER'}
    isAdmin={permissions.isAdmin} canManage={permissions.canManage} /></ConfigProvider>;
}

function ScopedGovernance({ departmentId, departmentName, organizationName, role, isAdmin, canManage }: {
  departmentId: string; departmentName: string; organizationName: string; role: string; isAdmin: boolean; canManage: boolean;
}) {
  const text = useGovernanceText();
  const [tab, setTab] = useState('access');
  const [reload, setReload] = useState(0);
  const [catalog, setCatalog] = useState<CapabilityCatalog>();
  const [capabilities, setCapabilities] = useState<CapabilityDescriptor[]>([]);
  const [policy, setPolicy] = useState<PolicyRecord>();
  const [history, setHistory] = useState<PolicyRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [unavailable, setUnavailable] = useState(false);
  const [editor, setEditor] = useState<PolicyRecord>();
  const [saved, setSaved] = useState(false);
  const controller = useRef<AbortController | undefined>(undefined);
  const current = useRef(0);

  useEffect(() => {
    const request = new AbortController();
    controller.current = request;
    const generation = ++current.current;
    setLoading(true); setLoadError(false); setUnavailable(false); setCatalog(undefined); setPolicy(undefined); setHistory([]); setCapabilities([]);
    const target = tab === 'organization' ? null : departmentId;
    const load = async () => {
      try {
        // Members never request managerial policies, history, users or connector settings.
        const results = await Promise.allSettled([
          getGovernanceCatalog(departmentId, request.signal), getGovernanceCapabilities(request.signal),
          tab !== 'access' && canManage ? getCapabilityPolicy(target, request.signal) : undefined,
          tab === 'department' && canManage ? getCapabilityPolicyHistory(departmentId, request.signal) : undefined,
        ]);
        if (request.signal.aborted || current.current !== generation) return;
        const rejected = results.filter(result => result.status === 'rejected');
        if (rejected.some(result => result.status === 'rejected' && axios.isAxiosError(result.reason)
            && [401, 403, 404].includes(result.reason.response?.status || 0))) {
          setUnavailable(true); return;
        }
        const [directory, inventory, document, revisions] = results;
        if (directory.status === 'fulfilled') setCatalog(directory.value.data);
        if (inventory.status === 'fulfilled') setCapabilities(inventory.value.data.capabilities);
        if (document.status === 'fulfilled') setPolicy(document.value?.data);
        if (revisions.status === 'fulfilled') setHistory(revisions.value?.data.revisions || []);
        setLoadError(rejected.length > 0);
      } catch (error) {
        if (request.signal.aborted || current.current !== generation) return;
        setLoadError(true);
        if (axios.isAxiosError(error) && [401, 403, 404].includes(error.response?.status || 0)) setUnavailable(true);
      } finally { if (!request.signal.aborted && current.current === generation) setLoading(false); }
    };
    void load();
    return () => { request.abort(); ++current.current; };
  }, [departmentId, canManage, tab, reload]);

  const save = async (document: PolicyDocument): Promise<'saved' | 'conflict' | 'unavailable' | 'error'> => {
    const selected = editor;
    const request = controller.current;
    const generation = current.current;
    if (!selected || !canManage || !request || request.signal.aborted) return 'unavailable';
    try {
      await updateCapabilityPolicy(selected.scope_type === 'organization' ? null : departmentId,
        document, selected.revision, request.signal);
      if (request.signal.aborted || current.current !== generation) return 'unavailable';
      setEditor(undefined); setSaved(true); setLoading(true); setReload(value => value + 1);
      return 'saved';
    } catch (error) {
      if (request.signal.aborted || current.current !== generation) return 'unavailable';
      if (axios.isAxiosError(error)) {
        if (error.response?.status === 409) { setPolicy(undefined); return 'conflict'; }
        if ([401, 403, 404].includes(error.response?.status || 0)) {
          // Server-side revocation clears old resources and edit authority immediately.
          setEditor(undefined); setPolicy(undefined); setCatalog(undefined); setHistory([]); setUnavailable(true);
          return 'unavailable';
        }
      }
      return 'error';
    }
  };
  const refresh = () => { setEditor(undefined); setSaved(false); setReload(value => value + 1); };
  const policyView = policy && <Space direction="vertical" style={{ width: '100%' }} size="middle">
    <Descriptions size="small" items={[
      { key: 'revision', label: text.revision, children: policy.revision },
      { key: 'default', label: text.defaultPolicy, children: policy.document.default === 'inherit' ? text.inherit : text.defaultDeny },
      { key: 'actor', label: text.actor, children: <bdi dir="ltr">{policy.updated_by || '—'}</bdi> },
    ]} />
    <Button onClick={() => { setSaved(false); setEditor(policy); }}>{text.edit}</Button>
    <CapabilityPolicyRules rules={policy.document.rules} text={text} />
    {tab === 'department' && <Collapse items={[{ key: 'history', label: text.history, children: <Table rowKey="revision"
      size="small" pagination={{ pageSize: 5 }} dataSource={history} scroll={{ x: 450 }}
      locale={{ emptyText: text.noHistory }} expandable={{ expandedRowRender: row => <CapabilityPolicyRules rules={row.document.rules} text={text} /> }}
      columns={[{ title: text.revision, dataIndex: 'revision' }, { title: text.actor, dataIndex: 'updated_by', render: value => <bdi dir="ltr">{value}</bdi> },
        { title: text.updated, dataIndex: 'updated_at', render: value => <bdi dir="ltr">{value}</bdi> }]} /> }]} />}
  </Space>;
  return <Card title={text.title} extra={<Button disabled={loading} onClick={refresh}>{text.refresh}</Button>}>
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      <Space wrap><Typography.Text>{text.organization}: {organizationName}</Typography.Text>
        <Typography.Text>{text.department}: {departmentName}</Typography.Text><Typography.Text>{text.role}: <bdi dir="ltr">{role}</bdi></Typography.Text></Space>
      <Alert showIcon type="info" message={canManage ? isAdmin ? text.ceiling : text.managerHint : text.readOnly} />
      {saved && <Alert role="status" type="success" showIcon message={text.saved} />}
      {loadError && !unavailable && <Alert role="alert" type="warning" showIcon message={text.loadError} action={<Button onClick={refresh}>{text.refresh}</Button>} />}
      {unavailable ? <Alert role="alert" type="warning" showIcon message={text.unavailable} />
        : <Tabs activeKey={tab} onChange={value => { setEditor(undefined); setPolicy(undefined); setHistory([]); setLoading(true); setSaved(false); setTab(value); }} items={[
          { key: 'access', label: text.available, children: loading ? <Spin aria-label={text.loading} /> : catalog
            ? <CapabilityAccessTable catalog={catalog} capabilities={capabilities} text={text} /> : <Empty description={loadError ? text.loadError : text.empty} /> },
          ...(canManage ? [{ key: 'department', label: text.departmentPolicy, children: loading ? <Spin aria-label={text.loading} /> : policyView || <Alert type="warning" message={text.policyError} /> }] : []),
          ...(isAdmin ? [{ key: 'organization', label: text.organizationPolicy, children: loading ? <Spin aria-label={text.loading} /> : policyView || <Alert type="warning" message={text.policyError} /> }] : []),
        ]} />}
      {editor && <CapabilityPolicyEditor record={editor} isAdmin={isAdmin} capabilities={capabilities} text={text}
        onClose={() => setEditor(undefined)} onSave={save} />}
    </Space>
  </Card>;
}
