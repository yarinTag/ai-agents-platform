import React from 'react';
import { Alert, Card, Descriptions, Space } from 'antd';
import { useAuth } from '../../context/AuthContext';
import CapabilityGovernancePanel from '../org/CapabilityGovernancePanel';
import { useGovernanceText } from '../../i18n/governance';

export default function DepartmentAccessPage() {
  const { user, organization, departments, activeDepartmentId } = useAuth();
  const text = useGovernanceText();
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
    <CapabilityGovernancePanel />
  </Space>;
}
