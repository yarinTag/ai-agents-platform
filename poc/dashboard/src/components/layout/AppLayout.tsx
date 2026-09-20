import React from 'react';
import { Layout } from 'antd';
import { OfficeTopBar } from './OfficeTopBar';

const { Content } = Layout;

interface AppLayoutProps {
  children: React.ReactNode;
}

export const AppLayout: React.FC<AppLayoutProps> = ({ children }) => {
  return (
    <Layout style={{ minHeight: '100vh', background: '#f7f6f2' }}>
      {/* Top Header */}
      <OfficeTopBar />

      {/* Main Content Area */}
      <Content
        style={{
          background: '#f7f6f2',
          minHeight: 'calc(100vh - 52px)',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        {children}
      </Content>
    </Layout>
  );
};

export default AppLayout;
