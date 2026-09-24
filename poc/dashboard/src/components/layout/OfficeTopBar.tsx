import React, { useState, useEffect } from 'react';
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

  const navLinks = [
    { to: '/', label: 'OFFICE CANVAS' },
    { to: '/flow', label: 'LIVE FLOW' },
    { to: '/agents', label: 'AGENTS ROSTER' },
    { to: '/skills', label: 'PLUGINS HUB' },
    { to: '/tasks', label: 'TASKS QUEUE' },
    { to: '/projects', label: 'PROJECTS & MEMORY' },
    { to: '/calendar', label: '🗓️ SCHEDULE / CALENDAR' },
  ];

  return (
    <header
      style={{
        height: '52px',
        background: '#0d1117',
        borderBottom: '1px solid #21262d',
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

      {/* Navigation Links in Center */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        {navLinks.map((link) => {
          const isActive = location.pathname === link.to;
          return (
            <Link
              key={link.to}
              to={link.to}
              style={{
                fontSize: '11px',
                fontWeight: 700,
                color: isActive ? '#f0f6fc' : '#8b949e',
                textDecoration: 'none',
                padding: '5px 11px',
                borderRadius: '6px',
                background: isActive ? '#21262d' : 'transparent',
                border: isActive ? '1px solid #30363d' : '1px solid transparent',
                transition: 'all 0.15s ease',
              }}
            >
              {link.label}
            </Link>
          );
        })}
      </div>

      {/* Right: Headless status + Clock */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '10px', fontWeight: 700, color: '#8b949e' }}>
          <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#10b981' }} />
          <span>RUNS HEADLESS ON</span>
          <span style={{ fontSize: '12px' }}>⚙️ 🧠</span>
        </div>

        {/* Live Digital Clock */}
        <div
          style={{
            fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
            fontSize: '13px',
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
