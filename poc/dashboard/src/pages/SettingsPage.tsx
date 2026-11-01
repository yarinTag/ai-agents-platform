import React from 'react';
import { Typography } from 'antd';
import { SettingOutlined } from '@ant-design/icons';
import { useRuntimeSetupText } from '../i18n/runtimeSetup';
import { RuntimeSettingsPanel } from '../components/common/RuntimeSettingsPanel';

const { Title, Text } = Typography;

export const SettingsPage: React.FC = () => {
  const runtimeText = useRuntimeSetupText();

  return (
    <div style={{ padding: 24, minHeight: '100vh', background: '#0a0d12' }}>
      <div style={{ marginBottom: 20 }}>
        <Title level={3} style={{ margin: 0, color: '#f0f6fc', display: 'flex', alignItems: 'center', gap: 10 }}>
          <SettingOutlined style={{ color: '#10b981' }} />
          <span>{runtimeText.settings}</span>
        </Title>
        <Text type="secondary" style={{ fontSize: 13 }}>
          {runtimeText.intro}
        </Text>
      </div>

      <RuntimeSettingsPanel />
    </div>
  );
};

export default SettingsPage;
