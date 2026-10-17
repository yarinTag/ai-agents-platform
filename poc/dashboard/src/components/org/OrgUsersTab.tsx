import React from 'react';
import { Table, Tag, Space, Typography } from 'antd';
import { UserOutlined } from '@ant-design/icons';
import { OrganizationUser } from '../../types/auth';
import { useTranslation } from '../../i18n';

const { Text } = Typography;

export interface OrgUsersTabProps {
  orgUsers: OrganizationUser[];
  loading: boolean;
  currentUserId?: string;
  organizationName?: string;
}

export const OrgUsersTab: React.FC<OrgUsersTabProps> = ({
  orgUsers,
  loading,
  currentUserId,
  organizationName,
}) => {
  const { t } = useTranslation();

  return (
    <div style={{ marginTop: 8 }}>
      <div style={{ marginBottom: 12 }}>
        <Text style={{ color: '#c9d1d9', fontSize: 13 }}>
          {t('org.allUsersTitle')} {organizationName || 'the organization'}
        </Text>
      </div>

      <Table
        dataSource={orgUsers}
        rowKey="id"
        loading={loading}
        pagination={{ pageSize: 8 }}
        size="small"
        columns={[
          {
            title: t('common.name'),
            dataIndex: 'full_name',
            key: 'full_name',
            render: (name: string, record: OrganizationUser) => (
              <Space>
                <UserOutlined style={{ color: '#8b949e' }} />
                <span style={{ fontWeight: 600, color: '#f0f6fc' }}>{name}</span>
                {record.id === currentUserId && <Tag color="gold" style={{ fontSize: 10 }}>{t('common.you')}</Tag>}
              </Space>
            ),
          },
          {
            title: 'Email',
            dataIndex: 'email',
            key: 'email',
            render: (email: string) => <span style={{ color: '#8b949e' }}>{email}</span>,
          },
          {
            title: t('common.role'),
            dataIndex: 'role',
            key: 'role',
            render: (role: string) => (
              <Tag color={role === 'ORG_ADMIN' ? 'gold' : 'blue'}>
                {role}
              </Tag>
            ),
          },
          {
            title: t('common.status'),
            dataIndex: 'status',
            key: 'status',
            render: (status: string) => (
              <Tag color={status === 'ACTIVE' ? 'success' : 'default'}>
                {status}
              </Tag>
            ),
          },
          {
            title: t('org.lastLogin'),
            dataIndex: 'last_login_at',
            key: 'last_login_at',
            render: (val: string) => (
              <span style={{ fontSize: 11, color: '#8b949e' }}>
                {val ? new Date(val).toLocaleString() : t('org.neverLoggedIn')}
              </span>
            ),
          },
        ]}
      />
    </div>
  );
};

export default OrgUsersTab;
