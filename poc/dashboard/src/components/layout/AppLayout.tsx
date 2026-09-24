import React from 'react';
import { Layout } from 'antd';
import { useLocation } from 'react-router-dom';
import { OfficeTopBar } from './OfficeTopBar';
import { MCPTopBar } from './MCPTopBar';

const { Content } = Layout;

interface AppLayoutProps {
  children: React.ReactNode;
}

export const AppLayout: React.FC<AppLayoutProps> = ({ children }) => {
  const location = useLocation();
  const isOfficeView = location.pathname === '/';

  return (
    <Layout style={{ minHeight: '100vh', background: '#0a0d12', color: '#f0f6fc' }}>
      {/* Top Header */}
      <OfficeTopBar />
      {/* MCP Connectors Sub-Header */}
      <MCPTopBar />


      {/* Main Content Area */}
      <Content
        style={{
          background: '#0a0d12',
          minHeight: 'calc(100vh - 52px)',
          display: 'flex',
          flexDirection: 'column',
          padding: isOfficeView ? 0 : '24px 28px',
          maxWidth: isOfficeView ? '100%' : '1600px',
          margin: isOfficeView ? 0 : '0 auto',
          width: '100%',
        }}
      >
        {children}
      </Content>
    </Layout>
  );
};

export default AppLayout;
