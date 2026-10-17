import React, { useState } from 'react';
import { Card, Typography, Alert, Space, Tabs } from 'antd';
import {
  UserOutlined,
  BankOutlined,
  KeyOutlined,
  RocketOutlined,
  SafetyCertificateOutlined,
} from '@ant-design/icons';
import { useAuth } from '../context/AuthContext';
import { useTranslation } from '../i18n';
import { SignInForm, RegisterOrgForm, AcceptInviteForm } from '../components/auth';

const { Title, Text, Paragraph } = Typography;

export const AuthPage: React.FC = () => {
  const { login, register, acceptInvitation } = useAuth();
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState<'signin' | 'register' | 'invite'>('signin');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(false);

  const handleSignIn = async (values: any) => {
    setLoading(true);
    setErrorMessage(null);
    try {
      await login({
        email: values.email.trim(),
        password: values.password,
      });
    } catch (err: any) {
      const detail = err.response?.data?.detail || err.message || t('auth.loginFailed');
      setErrorMessage(detail);
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (values: any) => {
    setLoading(true);
    setErrorMessage(null);
    try {
      await register({
        name: values.name.trim(),
        slug: values.slug.trim().toLowerCase(),
        domain: values.domain ? values.domain.trim().toLowerCase() : undefined,
        admin_name: values.admin_name.trim(),
        admin_email: values.admin_email.trim().toLowerCase(),
        admin_password: values.admin_password,
      });
    } catch (err: any) {
      const detail = err.response?.data?.detail || err.message || t('auth.registerFailed');
      setErrorMessage(detail);
    } finally {
      setLoading(false);
    }
  };

  const handleAcceptInvite = async (values: any) => {
    setLoading(true);
    setErrorMessage(null);
    try {
      await acceptInvitation({
        invite_token: values.invite_token.trim(),
        full_name: values.full_name.trim(),
        password: values.password,
      });
    } catch (err: any) {
      const detail = err.response?.data?.detail || err.message || t('auth.inviteFailed');
      setErrorMessage(detail);
    } finally {
      setLoading(false);
    }
  };

  const tabItems = [
    {
      key: 'signin',
      label: (
        <span style={{ fontSize: '14px', fontWeight: 600 }}>
          <UserOutlined style={{ marginRight: 6 }} />
          {t('auth.signInTab')}
        </span>
      ),
      children: <SignInForm onSubmit={handleSignIn} loading={loading} />,
    },
    {
      key: 'register',
      label: (
        <span style={{ fontSize: '14px', fontWeight: 600 }}>
          <BankOutlined style={{ marginRight: 6 }} />
          {t('auth.registerTab')}
        </span>
      ),
      children: <RegisterOrgForm onSubmit={handleRegister} loading={loading} />,
    },
    {
      key: 'invite',
      label: (
        <span style={{ fontSize: '14px', fontWeight: 600 }}>
          <KeyOutlined style={{ marginRight: 6 }} />
          {t('auth.inviteTab')}
        </span>
      ),
      children: <AcceptInviteForm onSubmit={handleAcceptInvite} loading={loading} />,
    },
  ];

  return (
    <div
      style={{
        minHeight: '100vh',
        background: '#0a0d12',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '24px 16px',
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      {/* Ambient background glow */}
      <div
        style={{
          position: 'absolute',
          top: '20%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          width: '600px',
          height: '400px',
          background: 'radial-gradient(circle, rgba(16, 185, 129, 0.08) 0%, transparent 70%)',
          pointerEvents: 'none',
        }}
      />

      <Card
        style={{
          width: '100%',
          maxWidth: 540,
          background: '#161b22',
          borderColor: '#30363d',
          borderRadius: 14,
          boxShadow: '0 20px 40px rgba(0, 0, 0, 0.55)',
          zIndex: 1,
        }}
        bodyStyle={{ padding: '32px 28px' }}
      >
        {/* Header branding */}
        <div style={{ textAlign: 'center', marginBottom: 24 }}>
          <Space direction="vertical" size={4} style={{ display: 'flex', alignItems: 'center' }}>
            <div
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: 48,
                height: 48,
                borderRadius: 12,
                background: 'rgba(16, 185, 129, 0.15)',
                border: '1px solid rgba(16, 185, 129, 0.35)',
                marginBottom: 8,
              }}
            >
              <RocketOutlined style={{ fontSize: 24, color: '#10b981' }} />
            </div>

            <Title level={3} style={{ color: '#f0f6fc', margin: 0, fontWeight: 800, letterSpacing: '0.5px' }}>
              {t('auth.title')}
            </Title>
            <Text style={{ color: '#8b949e', fontSize: '13px', fontWeight: 500 }}>
              {t('auth.subtitle')}
            </Text>

            <div
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                marginTop: 6,
                padding: '2px 10px',
                borderRadius: 20,
                background: '#0d1117',
                border: '1px solid #21262d',
                fontSize: '11px',
                color: '#34d399',
              }}
            >
              <SafetyCertificateOutlined style={{ fontSize: 12 }} />
              <span>{t('auth.rbacBadge')}</span>
            </div>
          </Space>
        </div>

        {errorMessage && (
          <Alert
            type="error"
            message={errorMessage}
            showIcon
            closable
            onClose={() => setErrorMessage(null)}
            style={{
              marginBottom: 20,
              background: 'rgba(239, 68, 68, 0.12)',
              borderColor: 'rgba(239, 68, 68, 0.3)',
              color: '#f87171',
            }}
          />
        )}

        <Tabs
          activeKey={activeTab}
          onChange={(key) => {
            setActiveTab(key as any);
            setErrorMessage(null);
          }}
          items={tabItems}
          centered
          tabBarStyle={{ borderColor: '#21262d', marginBottom: 20 }}
        />
      </Card>

      {/* Footer information */}
      <Paragraph style={{ marginTop: 24, color: '#6e7681', fontSize: '12px', textAlign: 'center' }}>
        {t('auth.footerText')}
      </Paragraph>
    </div>
  );
};

export default AuthPage;
