import React, { useState, useEffect } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { Tooltip, Button, Tag, Popconfirm, Select } from 'antd';
import {
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  LogoutOutlined,
  BankOutlined,
  UserOutlined,
} from '@ant-design/icons';
import { useAuth } from '../../context/AuthContext';

interface OfficeTopBarProps {
  collapsed?: boolean;
  onToggleCollapse?: () => void;
}

const routeTitles: Record<string, { title: string; subtitle: string; icon: string }> = {
  '/workflow-assistant': { title: 'WORKFLOW ASSISTANT', subtitle: 'Permission-aware workflow drafts', icon: '✦' },
  // '/': { title: 'OFFICE CANVAS', subtitle: 'Interactive Autonomous Workstation', icon: '🏢' },
  '/flow': { title: 'LIVE FLOW', subtitle: 'Execution Pipeline & Dag', icon: '⚡' },
  '/agents': { title: 'AGENTS ROSTER', subtitle: 'Autonomous Agent Fleet', icon: '🤖' },
  '/skills': { title: 'PLUGINS HUB', subtitle: 'Extensible Capabilities & Skills', icon: '🧩' },
  '/mcp': { title: 'MCP HUB', subtitle: 'Model Context Protocol Integrations', icon: '🔌' },
  '/tasks': { title: 'TASKS QUEUE', subtitle: 'Orchestrated Assignments', icon: '📋' },
  '/projects': { title: 'PROJECTS', subtitle: 'Enterprise Workspaces & Repositories', icon: '🗂️' },
  '/calendar': { title: 'SCHEDULE & CALENDAR', subtitle: 'Automated Cron Routines', icon: '🗓️' },
  '/organization': { title: 'ORG & TEAMS', subtitle: 'Departments, Budgets & Access Control', icon: '🏢' },
  '/dashboard': { title: 'SYSTEM METRICS', subtitle: 'Health & Runtime Statistics', icon: '📊' },
};

export const OfficeTopBar: React.FC<OfficeTopBarProps> = ({ collapsed = false, onToggleCollapse }) => {
  const [timeStr, setTimeStr] = useState('');
  const navigate = useNavigate();
  const { organization, user, departments, activeDepartmentId, setActiveDepartmentId, logout } = useAuth();
  const location = useLocation();

  useEffect(() => {
    const updateClock = () => {
      const now = new Date();
      setTimeStr(
        now.toLocaleTimeString('en-US', {
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
          hour12: true,
        }).toLowerCase()
      );
    };

    updateClock();
    const timer = setInterval(updateClock, 1000);
    return () => clearInterval(timer);
  }, []);

  const currentRoute = routeTitles[location.pathname] || {
    title: 'AGENTS PLATFORM',
    subtitle: 'Autonomous AI Office',
    icon: '⚡',
  };

  return (
    <header
      style={{
        height: '52px',
        flexShrink: 0,
        background: '#0d1117',
        borderBottom: '1px solid #21262d',
        padding: '0 20px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        userSelect: 'none',
        zIndex: 100,
      }}
    >
      {/* Left: Collapse Toggle + Brand + Live Status */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
        {onToggleCollapse && (
          <Tooltip title={collapsed ? 'Expand Menu' : 'Collapse Menu'} placement="bottom">
            <Button
              type="text"
              icon={
                collapsed ? (
                  <MenuUnfoldOutlined style={{ fontSize: '16px', color: '#8b949e' }} />
                ) : (
                  <MenuFoldOutlined style={{ fontSize: '16px', color: '#8b949e' }} />
                )
              }
              onClick={onToggleCollapse}
              style={{
                width: 34,
                height: 34,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                borderRadius: '6px',
                border: '1px solid #21262d',
                background: '#161b22',
              }}
            />
          </Tooltip>
        )}

        {/* Brand */}
        <Link to="/" style={{ textDecoration: 'none', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '15px', fontWeight: 900, color: '#f0f6fc', letterSpacing: '1px' }}>
            AGENTS OFFICE
          </span>
          <span
            style={{
              fontSize: '10px',
              fontWeight: 800,
              color: '#8b949e',
              padding: '1px 5px',
              background: '#161b22',
              borderRadius: '4px',
              border: '1px solid #30363d',
            }}
          >
            v3
          </span>
        </Link>

        {/* Live Platform Status */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            fontSize: '10px',
            fontWeight: 800,
            color: '#34d399',
            background: 'rgba(16, 185, 129, 0.15)',
            padding: '3px 9px',
            borderRadius: '12px',
            border: '1px solid rgba(16, 185, 129, 0.35)',
          }}
        >
          <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#10b981' }} />
          <span>ACTIVE PLATFORM</span>
        </div>
      </div>

      {/* Center: Current View Indicator */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          background: '#161b22',
          padding: '4px 12px',
          borderRadius: '20px',
          border: '1px solid #21262d',
        }}
      >
        <span style={{ fontSize: '13px' }}>{currentRoute.icon}</span>
        <span style={{ fontSize: '11px', fontWeight: 700, color: '#f0f6fc', letterSpacing: '0.5px' }}>
          {currentRoute.title}
        </span>
        <span style={{ color: '#30363d' }}>•</span>
        <span style={{ fontSize: '10px', fontWeight: 500, color: '#8b949e' }}>
          {currentRoute.subtitle}
        </span>
      </div>

      {/* Right: Org Info + User & Role + Logout + Clock */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
        {organization && (
          <Tooltip title="View Organization & Teams">
            <Tag
              icon={<BankOutlined />}
              color="blue"
              onClick={() => navigate('/organization')}
              style={{
                margin: 0,
                padding: '2px 8px',
                borderRadius: '6px',
                fontWeight: 600,
                fontSize: '11px',
                background: '#161b22',
                borderColor: '#30363d',
                color: '#58a6ff',
                cursor: 'pointer',
              }}
            >
              {organization.name}
            </Tag>
          </Tooltip>
        )}

        {/* Compact Department Selector Dropdown */}
        {departments && departments.length > 0 && (
          <Select
            size="small"
            value={activeDepartmentId || (user?.role === 'ORG_ADMIN' ? 'all' : departments[0]?.id)}
            onChange={(val) => {
              setActiveDepartmentId(val === 'all' ? null : val);
            }}
            options={[
              ...(user?.role === 'ORG_ADMIN' ? [{ label: '🌐 All Departments', value: 'all' }] : []),
              ...departments.map((d) => ({
                label: `📁 ${d.name}`,
                value: d.id,
              })),
            ]}
            style={{ minWidth: 150 }}
            popupMatchSelectWidth={false}
          />
        )}

        {user && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              background: '#161b22',
              padding: '2px 8px',
              borderRadius: '6px',
              border: '1px solid #30363d',
            }}
          >
            <UserOutlined style={{ color: '#8b949e', fontSize: '11px' }} />
            <span style={{ fontSize: '11px', fontWeight: 600, color: '#f0f6fc' }}>
              {user.full_name}
            </span>
            <Tag
              color={user.role === 'ORG_ADMIN' ? 'gold' : 'cyan'}
              style={{ margin: 0, fontSize: '10px', padding: '0 4px', lineHeight: '16px' }}
            >
              {user.role}
            </Tag>
          </div>
        )}

        <Popconfirm
          title="Are you sure you want to log out?"
          onConfirm={logout}
          okText="Log out"
          cancelText="Cancel"
          placement="bottomRight"
        >
          <Tooltip title="Log out">
            <Button
              type="text"
              size="small"
              icon={<LogoutOutlined style={{ color: '#ef4444' }} />}
              style={{
                width: 28,
                height: 28,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                borderRadius: '6px',
                border: '1px solid #30363d',
                background: '#161b22',
              }}
            />
          </Tooltip>
        </Popconfirm>

        {/* Live Digital Clock */}
        <div
          style={{
            fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
            fontSize: '12px',
            fontWeight: 700,
            color: '#f0f6fc',
            letterSpacing: '0.5px',
            background: '#161b22',
            padding: '2px 8px',
            borderRadius: '6px',
            border: '1px solid #30363d',
          }}
        >
          {timeStr}
        </div>
      </div>
    </header>
  );
};

export default OfficeTopBar;
