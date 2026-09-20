import React, { useState, useEffect } from 'react';
import { Tag } from 'antd';
import {
  GithubOutlined,
  ThunderboltFilled,
  GlobalOutlined,
} from '@ant-design/icons';
import { Link, useLocation } from 'react-router-dom';

export const OfficeTopBar: React.FC = () => {
  const [timeStr, setTimeStr] = useState('');
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

  return (
    <header
      style={{
        height: '52px',
        background: '#f7f6f2',
        borderBottom: '1px solid #e5e2d8',
        padding: '0 24px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        userSelect: 'none',
        zIndex: 100,
      }}
    >
      {/* Left: Brand + Connected App Icons */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
        {/* Brand */}
        <Link to="/" style={{ textDecoration: 'none', display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span style={{ fontSize: '15px', fontWeight: 900, color: '#1c1917', letterSpacing: '1px' }}>
            AGENTS OFFICE
          </span>
          <span
            style={{
              fontSize: '10px',
              fontWeight: 800,
              color: '#78716c',
              padding: '1px 4px',
              background: '#eae7dd',
              borderRadius: '4px',
            }}
          >
            v3
          </span>
        </Link>

        {/* Connected To Label & Icons */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '10px', fontWeight: 800, color: '#78716c' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#10b981' }} />
            <span>CONNECTED TO</span>
          </div>

          {/* App Icons (Meta, Claude, GitHub, Notion, Gmail, Discord) */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '14px', color: '#44403c' }}>
            <span title="Meta / Facebook" style={{ cursor: 'pointer' }}>♾️</span>
            <span title="Anthropic Claude" style={{ cursor: 'pointer' }}>✳️</span>
            <span title="OpenAI / ChatGPT" style={{ cursor: 'pointer' }}>⚡</span>
            <span title="GitHub Local Repos" style={{ cursor: 'pointer' }}><GithubOutlined /></span>
            <span title="Notion Notes" style={{ cursor: 'pointer' }}>📓</span>
            <span title="Google Workspace / Gmail" style={{ cursor: 'pointer' }}>✉️</span>
            <span title="Terminal CLI" style={{ cursor: 'pointer' }}>💻</span>
          </div>
        </div>
      </div>

      {/* Navigation Links in Center */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        <Link
          to="/"
          style={{
            fontSize: '11px',
            fontWeight: 800,
            color: location.pathname === '/' ? '#1c1917' : '#78716c',
            textDecoration: 'none',
            padding: '4px 10px',
            borderRadius: '8px',
            background: location.pathname === '/' ? '#eae7dd' : 'transparent',
          }}
        >
          OFFICE CANVAS
        </Link>
        <Link
          to="/flow"
          style={{
            fontSize: '11px',
            fontWeight: 800,
            color: location.pathname === '/flow' ? '#1c1917' : '#78716c',
            textDecoration: 'none',
            padding: '4px 10px',
            borderRadius: '8px',
            background: location.pathname === '/flow' ? '#eae7dd' : 'transparent',
          }}
        >
          LIVE FLOW
        </Link>
        <Link
          to="/agents"
          style={{
            fontSize: '11px',
            fontWeight: 800,
            color: location.pathname === '/agents' ? '#1c1917' : '#78716c',
            textDecoration: 'none',
            padding: '4px 10px',
            borderRadius: '8px',
            background: location.pathname === '/agents' ? '#eae7dd' : 'transparent',
          }}
        >
          AGENTS ROSTER
        </Link>
        <Link
          to="/skills"
          style={{
            fontSize: '11px',
            fontWeight: 800,
            color: location.pathname === '/skills' ? '#1c1917' : '#78716c',
            textDecoration: 'none',
            padding: '4px 10px',
            borderRadius: '8px',
            background: location.pathname === '/skills' ? '#eae7dd' : 'transparent',
          }}
        >
          PLUGINS HUB
        </Link>
        <Link
          to="/tasks"
          style={{
            fontSize: '11px',
            fontWeight: 800,
            color: location.pathname === '/tasks' ? '#1c1917' : '#78716c',
            textDecoration: 'none',
            padding: '4px 10px',
            borderRadius: '8px',
            background: location.pathname === '/tasks' ? '#eae7dd' : 'transparent',
          }}
        >
          TASKS QUEUE
        </Link>
      </div>

      {/* Right: Headless status + Clock */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '10px', fontWeight: 800, color: '#78716c' }}>
          <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#10b981' }} />
          <span>RUNS HEADLESS ON</span>
          <span style={{ fontSize: '12px' }}>⚙️ 🧠</span>
        </div>

        {/* Live Digital Clock (matching screenshot e.g. 05:44:10 pm) */}
        <div
          style={{
            fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
            fontSize: '13px',
            fontWeight: 700,
            color: '#1c1917',
            letterSpacing: '0.5px',
          }}
        >
          {timeStr}
        </div>
      </div>
    </header>
  );
};

export default OfficeTopBar;
