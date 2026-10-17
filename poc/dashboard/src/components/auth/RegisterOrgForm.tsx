import React from 'react';
import { Form, Input, Button, Typography, Space, Divider } from 'antd';
import {
  BankOutlined,
  GlobalOutlined,
  UserOutlined,
  MailOutlined,
  LockOutlined,
} from '@ant-design/icons';
import { useTranslation } from '../../i18n';

const { Text } = Typography;

export interface RegisterOrgFormProps {
  onSubmit: (values: any) => Promise<void>;
  loading: boolean;
}

export const RegisterOrgForm: React.FC<RegisterOrgFormProps> = ({ onSubmit, loading }) => {
  const { t } = useTranslation();
  const [form] = Form.useForm();

  // Helper to slugify organization name automatically
  const handleOrgNameChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    const currentSlug = form.getFieldValue('slug');
    const autoSlug = val
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '');

    // Only auto-update if slug hasn't been manually set or matches previous auto-slug
    if (!currentSlug || currentSlug === autoSlug.slice(0, -1) || form.isFieldTouched('slug') === false) {
      form.setFieldsValue({ slug: autoSlug });
    }
  };

  return (
    <Form
      form={form}
      layout="vertical"
      onFinish={onSubmit}
      size="middle"
      style={{ marginTop: 12 }}
    >
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
        <Form.Item
          name="name"
          label={<Text style={{ color: '#c9d1d9', fontSize: '13px' }}>{t('auth.orgNameLabel')}</Text>}
          rules={[{ required: true, message: t('auth.orgNameRequired') }]}
        >
          <Input
            prefix={<BankOutlined style={{ color: '#8b949e' }} />}
            placeholder={t('auth.orgNamePlaceholder')}
            onChange={handleOrgNameChange}
            style={{ background: '#0d1117', borderColor: '#30363d', color: '#f0f6fc' }}
          />
        </Form.Item>

        <Form.Item
          name="slug"
          label={<Text style={{ color: '#c9d1d9', fontSize: '13px' }}>{t('auth.orgSlugLabel')}</Text>}
          rules={[{ required: true, message: t('auth.orgSlugRequired') }]}
          extra={<Text style={{ color: '#8b949e', fontSize: '11px' }}>{t('auth.orgSlugHelp')}</Text>}
        >
          <Input
            placeholder={t('auth.orgSlugPlaceholder')}
            style={{ background: '#0d1117', borderColor: '#30363d', color: '#f0f6fc' }}
          />
        </Form.Item>
      </div>

      <Form.Item
        name="domain"
        label={
          <Space>
            <Text style={{ color: '#c9d1d9', fontSize: '13px' }}>{t('auth.domainLabel')}</Text>
            <Text style={{ color: '#8b949e', fontSize: '11px' }}>{t('auth.domainOptional')}</Text>
          </Space>
        }
      >
        <Input
          prefix={<GlobalOutlined style={{ color: '#8b949e' }} />}
          placeholder={t('auth.domainPlaceholder')}
          style={{ background: '#0d1117', borderColor: '#30363d', color: '#f0f6fc' }}
        />
      </Form.Item>

      <Divider style={{ borderColor: '#30363d', margin: '14px 0' }}>
        <Text style={{ color: '#8b949e', fontSize: '12px' }}>{t('auth.adminDetailsDivider')}</Text>
      </Divider>

      <Form.Item
        name="admin_name"
        label={<Text style={{ color: '#c9d1d9', fontSize: '13px' }}>{t('auth.adminNameLabel')}</Text>}
        rules={[{ required: true, message: t('auth.adminNameRequired') }]}
      >
        <Input
          prefix={<UserOutlined style={{ color: '#8b949e' }} />}
          placeholder={t('auth.adminNamePlaceholder')}
          style={{ background: '#0d1117', borderColor: '#30363d', color: '#f0f6fc' }}
        />
      </Form.Item>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
        <Form.Item
          name="admin_email"
          label={<Text style={{ color: '#c9d1d9', fontSize: '13px' }}>{t('auth.adminEmailLabel')}</Text>}
          rules={[
            { required: true, message: t('auth.emailRequired') },
            { type: 'email', message: t('auth.emailInvalid') },
          ]}
        >
          <Input
            prefix={<MailOutlined style={{ color: '#8b949e' }} />}
            placeholder={t('auth.emailPlaceholder')}
            style={{ background: '#0d1117', borderColor: '#30363d', color: '#f0f6fc' }}
          />
        </Form.Item>

        <Form.Item
          name="admin_password"
          label={<Text style={{ color: '#c9d1d9', fontSize: '13px' }}>{t('auth.adminPasswordLabel')}</Text>}
          rules={[
            { required: true, message: t('auth.passwordRequired') },
            { min: 6, message: t('auth.passwordMinLength') },
          ]}
        >
          <Input.Password
            prefix={<LockOutlined style={{ color: '#8b949e' }} />}
            placeholder={t('auth.passwordPlaceholder')}
            style={{ background: '#0d1117', borderColor: '#30363d', color: '#f0f6fc' }}
          />
        </Form.Item>
      </div>

      <Form.Item style={{ marginTop: 20, marginBottom: 8 }}>
        <Button
          type="primary"
          htmlType="submit"
          loading={loading}
          block
          style={{
            height: 44,
            background: '#10b981',
            borderColor: '#10b981',
            fontWeight: 700,
            fontSize: '15px',
            borderRadius: 8,
          }}
        >
          {t('auth.createOrgButton')}
        </Button>
      </Form.Item>
    </Form>
  );
};

export default RegisterOrgForm;
