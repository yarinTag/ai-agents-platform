import React from 'react';
import { Form, Input, Button, Typography } from 'antd';
import { MailOutlined, LockOutlined } from '@ant-design/icons';
import { useTranslation } from '../../i18n';

const { Text } = Typography;

export interface SignInFormProps {
  onSubmit: (values: { email: string; password: string }) => Promise<void>;
  loading: boolean;
}

export const SignInForm: React.FC<SignInFormProps> = ({ onSubmit, loading }) => {
  const { t } = useTranslation();

  return (
    <Form layout="vertical" onFinish={onSubmit} size="large" style={{ marginTop: 12 }}>
      <Form.Item
        name="email"
        label={<Text style={{ color: '#c9d1d9', fontSize: '13px' }}>{t('auth.emailLabel')}</Text>}
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
        name="password"
        label={<Text style={{ color: '#c9d1d9', fontSize: '13px' }}>{t('auth.passwordLabel')}</Text>}
        rules={[{ required: true, message: t('auth.passwordRequired') }]}
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
          {t('auth.signInButton')}
        </Button>
      </Form.Item>
    </Form>
  );
};

export default SignInForm;
