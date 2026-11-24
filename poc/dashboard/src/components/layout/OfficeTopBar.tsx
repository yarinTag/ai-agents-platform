import { useNavigationText } from '../../i18n/navigation';
import { useTranslation } from '../../i18n';
import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Tooltip, Button, Tag, Popconfirm, Select } from 'antd';
import {
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  LogoutOutlined,
  UserOutlined,
} from '@ant-design/icons';
import { useAuth } from '../../context/AuthContext';

interface OfficeTopBarProps {
  collapsed?: boolean;
  onToggleCollapse?: () => void;
}

export const OfficeTopBar: React.FC<OfficeTopBarProps> = ({ collapsed = false, onToggleCollapse }) => {
  const text = useNavigationText();
  const { locale } = useTranslation();
  const [timeStr, setTimeStr] = useState('');
  const { user, departments, activeDepartmentId, setActiveDepartmentId, logout } = useAuth();

  useEffect(() => {
    const updateClock = () => {
      const now = new Date();
      setTimeStr(
        now.toLocaleTimeString(locale, {
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
          hour12: locale !== 'he',
        }).toLowerCase()
      );
    };

    updateClock();
    const timer = setInterval(updateClock, 1000);
    return () => clearInterval(timer);
  }, [locale]);

  return (
    <header
      style={{
        minHeight: '52px', flexWrap: 'wrap', gap: 8, paddingBlock: 8,
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
      <div style={{ display: 'flex', alignItems: 'center', gap: '14px', flexWrap: 'wrap', maxWidth: '100%' }}>
        {onToggleCollapse && (
          <Tooltip title={collapsed ? text.expand : text.collapse} placement="bottom">
            <Button
              type="text"
              icon={
                collapsed ? (
                  <MenuUnfoldOutlined style={{ fontSize: '16px', color: '#8b949e' }} />
                ) : (
                  <MenuFoldOutlined style={{ fontSize: '16px', color: '#8b949e' }} />
                )
              }
              aria-label={collapsed ? text.expand : text.collapse} onClick={onToggleCollapse}
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
          <span>{text.active}</span>
        </div>
      </div>

      {/* Right: Department Selector + User & Role + Logout + Clock */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap', maxWidth: '100%' }}>
        {/* Compact Department Selector Dropdown */}
        {departments && departments.length > 0 && (() => {
          const deptOptions = [
            ...(user?.role === 'ORG_ADMIN' ? [{ label: '🌐 ' + text.allDepartments, value: 'all' }] : []),
            ...departments.map((d) => {
              const deptId = d.id || d.department_id || '';
              return {
                label: `📁 ${d.name}`,
                value: deptId,
              };
            }),
          ];
          const firstDeptId = departments[0]?.id || departments[0]?.department_id;
          const fallbackValue = user?.role === 'ORG_ADMIN' ? 'all' : firstDeptId;
          const selectedValue =
            activeDepartmentId && deptOptions.some((opt) => opt.value === activeDepartmentId)
              ? activeDepartmentId
              : fallbackValue;

          return (
            <Select
              size="small" aria-label={text.department}
              value={selectedValue}
              optionFilterProp="label"
              onChange={(val) => {
                setActiveDepartmentId(val === 'all' ? null : val);
              }}
              options={deptOptions}
              style={{ minWidth: 160 }}
              popupMatchSelectWidth={false}
            />
          );
        })()}

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
          title={text.logoutPrompt}
          onConfirm={logout}
          okText={text.logout}
          cancelText={text.cancel}
          placement="bottomRight"
        >
          <Tooltip title={text.logout}>
            <Button
              type="text"
              size="small"
              aria-label={text.logout} icon={<LogoutOutlined style={{ color: '#ef4444' }} />}
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
