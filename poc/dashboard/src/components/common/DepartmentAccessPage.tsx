import React from 'react';
import { Alert, Card, Descriptions, Space } from 'antd';
import { useAuth } from '../../context/AuthContext';

export default function DepartmentAccessPage() {
  const { user, organization, departments, activeDepartmentId } = useAuth();
  const visible = departments.filter(department => !activeDepartmentId || (department.id || department.department_id) === activeDepartmentId);
  return <Space direction="vertical" style={{ width: '100%' }}>
    <Alert type="info" showIcon message="Organization access" description="Organization settings, credentials, membership changes and connector grants are managed by your organization administrator." />
    {visible.map(department => <Card key={department.id} title={department.name}>
      <Descriptions column={1} items={[
        { key: 'organization', label: 'Organization', children: organization?.name },
        { key: 'account', label: 'Account role', children: user?.role },
        { key: 'membership', label: 'Department role', children: department.department_role },
        { key: 'budget', label: 'Monthly budget', children: `$${department.monthly_budget_usd}` },
      ]} />
    </Card>)}
  </Space>;
}
