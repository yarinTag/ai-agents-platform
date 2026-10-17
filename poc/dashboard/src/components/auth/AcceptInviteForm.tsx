import React from 'react';
import { Form, Input, Button, Typography } from 'antd';
import { KeyOutlined, UserOutlined, LockOutlined } from '@ant-design/icons';
import { useTranslation } from '../../i18n';

const { Text } = Typography;

export interface AcceptInviteFormProps {
  onSubmit: (values: { invite_token: string; full_name: string; password: string }) => Promise<void>;
  loading: boolean;
}

export const AcceptInviteForm: React.FC<AcceptInviteFormProps> = ({ onSubmit, loading }) => {
  const { t } = useTranslation();

  return (
    <Form layout="vertical" onFinish={onSubmit} size="large" style={{ marginTop: 12 }}>
      <Form.Item
        name="invite_token"
        label={<Text style={{ color: '#c9d1d9', fontSize: '13px' }}>{t('auth.inviteTokenLabel')}</Text>}
        rules={[{ required: true, message: t('auth.inviteTokenRequired') }]}
        extra={<Text style={{ color: '#8b949e', fontSize: '11px' }}>{t('auth.inviteTokenHelp')}</Text>}
      >
        <Input
          prefix={<KeyOutlined style={{ color: '#8b949e' }} />}
          placeholder={t('auth.inviteTokenPlaceholder')}
          style={{ background: '#0d1117', borderColor: '#30363d', color: '#f0f6fc', fontFamily: 'monospace' }}
        />
      </Form.Item>

      <Form.Item
        name="full_name"
        label={<Text style={{ color: '#c9d1d9', fontSize: '13px' }}>{t('auth.fullNameLabel')}</Text>}
        rules={[{ required: true, message: t('auth.fullNameRequired') }]}
      >
        <Input
          prefix={<UserOutlined style={{ color: '#8b949e' }} />}
          placeholder={t('auth.fullNamePlaceholder')}
          style={{ background: '#0d1117', borderColor: '#30363d', color: '#f0f6fc' }}
        />
      </Form.Item>

      <Form.Item
        name="password"
        label={<Text style={{ color: '#c9d1d9', fontSize: '13px' }}>{t('auth.newPasswordLabel')}</Text>}
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

      <Form.Item style={{ marginTop: 24, marginBottom: 8 }}>
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
          {t('auth.joinOrgButton')}
        </Button>
      </Form.Item>
    </Form>
  );
};

export default AcceptInviteForm;
