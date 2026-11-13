import React from 'react';
import { Alert, Card, Descriptions, Space, Tabs } from 'antd';
import { useAuth } from '../../context/AuthContext';
import CapabilityGovernancePanel from '../org/CapabilityGovernancePanel';
import ExternalIdentitiesPanel from '../org/ExternalIdentitiesPanel';
import ChannelBindingsPanel from '../org/ChannelBindingsPanel';
import { useExternalIdentitiesText } from '../../i18n/externalIdentities';
import { useChannelBindingsText } from '../../i18n/channelBindings';
import { useGovernanceText } from '../../i18n/governance';

export default function DepartmentAccessPage() {
  const { user, organization, departments, activeDepartmentId } = useAuth();
  const text = useGovernanceText();
  const identitiesText = useExternalIdentitiesText();
  const channelsText = useChannelBindingsText();
  const visible = departments.filter(department => !activeDepartmentId || (department.id || department.department_id) === activeDepartmentId);
  return <Space direction="vertical" style={{ width: '100%' }}>
    <Alert type="info" showIcon message={text.organization} description={text.ceiling} />
    {visible.map(department => <Card key={department.id} title={department.name}>
      <Descriptions column={1} items={[
        { key: 'organization', label: text.organization, children: organization?.name },
        { key: 'account', label: text.currentRole, children: <bdi dir="ltr">{user?.role}</bdi> },
        { key: 'membership', label: text.membershipRole, children: <bdi dir="ltr">{department.department_role}</bdi> },
        { key: 'budget', label: text.budget, children: <bdi dir="ltr">${department.monthly_budget_usd}</bdi> },
      ]} />
    </Card>)}
    <Tabs items={[
      { key: 'capabilities', label: text.title, children: <CapabilityGovernancePanel /> },
      { key: 'channels', label: channelsText.title, children: <ChannelBindingsPanel /> },
      { key: 'identities', label: identitiesText.title, children: <ExternalIdentitiesPanel />, destroyOnHidden: true },
    ]} />
  </Space>;
}
