import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Tooltip, Button } from 'antd';
import {
  DesktopOutlined,
  DeploymentUnitOutlined,
  TeamOutlined,
  AppstoreOutlined,
  ApiOutlined,
  CheckSquareOutlined,
  FolderOpenOutlined,
  CalendarOutlined,
  BarChartOutlined,
  LeftOutlined,
  RightOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';

interface AppSidebarProps {
  collapsed: boolean;
  onToggleCollapse: () => void;
}

interface NavSection {
  title?: string;
  items: {
    to: string;
    label: string;
    icon: React.ReactNode;
    badge?: string;
    badgeColor?: string;
  }[];
}

export const AppSidebar: React.FC<AppSidebarProps> = ({ collapsed, onToggleCollapse }) => {
  const location = useLocation();

  const sections: NavSection[] = [
    {
      title: 'OPERATIONS',
      items: [
        {
          to: '/',
          label: 'Office Canvas',
          icon: <DesktopOutlined style={{ fontSize: '15px' }} />,
          badge: 'LIVE',
          badgeColor: '#10b981',
        },
        {
          to: '/flow',
          label: 'Live Flow',
          icon: <DeploymentUnitOutlined style={{ fontSize: '15px' }} />,
        },
        {
          to: '/agents',
          label: 'Agents Roster',
          icon: <TeamOutlined style={{ fontSize: '15px' }} />,
        },
      ],
    },
    {
      title: 'TOOLS & PLUGINS',
      items: [
        {
          to: '/skills',
          label: 'Plugins Hub',
          icon: <AppstoreOutlined style={{ fontSize: '15px' }} />,
        },
        {
          to: '/mcp',
          label: 'MCP Hub',
          icon: <ApiOutlined style={{ fontSize: '15px' }} />,
          badge: 'MCP',
          badgeColor: '#38bdf8',
        },
        {
          to: '/tasks',
          label: 'Tasks Queue',
          icon: <CheckSquareOutlined style={{ fontSize: '15px' }} />,
        },
      ],
    },
    {
      title: 'WORKSPACE & DATA',
      items: [
        {
          to: '/projects',
          label: 'Projects & Memory',
          icon: <FolderOpenOutlined style={{ fontSize: '15px' }} />,
        },
        {
          to: '/calendar',
          label: 'Schedule & Calendar',
          icon: <CalendarOutlined style={{ fontSize: '15px' }} />,
        },
        {
          to: '/dashboard',
          label: 'System Metrics',
          icon: <BarChartOutlined style={{ fontSize: '15px' }} />,
        },
      ],
    },
  ];

  return (
    <aside
      style={{
        width: collapsed ? '68px' : '230px',
        minWidth: collapsed ? '68px' : '230px',
        height: 'calc(100vh - 52px)',
        background: '#0d1117',
        borderRight: '1px solid #21262d',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        transition: 'width 0.22s cubic-bezier(0.4, 0, 0.2, 1), min-width 0.22s cubic-bezier(0.4, 0, 0.2, 1)',
        userSelect: 'none',
        zIndex: 90,
        overflow: 'hidden',
      }}
    >
      {/* Navigation List */}
      <div
        style={{
          flex: 1,
          overflowY: 'auto',
          overflowX: 'hidden',
          padding: collapsed ? '12px 8px' : '12px 10px',
          display: 'flex',
          flexDirection: 'column',
          gap: '4px',
        }}
      >
        {sections.map((section, sIdx) => (
          <div key={sIdx} style={{ marginBottom: collapsed ? '8px' : '12px' }}>
            {/* Section Header */}
            {!collapsed && section.title && (
              <div
                style={{
                  fontSize: '10px',
                  fontWeight: 700,
                  letterSpacing: '1px',
                  color: '#6e7681',
                  padding: '8px 12px 4px 12px',
                  textTransform: 'uppercase',
                }}
              >
                {section.title}
              </div>
            )}

            {collapsed && sIdx > 0 && (
              <div
                style={{
                  height: '1px',
                  background: '#21262d',
                  margin: '6px 8px',
                }}
              />
            )}

            {/* Nav Items */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
              {section.items.map((item) => {
                const isActive = location.pathname === item.to;

                const linkElement = (
                  <Link
                    to={item.to}
                    key={item.to}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: collapsed ? 'center' : 'space-between',
                      gap: collapsed ? 0 : '10px',
                      padding: collapsed ? '10px 0' : '9px 12px',
                      borderRadius: '8px',
                      textDecoration: 'none',
                      background: isActive
                        ? 'rgba(16, 185, 129, 0.12)'
                        : 'transparent',
                      color: isActive ? '#f0f6fc' : '#8b949e',
                      border: isActive
                        ? '1px solid rgba(16, 185, 129, 0.3)'
                        : '1px solid transparent',
                      borderLeft: isActive
                        ? '3px solid #10b981'
                        : '1px solid transparent',
                      fontWeight: isActive ? 700 : 500,
                      fontSize: '12px',
                      letterSpacing: '0.2px',
                      transition: 'all 0.15s ease',
                      boxShadow: isActive ? '0 1px 3px rgba(0, 0, 0, 0.2)' : 'none',
                    }}
                    onMouseEnter={(e) => {
                      if (!isActive) {
                        e.currentTarget.style.background = '#161b22';
                        e.currentTarget.style.color = '#f0f6fc';
                      }
                    }}
                    onMouseLeave={(e) => {
                      if (!isActive) {
                        e.currentTarget.style.background = 'transparent';
                        e.currentTarget.style.color = '#8b949e';
                      }
                    }}
                  >
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '10px',
                        minWidth: 0,
                      }}
                    >
                      <span
                        style={{
                          color: isActive ? '#34d399' : '#8b949e',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          transition: 'color 0.15s ease',
                        }}
                      >
                        {item.icon}
                      </span>
                      {!collapsed && (
                        <span
                          style={{
                            whiteSpace: 'nowrap',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                          }}
                        >
                          {item.label}
                        </span>
                      )}
                    </div>

                    {!collapsed && item.badge && (
                      <span
                        style={{
                          fontSize: '9px',
                          fontWeight: 800,
                          padding: '1px 5px',
                          borderRadius: '4px',
                          background: item.badgeColor ? `${item.badgeColor}20` : '#21262d',
                          color: item.badgeColor || '#8b949e',
                          border: item.badgeColor
                            ? `1px solid ${item.badgeColor}40`
                            : '1px solid #30363d',
                          letterSpacing: '0.5px',
                        }}
                      >
                        {item.badge}
                      </span>
                    )}
                  </Link>
                );

                if (collapsed) {
                  return (
                    <Tooltip
                      key={item.to}
                      title={
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                          <span>{item.label}</span>
                          {item.badge && (
                            <span
                              style={{
                                fontSize: '9px',
                                padding: '1px 4px',
                                borderRadius: '3px',
                                background: item.badgeColor ? `${item.badgeColor}30` : '#30363d',
                                color: item.badgeColor || '#8b949e',
                              }}
                            >
                              {item.badge}
                            </span>
                          )}
                        </div>
                      }
                      placement="right"
                      mouseEnterDelay={0.05}
                    >
                      {linkElement}
                    </Tooltip>
                  );
                }

                return linkElement;
              })}
            </div>
          </div>
        ))}
      </div>

      {/* Bottom Footer / Collapse Toggle */}
      <div
        style={{
          borderTop: '1px solid #21262d',
          padding: collapsed ? '10px 8px' : '10px 12px',
          background: '#0a0d12',
          display: 'flex',
          flexDirection: 'column',
          gap: '8px',
        }}
      >
        <Button
          type="text"
          onClick={onToggleCollapse}
          style={{
            width: '100%',
            height: '36px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: collapsed ? 'center' : 'flex-start',
            gap: '8px',
            color: '#8b949e',
            background: 'transparent',
            borderRadius: '6px',
            padding: collapsed ? '0' : '0 10px',
            fontSize: '11px',
            fontWeight: 600,
            border: '1px solid transparent',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.color = '#f0f6fc';
            e.currentTarget.style.background = '#161b22';
            e.currentTarget.style.borderColor = '#30363d';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.color = '#8b949e';
            e.currentTarget.style.background = 'transparent';
            e.currentTarget.style.borderColor = 'transparent';
          }}
        >
          {collapsed ? (
            <Tooltip title="Expand Sidebar" placement="right">
              <RightOutlined style={{ fontSize: '13px' }} />
            </Tooltip>
          ) : (
            <>
              <LeftOutlined style={{ fontSize: '12px' }} />
              <span>COLLAPSE SIDEBAR</span>
            </>
          )}
        </Button>

        {!collapsed && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              fontSize: '10px',
              color: '#6e7681',
              padding: '0 8px 4px 8px',
            }}
          >
            <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              <ThunderboltOutlined style={{ color: '#10b981' }} />
              <span>Autonomous v3</span>
            </span>
            <span style={{ fontFamily: 'monospace' }}>HEADLESS</span>
          </div>
        )}
      </div>
    </aside>
  );
};

export default AppSidebar;
