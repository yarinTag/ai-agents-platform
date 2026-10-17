import React, { useState } from 'react';
import { Table, Button, Form, Input, InputNumber, Select, Tag, Progress, Typography, Card } from 'antd';
import { PlusOutlined, CloseOutlined } from '@ant-design/icons';
import { Department } from '../../types/auth';
import { useTranslation } from '../../i18n';

const { Text, Title } = Typography;

export interface DepartmentsBudgetTabProps {
  departments: Department[];
  loading: boolean;
  onCreateDepartment: (values: any) => Promise<void>;
  creating: boolean;
  onManageTeam: (departmentId: string) => void;
}

export const DepartmentsBudgetTab: React.FC<DepartmentsBudgetTabProps> = ({
  departments,
  loading,
  onCreateDepartment,
  creating,
  onManageTeam,
}) => {
  const { t } = useTranslation();
  const [showCreateDept, setShowCreateDept] = useState<boolean>(false);
  const [createDeptForm] = Form.useForm();

  const handleFinish = async (values: any) => {
    await onCreateDepartment(values);
    createDeptForm.resetFields();
    setShowCreateDept(false);
  };

  return (
    <div style={{ marginTop: 8 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
        <Text style={{ color: '#c9d1d9', fontSize: 13 }}>
          {t('departments.title')}
        </Text>
        <Button
          type="primary"
          size="small"
          icon={showCreateDept ? <CloseOutlined /> : <PlusOutlined />}
          onClick={() => setShowCreateDept(!showCreateDept)}
          style={{ background: '#10b981', borderColor: '#10b981', fontWeight: 600 }}
        >
          {showCreateDept ? t('departments.cancelNew') : t('departments.newDepartment')}
        </Button>
      </div>

      {showCreateDept && (
        <Card
          style={{
            background: '#0d1117',
            borderColor: '#30363d',
            marginBottom: 16,
            borderRadius: 8,
          }}
          bodyStyle={{ padding: '16px' }}
        >
          <Title level={5} style={{ color: '#f0f6fc', marginTop: 0, marginBottom: 12 }}>
            {t('departments.addTitle')}
          </Title>
          <Form
            form={createDeptForm}
            layout="vertical"
            onFinish={handleFinish}
            initialValues={{ monthly_budget_usd: 100, budget_action: 'HARD_STOP' }}
          >
            <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 1fr', gap: 12 }}>
              <Form.Item
                name="name"
                label={<Text style={{ color: '#c9d1d9', fontSize: 12 }}>{t('departments.nameLabel')}</Text>}
                rules={[{ required: true, message: t('departments.nameRequired') }]}
              >
                <Input
                  placeholder={t('departments.namePlaceholder')}
                  style={{ background: '#161b22', borderColor: '#30363d', color: '#f0f6fc' }}
                />
              </Form.Item>

              <Form.Item
                name="monthly_budget_usd"
                label={<Text style={{ color: '#c9d1d9', fontSize: 12 }}>{t('departments.budgetLabel')}</Text>}
                rules={[{ required: true, message: t('departments.budgetRequired') }]}
              >
                <InputNumber
                  min={1}
                  style={{ width: '100%', background: '#161b22', borderColor: '#30363d', color: '#f0f6fc' }}
                />
              </Form.Item>

              <Form.Item
                name="budget_action"
                label={<Text style={{ color: '#c9d1d9', fontSize: 12 }}>{t('departments.actionLabel')}</Text>}
              >
                <Select
                  options={[
                    { label: t('departments.hardStop'), value: 'HARD_STOP' },
                    { label: t('departments.alertOnly'), value: 'ALERT_ONLY' },
                  ]}
                  style={{ width: '100%' }}
                />
              </Form.Item>
            </div>

            <Form.Item
              name="description"
              label={<Text style={{ color: '#c9d1d9', fontSize: 12 }}>{t('departments.descLabel')}</Text>}
              style={{ marginBottom: 12 }}
            >
              <Input
                placeholder={t('departments.descPlaceholder')}
                style={{ background: '#161b22', borderColor: '#30363d', color: '#f0f6fc' }}
              />
            </Form.Item>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
              <Button size="small" onClick={() => setShowCreateDept(false)}>
                {t('common.cancel')}
              </Button>
              <Button
                type="primary"
                size="small"
                htmlType="submit"
                loading={creating}
                style={{ background: '#10b981', borderColor: '#10b981' }}
              >
                {t('departments.saveButton')}
              </Button>
            </div>
          </Form>
        </Card>
      )}

      <Table
        dataSource={departments}
        rowKey="id"
        loading={loading}
        pagination={false}
        size="small"
        columns={[
          {
            title: t('departments.tableColName'),
            dataIndex: 'name',
            key: 'name',
            render: (name: string, record: Department) => (
              <div>
                <div style={{ fontWeight: 600, color: '#f0f6fc' }}>{name}</div>
                {record.description && (
                  <div style={{ fontSize: 11, color: '#8b949e' }}>{record.description}</div>
                )}
              </div>
            ),
          },
          {
            title: t('departments.tableColBudget'),
            key: 'budget',
            render: (_: any, record: Department) => {
              const pct =
                record.monthly_budget_usd > 0
                  ? Math.min(100, Math.round((record.current_spend_usd / record.monthly_budget_usd) * 100))
                  : 0;
              const strokeColor = pct >= 90 ? '#ef4444' : pct >= 70 ? '#f59e0b' : '#10b981';
              return (
                <div style={{ minWidth: 160 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 2 }}>
                    <span style={{ color: '#f0f6fc' }}>${record.current_spend_usd.toFixed(2)}</span>
                    <span style={{ color: '#8b949e' }}>
                      / ${record.monthly_budget_usd.toFixed(2)} ({pct}%)
                    </span>
                  </div>
                  <Progress percent={pct} size="small" strokeColor={strokeColor} showInfo={false} />
                </div>
              );
            },
          },
          {
            title: t('departments.tableColAction'),
            dataIndex: 'budget_action',
            key: 'budget_action',
            width: 140,
            render: (action: string) => (
              <Tag color={action === 'HARD_STOP' ? 'error' : 'warning'}>{action}</Tag>
            ),
          },
          {
            title: t('departments.tableColActions'),
            key: 'actions',
            width: 130,
            render: (_: any, record: Department) => (
              <Button
                size="small"
                type="link"
                onClick={() => onManageTeam(record.id)}
                style={{ padding: 0, color: '#58a6ff' }}
              >
                {t('departments.manageTeam')}
              </Button>
            ),
          },
        ]}
      />
    </div>
  );
};

export default DepartmentsBudgetTab;
