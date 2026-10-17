import React from 'react';
import { Table, Button, Form, Select, Tag, Space, Typography, Card, Alert, Popconfirm, message } from 'antd';
import { MailOutlined, CopyOutlined, DeleteOutlined, UserOutlined } from '@ant-design/icons';
import { Department, DepartmentMember, InvitationRecord } from '../../types/auth';
import { useTranslation } from '../../i18n';

const { Text, Title } = Typography;

export interface TeamInvitationsTabProps {
  departments: Department[];
  selectedDeptId: string | null;
  onSelectDeptId: (id: string) => void;
  deptMembers: DepartmentMember[];
  loadingMembers: boolean;
  onInviteMembers: (values: any) => Promise<void>;
  inviting: boolean;
  recentInvitations: InvitationRecord[];
  onRemoveMember: (userId: string) => Promise<void>;
  currentUserId?: string;
}

export const TeamInvitationsTab: React.FC<TeamInvitationsTabProps> = ({
  departments,
  selectedDeptId,
  onSelectDeptId,
  deptMembers,
  loadingMembers,
  onInviteMembers,
  inviting,
  recentInvitations,
  onRemoveMember,
  currentUserId,
}) => {
  const { t } = useTranslation();
  const [inviteForm] = Form.useForm();

  const handleFinish = async (values: any) => {
    await onInviteMembers(values);
    inviteForm.resetFields();
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    message.success(t('org.tokenCopied'));
  };

  return (
    <div style={{ marginTop: 8 }}>
      {/* Department selector */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
        <Text style={{ color: '#c9d1d9', fontSize: 13, whiteSpace: 'nowrap' }}>
          {t('departments.selectDeptToManage')}
        </Text>
        <Select
          value={selectedDeptId}
          onChange={(val) => onSelectDeptId(val)}
          style={{ minWidth: 280 }}
          options={departments.map((d) => ({
            label: `${d.name} ($${d.current_spend_usd.toFixed(1)} / $${d.monthly_budget_usd.toFixed(1)})`,
            value: d.id,
          }))}
          placeholder={t('departments.selectDepartment')}
        />
      </div>

      {/* Invite Members Box */}
      <Card
        style={{
          background: '#0d1117',
          borderColor: '#30363d',
          marginBottom: 16,
          borderRadius: 8,
        }}
        bodyStyle={{ padding: '14px 16px' }}
      >
        <Title level={5} style={{ color: '#f0f6fc', margin: '0 0 10px 0', fontSize: 13 }}>
          <MailOutlined style={{ marginRight: 6, color: '#10b981' }} />
          {t('departments.inviteNewMembersTitle')}
        </Title>
        <Form form={inviteForm} layout="vertical" onFinish={handleFinish} initialValues={{ role: 'OPERATOR' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '3fr 1fr auto', gap: 10, alignItems: 'start' }}>
            <Form.Item
              name="emails"
              rules={[{ required: true, message: t('org.inviteEmailsRequired') }]}
              style={{ margin: 0 }}
            >
              <Select
                mode="tags"
                placeholder={t('org.inviteEmailsPlaceholder')}
                tokenSeparators={[',', ' ']}
                style={{ width: '100%' }}
              />
            </Form.Item>

            <Form.Item name="role" style={{ margin: 0 }}>
              <Select
                options={[
                  { label: 'Manager (MANAGER)', value: 'MANAGER' },
                  { label: 'Operator (OPERATOR)', value: 'OPERATOR' },
                  { label: 'Member (MEMBER)', value: 'MEMBER' },
                ]}
              />
            </Form.Item>

            <Button
              type="primary"
              htmlType="submit"
              loading={inviting}
              style={{ background: '#10b981', borderColor: '#10b981', fontWeight: 600 }}
            >
              {t('org.generateInvitesButton')}
            </Button>
          </div>
        </Form>

        {/* Recently generated invitations */}
        {recentInvitations.length > 0 && (
          <div style={{ marginTop: 14 }}>
            <Alert
              type="success"
              message={t('org.inviteIssuedAlert')}
              style={{ background: 'rgba(16, 185, 129, 0.1)', borderColor: 'rgba(16, 185, 129, 0.3)', marginBottom: 8 }}
            />
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {recentInvitations.map((inv) => (
                <div
                  key={inv.id || inv.token}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    background: '#161b22',
                    padding: '6px 12px',
                    borderRadius: 6,
                    border: '1px solid #30363d',
                  }}
                >
                  <div>
                    <Text style={{ color: '#f0f6fc', fontWeight: 600, marginRight: 8 }}>{inv.email}</Text>
                    <Tag color="cyan" style={{ fontSize: 10 }}>{inv.role}</Tag>
                    <code style={{ fontSize: 11, color: '#34d399', background: '#0a0d12', padding: '2px 6px', borderRadius: 4 }}>
                      {inv.token}
                    </code>
                  </div>
                  <Button
                    size="small"
                    icon={<CopyOutlined />}
                    onClick={() => copyToClipboard(inv.token)}
                    style={{ background: '#21262d', borderColor: '#30363d', color: '#c9d1d9' }}
                  >
                    {t('org.copyToken')}
                  </Button>
                </div>
              ))}
            </div>
          </div>
        )}
      </Card>

      {/* Department Members Table */}
      <Table
        dataSource={deptMembers}
        rowKey="id"
        loading={loadingMembers}
        pagination={false}
        size="small"
        columns={[
          {
            title: t('common.name'),
            dataIndex: 'full_name',
            key: 'full_name',
            render: (name: string, record: DepartmentMember) => (
              <Space>
                <UserOutlined style={{ color: '#8b949e' }} />
                <span style={{ fontWeight: 600, color: '#f0f6fc' }}>{name}</span>
                {record.user_id === currentUserId && <Tag color="gold" style={{ fontSize: 10 }}>{t('common.you')}</Tag>}
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
            render: (role: string) => {
              const colorMap: Record<string, string> = {
                MANAGER: 'volcano',
                OPERATOR: 'blue',
                MEMBER: 'default',
              };
              return <Tag color={colorMap[role] || 'default'}>{role}</Tag>;
            },
          },
          {
            title: t('org.joinedDate'),
            dataIndex: 'joined_at',
            key: 'joined_at',
            render: (val: string) => (
              <span style={{ fontSize: 11, color: '#8b949e' }}>
                {val ? new Date(val).toLocaleDateString() : '—'}
              </span>
            ),
          },
          {
            title: t('common.actions'),
            key: 'actions',
            width: 90,
            render: (_: any, record: DepartmentMember) => (
              <Popconfirm
                title={t('org.removeMemberConfirm')}
                onConfirm={() => onRemoveMember(record.user_id)}
                okText={t('common.remove')}
                cancelText={t('common.cancel')}
              >
                <Button
                  size="small"
                  type="text"
                  danger
                  icon={<DeleteOutlined />}
                  disabled={record.user_id === currentUserId}
                />
              </Popconfirm>
            ),
          },
        ]}
      />
    </div>
  );
};

export default TeamInvitationsTab;
