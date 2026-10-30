import React, { useState } from 'react';
import { Layout } from 'antd';
import { useLocation } from 'react-router-dom';
import { OfficeTopBar } from './OfficeTopBar';
import { AppSidebar } from './AppSidebar';

const { Content } = Layout;

interface AppLayoutProps {
  children: React.ReactNode;
}

export const AppLayout: React.FC<AppLayoutProps> = ({ children }) => {
  const location = useLocation();
  const isOfficeView = location.pathname === '/';

  const [collapsed, setCollapsed] = useState<boolean>(() => {
    try {
      return localStorage.getItem('agents_office_sidebar_collapsed') === 'true';
    } catch {
      return false;
    }
  });

  const handleToggleCollapse = () => {
    setCollapsed((prev) => {
      const next = !prev;
      try {
        localStorage.setItem('agents_office_sidebar_collapsed', String(next));
      } catch {}
      return next;
    });
  };

  return (
    <Layout style={{ height: '100dvh', minHeight: 0, overflow: 'hidden', background: '#0a0d12', color: '#f0f6fc' }}>
      {/* Top Header */}
      <OfficeTopBar collapsed={collapsed} onToggleCollapse={handleToggleCollapse} />

      {/* Main Body: Collapsible Sidebar + Content */}
      <Layout
        style={{
          background: '#0a0d12',
          display: 'flex',
          flexDirection: 'row',
          flex: 1,
          minHeight: 0,
          overflow: 'hidden',
        }}
      >
        <AppSidebar collapsed={collapsed} onToggleCollapse={handleToggleCollapse} />

        <Content
          style={{
            background: '#0a0d12',
            minHeight: 0,
            minWidth: 0,
            height: '100%',
            overflow: isOfficeView ? 'hidden' : 'auto',
            flex: 1,
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
    </Layout>
  );
};

export default AppLayout;

