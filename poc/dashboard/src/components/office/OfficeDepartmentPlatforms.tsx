import { Tag } from 'antd';
import { StarFilled, SyncOutlined } from '@ant-design/icons';
import { Agent } from '../../types/agent';
import { Task } from '../../types/task';

import type { useOfficeCanvas } from './useOfficeCanvas';

export function OfficeDepartmentPlatforms({ model }: { model: ReturnType<typeof useOfficeCanvas> }) {
  const {
    agents, onSelectAgent, onSelectDepartment, hoveredDept, setHoveredDept,
    DEPARTMENTS, findAgentForDesk, getAgentActiveTask, getDeptStats,
  } = model;
  return (<>
{/* 6 Department Floating Isometric Platforms */}
        {DEPARTMENTS.map((dept) => {
          const stats = getDeptStats(dept.key);
          const isDeptActive = stats.doing > 0;

          return (
            <div
              key={dept.key}
              onMouseEnter={() => setHoveredDept(dept.key)}
              onMouseLeave={() => setHoveredDept(null)}
              style={{
                position: 'absolute',
                left: `${dept.posX}px`,
                top: `${dept.posY}px`,
                transform: 'translate(-50%, -50%)',
                width: '260px',
                height: '190px',
              }}
            >
              {/* Isometric 3D Platform Slab */}
              <div
                style={{
                  position: 'absolute',
                  inset: 0,
                  background: isDeptActive ? '#f4fbf7' : '#eae7dd',
                  borderRadius: '24px',
                  boxShadow: isDeptActive
                    ? `0 16px 32px ${dept.dotColor}25, inset 0 2px 0 rgba(255,255,255,0.9)`
                    : '0 16px 30px rgba(0,0,0,0.12), inset 0 2px 0 rgba(255,255,255,0.7)',
                  border: isDeptActive ? `2px solid ${dept.dotColor}88` : '1px solid #dcd8ca',
                  transform: 'perspective(600px) rotateX(20deg)',
                  transformOrigin: 'center center',
                  transition: 'background 0.3s ease, border 0.3s ease',
                }}
              />

              {/* Office Plants in corners */}
              <div
                style={{
                  position: 'absolute',
                  top: '12px',
                  left: '12px',
                  fontSize: '15px',
                  filter: 'drop-shadow(0 2px 2px rgba(0,0,0,0.15))',
                  pointerEvents: 'none',
                }}
              >
                🪴
              </div>
              <div
                style={{
                  position: 'absolute',
                  bottom: '12px',
                  right: '12px',
                  fontSize: '15px',
                  filter: 'drop-shadow(0 2px 2px rgba(0,0,0,0.15))',
                  pointerEvents: 'none',
                }}
              >
                🪴
              </div>

              {/* Desks & Characters on the Platform */}
              {dept.desks.map((desk, dIdx) => {
                const deskAgent = findAgentForDesk(dept.key, desk.title, dIdx);
                const activeTask = deskAgent ? getAgentActiveTask(deskAgent.id) : undefined;
                const isWorking = !!activeTask;

                return (
                  <div
                    key={dIdx}
                    onClick={(e) => {
                      e.stopPropagation();
                      if (deskAgent) onSelectAgent(deskAgent);
                    }}
                    style={{
                      position: 'absolute',
                      left: `calc(50% + ${desk.relX}px)`,
                      top: `calc(50% + ${desk.relY}px)`,
                      transform: 'translate(-50%, -50%)',
                      cursor: 'pointer',
                      zIndex: 3,
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'center',
                      transition: 'transform 0.15s ease',
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.transform = 'translate(-50%, -55%) scale(1.1)')}
                    onMouseLeave={(e) => (e.currentTarget.style.transform = 'translate(-50%, -50%) scale(1)')}
                  >
                    {/* Live Speech / Task Bubble if Working */}
                    {isWorking && (
                      <div
                        style={{
                          background: '#10b981',
                          color: '#ffffff',
                          borderRadius: '8px',
                          padding: '2px 6px',
                          fontSize: '8px',
                          fontWeight: 700,
                          boxShadow: '0 2px 8px rgba(16, 185, 129, 0.4)',
                          whiteSpace: 'nowrap',
                          marginBottom: '2px',
                          animation: 'pulse 1.5s infinite',
                        }}
                      >
                        ⚡ WORKING...
                      </div>
                    )}

                    {/* Desk Name Tag Label */}
                    <div
                      style={{
                        background: deskAgent ? '#ffffff' : 'rgba(255, 255, 255, 0.45)',
                        border: isWorking
                          ? '1.5px solid #10b981'
                          : deskAgent
                          ? '1px solid #e2ded5'
                          : '1px dashed #dcd8ca',
                        borderRadius: '10px',
                        padding: '1px 6px',
                        fontSize: '9px',
                        fontWeight: deskAgent && desk.isLead ? 700 : 500,
                        color: deskAgent ? (desk.isLead ? '#b45309' : '#44403c') : '#a8a29e',
                        boxShadow: deskAgent ? '0 2px 6px rgba(0,0,0,0.08)' : 'none',
                        whiteSpace: 'nowrap',
                        marginBottom: '3px',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '3px',
                      }}
                    >
                      {deskAgent && desk.isLead && <StarFilled style={{ color: '#f59e0b', fontSize: '8px' }} />}
                      {deskAgent ? deskAgent.name.split(' ')[0] : 'Open Desk'}
                    </div>

                    {/* Desk & Computer Rig (Isometric 3D Illustration) */}
                    <div
                      style={{
                        position: 'relative',
                        width: '32px',
                        height: '24px',
                        background: isWorking ? '#e6fcf5' : '#d6d2c4',
                        borderRadius: '5px',
                        border: isWorking ? '1px solid #10b981' : '1px solid #b8b3a5',
                        boxShadow: '0 4px 6px rgba(0,0,0,0.15)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                      }}
                    >
                      {/* Computer Screen */}
                      <div
                        style={{
                          width: '18px',
                          height: '13px',
                          background: isWorking ? '#059669' : '#292524',
                          borderRadius: '2px',
                          border: '1px solid #1c1917',
                          boxShadow: isWorking ? '0 0 10px #10b981' : 'none',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                        }}
                      >
                        {isWorking ? (
                          <span style={{ fontSize: '7px', color: '#ecfdf5', fontWeight: 700 }}>AI</span>
                        ) : (
                          <div style={{ width: '12px', height: '1.5px', background: '#57534e' }} />
                        )}
                      </div>

                      {/* Agent Character sitting at desk - ONLY when real agent exists! */}
                      {deskAgent && (
                        <div
                          style={{
                            position: 'absolute',
                            bottom: '-8px',
                            width: '14px',
                            height: '14px',
                            borderRadius: '50%',
                            background: desk.isLead ? '#f59e0b' : '#0284c7',
                            border: isWorking ? '2px solid #10b981' : '2px solid #ffffff',
                            boxShadow: '0 2px 4px rgba(0,0,0,0.2)',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            color: '#fff',
                            fontSize: '8px',
                            fontWeight: 700,
                          }}
                        >
                          {deskAgent.name[0]}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}

              {/* Compact Department Tag (Visible always, above the platform, never blocking agents) */}
              <div
                onClick={(e) => {
                  e.stopPropagation();
                  if (onSelectDepartment) onSelectDepartment(dept.key);
                }}
                style={{
                  position: 'absolute',
                  top: '-18px',
                  left: '50%',
                  transform: 'translateX(-50%)',
                  background: '#ffffff',
                  borderRadius: '12px',
                  border: isDeptActive ? `1.5px solid ${dept.dotColor}` : '1px solid #e5e2d8',
                  boxShadow: '0 4px 10px rgba(0, 0, 0, 0.08)',
                  padding: '3px 10px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  whiteSpace: 'nowrap',
                  cursor: 'pointer',
                  zIndex: 4,
                  transition: 'all 0.15s ease',
                }}
              >
                <span
                  style={{
                    width: 7,
                    height: 7,
                    borderRadius: '50%',
                    background: dept.dotColor,
                    boxShadow: isDeptActive ? `0 0 6px ${dept.dotColor}` : 'none',
                  }}
                />
                <span style={{ fontSize: '10px', fontWeight: 800, color: '#1c1917', letterSpacing: '0.8px' }}>
                  {dept.name}
                </span>
                <span style={{ fontSize: '9px', fontWeight: 700, color: '#78716c' }}>
                  ({stats.agentsCount})
                </span>
                {isDeptActive && (
                  <span style={{ fontSize: '8px', fontWeight: 800, color: '#10b981' }}>
                    • ACTIVE
                  </span>
                )}
              </div>

              {/* Floating Department Detailed HUD Card - ONLY VISIBLE ON HOVER, NOT covering the platform */}
              {hoveredDept === dept.key && (
                <div
                  onClick={(e) => {
                    e.stopPropagation();
                    if (onSelectDepartment) onSelectDepartment(dept.key);
                  }}
                  style={{
                    position: 'absolute',
                    top: '-145px',
                    left: '50%',
                    transform: 'translateX(-50%)',
                    background: '#ffffff',
                    borderRadius: '16px',
                    border: isDeptActive ? `2px solid ${dept.dotColor}` : '1px solid #e5e2d8',
                    boxShadow: isDeptActive
                      ? `0 16px 36px ${dept.dotColor}35`
                      : '0 16px 36px rgba(0, 0, 0, 0.15)',
                    padding: '12px 16px',
                    minWidth: '180px',
                    cursor: 'pointer',
                    zIndex: 50,
                  }}
                >
                  {/* Header: Dot + Department Name */}
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <span
                        style={{
                          width: 8,
                          height: 8,
                          borderRadius: '50%',
                          background: dept.dotColor,
                          boxShadow: isDeptActive ? `0 0 6px ${dept.dotColor}` : 'none',
                        }}
                      />
                      <span style={{ fontSize: '11px', fontWeight: 800, color: '#1c1917', letterSpacing: '0.8px' }}>
                        {dept.name}
                      </span>
                    </div>
                    {isDeptActive ? (
                      <span style={{ fontSize: '9px', fontWeight: 800, color: '#10b981' }}>
                        <SyncOutlined spin /> ACTIVE
                      </span>
                    ) : (
                      <span style={{ fontSize: '9px', fontWeight: 600, color: '#94a3b8' }}>
                        IDLE
                      </span>
                    )}
                  </div>

                  {/* Big Agent Count */}
                  <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px', margin: '4px 0 10px 0' }}>
                    <span style={{ fontSize: '28px', fontWeight: 800, color: '#1c1917', lineHeight: 1 }}>
                      {stats.agentsCount}
                    </span>
                    <span style={{ fontSize: '10px', fontWeight: 700, color: '#78716c', letterSpacing: '0.5px' }}>
                      AGENTS
                    </span>
                  </div>

                  {/* Two Key Metrics */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '3px', marginBottom: '10px', fontSize: '11px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span style={{ color: '#78716c', fontSize: '9px', fontWeight: 700 }}>{dept.stat1Label}</span>
                      <span style={{ fontWeight: 800, color: '#1c1917' }}>{stats.total}</span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span style={{ color: '#78716c', fontSize: '9px', fontWeight: 700 }}>{dept.stat2Label}</span>
                      <span style={{ fontWeight: 800, color: isDeptActive ? '#10b981' : '#64748b' }}>
                        {isDeptActive ? `${stats.doing} IN PROGRESS` : stats.done > 0 ? `${stats.done} VERIFIED` : 'STANDBY'}
                      </span>
                    </div>
                  </div>

                  {/* Bottom Task Pipeline Pills */}
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      borderTop: '1px solid #f0ede4',
                      paddingTop: '6px',
                      fontSize: '9px',
                      fontWeight: 700,
                      color: '#78716c',
                    }}
                  >
                    <span>
                      DOING{' '}
                      <strong style={{ color: stats.doing > 0 ? '#10b981' : '#1c1917' }}>
                        {stats.doing}
                      </strong>
                    </span>
                    <span>
                      NEXT <strong style={{ color: '#1c1917' }}>{stats.next}</strong>
                    </span>
                    <span>
                      DONE <strong style={{ color: '#059669' }}>{stats.done}</strong>
                    </span>
                  </div>
                </div>
              )}
            </div>
          );
        })}
  </>);
}
