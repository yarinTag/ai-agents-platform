import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { ConfigProvider, theme, App as AntdApp } from 'antd';
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
              <Route path="/projects" element={<ProjectsPage />} />
              <Route path="/dashboard" element={<DashboardPage />} />
            </Routes>
          </AppLayout>
        </BrowserRouter>
      </AntdApp>
    </ConfigProvider>
  );
};

export default App;
