import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { ConfigProvider, theme, App as AntdApp, Spin } from 'antd';
import { AuthProvider, useAuth } from './context/AuthContext';
import { I18nProvider } from './i18n';
import AuthPage from './pages/AuthPage';
import AppLayout from './components/layout/AppLayout';
import RuntimeSetupModal from './components/common/RuntimeSetupModal';
import OfficeViewPage from './pages/OfficeView';
import AgentFlowPage from './pages/AgentFlow';
import AgentsPage from './pages/Agents';
import ProjectsPage from './pages/Projects';
import SkillsPage from './pages/Skills';
import TasksPage from './pages/Tasks';
import DashboardPage from './pages/Dashboard';
import CalendarViewPage from './pages/CalendarView';
import McpHubPage from './pages/McpHub';
import OrganizationPage from './pages/OrganizationPage';

const AuthenticatedShell: React.FC = () => {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div
        style={{
          minHeight: '100vh',
          background: '#0a0d12',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 16,
        }}
      >
        <Spin size="large" />
        <div style={{ color: '#8b949e', fontSize: 13, letterSpacing: 0.5, fontWeight: 600 }}>
          AUTHENTICATING AUTONOMOUS OFFICE...
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <AuthPage />;
  }

  return (
    <>
      <RuntimeSetupModal />
      <BrowserRouter>
        <AppLayout>
          <Routes>
            <Route path="/" element={<OfficeViewPage />} />
            <Route path="/flow" element={<AgentFlowPage />} />
            <Route path="/agents" element={<AgentsPage />} />
            <Route path="/skills" element={<SkillsPage />} />
            <Route path="/tasks" element={<TasksPage />} />
            <Route path="/calendar" element={<CalendarViewPage />} />
            <Route path="/mcp" element={<McpHubPage />} />
            <Route path="/projects" element={<ProjectsPage />} />
            <Route path="/organization" element={<OrganizationPage />} />
            <Route path="/dashboard" element={<DashboardPage />} />
          </Routes>
        </AppLayout>
      </BrowserRouter>
    </>
  );
};

export const App: React.FC = () => {
  return (
    <ConfigProvider
      theme={{
        algorithm: theme.darkAlgorithm,
        token: {
          colorPrimary: '#10b981',
          colorBgBase: '#0a0d12',
          colorBgContainer: '#161b22',
          colorBgElevated: '#1c2128',
          colorBorder: '#30363d',
          colorBorderSecondary: '#21262d',
          colorText: '#f0f6fc',
          colorTextSecondary: '#8b949e',
          colorTextPlaceholder: '#6e7681',
          borderRadius: 8,
          fontFamily: `-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif`,
        },
      }}
    >
      <AntdApp>
        <I18nProvider>
          <AuthProvider>
            <AuthenticatedShell />
          </AuthProvider>
        </I18nProvider>
      </AntdApp>
    </ConfigProvider>
  );
};

export default App;
