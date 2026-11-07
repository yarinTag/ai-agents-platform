import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ConfigProvider, theme, App as AntdApp, Spin } from 'antd';
import { AuthProvider, useAuth } from './context/AuthContext';
import { I18nProvider } from './i18n';
import AuthPage from './pages/AuthPage';
import AppLayout from './components/layout/AppLayout';
import { LazyFeatureRoute } from './components/common/LazyFeatureRoute';
import { usePermissions } from './hooks/usePermissions';
import DepartmentAccessPage from './components/common/DepartmentAccessPage';
import { Alert } from 'antd';
import { OptionalRuntimeSetup } from './components/common/OptionalRuntimeSetup';

// Optional view modules load only when their route is selected.
const featureRoutes = [
  { path: '/', load: () => import('./pages/OfficeView') },
  { path: '/workflows', capability: 'workflows', load: () => import('./pages/Workflows') },
  { path: '/workflows/:workflowId/logs', capability: 'workflows', load: () => import('./pages/WorkflowLogs') },
  { path: '/flow', load: () => import('./pages/AgentFlow') },
  { path: '/agents', load: () => import('./pages/Agents') },
  { path: '/skills', capability: 'skills', load: () => import('./pages/Skills') },
  { path: '/tasks', capability: 'tasks', load: () => import('./pages/Tasks') },
  { path: '/calendar', load: () => import('./pages/CalendarView') },
  { path: '/mcp', load: () => import('./pages/McpHub') },
  { path: '/projects', capability: 'projects', load: () => import('./pages/Projects') },
  { path: '/organization', capability: 'organizations', load: () => import('./pages/OrganizationPage') },
  { path: '/dashboard', capability: 'events', load: () => import('./pages/Dashboard') },
];

const AuthenticatedShell: React.FC = () => {
  const { isAuthenticated, isLoading, organization, user, activeDepartmentId } = useAuth();
  const permissions = usePermissions();
  const pageScope = JSON.stringify([organization?.id, user?.id, user?.role, activeDepartmentId, permissions.rank]);

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
      <BrowserRouter>
        <AppLayout>
          {permissions.isAdmin && <OptionalRuntimeSetup />}
          <Routes>
            <Route path="/settings" element={<Navigate to="/organization?tab=runtime" replace />} />
            {featureRoutes.map(({ path, capability, load }) => (
              <Route
                key={path}
                path={path}
                element={path === '/organization' && !permissions.isAdmin ? <DepartmentAccessPage key={pageScope} />
                  : !permissions.canRead ? <Alert type="info" message="No department access is assigned. Ask your organization administrator to add you to a department." />
                  : <LazyFeatureRoute key={`${pageScope}:${path}`} load={load} capability={capability} />}
              />
            ))}
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
