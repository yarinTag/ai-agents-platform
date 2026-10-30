import type { OfficeRightSidebarProps } from './officeSidebarTypes';
import React from 'react';
import { Input, Button, Dropdown, Progress, Tooltip } from 'antd';
import { DownOutlined, ThunderboltOutlined, SyncOutlined, DeleteOutlined } from '@ant-design/icons';

import { useOfficeSidebar } from './useOfficeSidebar';

export const OfficeRightSidebar: React.FC<OfficeRightSidebarProps> = (props) => {
  const {
    agents, onSelectAgent, departmentList,
    selectedDept, taskPrompt, setTaskPrompt, submitting, activeFilter,
    setActiveFilter, handleAddTask, handleDeleteTask, menuItems, runningTasks,
    backlogTasks, doneTasks, displayTasks, filteredTasks,
  } = useOfficeSidebar(props);
  return (
    <div
      style={{
        width: '380px',
        minWidth: '360px',
        background: '#ffffff',
        borderLeft: '1px solid #e5e2d8',
        padding: '18px 20px',
        display: 'flex',
        flexDirection: 'column',
        gap: '16px',
        height: 'calc(100vh - 52px)',
        overflowY: 'auto',
      }}
    >
      {/* Top Add Task Input Card */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        <div
          style={{
            background: '#ffffff',
            borderRadius: '24px',
            border: '1.5px solid #e5e2d8',
            padding: '4px 8px',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            boxShadow: '0 4px 14px rgba(0,0,0,0.04)',
          }}
        >
          {selectedDept ? (
            <Dropdown menu={{ items: menuItems }} trigger={['click']}>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  cursor: 'pointer',
                  padding: '4px 8px',
                  borderRadius: '12px',
                  fontSize: '11px',
                  fontWeight: 800,
                  color: '#1c1917',
                  whiteSpace: 'nowrap',
                  background: '#f7f6f2',
                }}
              >
                <span style={{ width: 7, height: 7, borderRadius: '50%', background: selectedDept.color }} />
                <span>{selectedDept.name}</span>
                <DownOutlined style={{ fontSize: '9px', color: '#78716c' }} />
              </div>
            </Dropdown>
          ) : (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                padding: '4px 8px',
                borderRadius: '12px',
                fontSize: '11px',
                fontWeight: 800,
                color: '#78716c',
                whiteSpace: 'nowrap',
                background: '#f7f6f2',
              }}
            >
              <span>GENERAL</span>
            </div>
          )}

          <Input
            placeholder={
              selectedDept
                ? `Type a task for ${selectedDept.name.toLowerCase()}...`
                : 'Type a task (no departments defined yet)...'
            }
            value={taskPrompt}
            onChange={(e) => setTaskPrompt(e.target.value)}
            onPressEnter={() => handleAddTask()}
            variant="borderless"
            style={{
              fontSize: '12px',
              color: '#1c1917',
              padding: '2px 4px',
            }}
          />

          <Button
            type="primary"
            onClick={() => handleAddTask()}
            loading={submitting}
            style={{
              background: '#1c1917',
              borderColor: '#1c1917',
              borderRadius: '18px',
              fontWeight: 800,
              fontSize: '11px',
              height: '28px',
              padding: '0 12px',
              color: '#fff',
            }}
          >
            ADD
          </Button>
        </div>

        {/* Quick Suggestion Chips */}
        {selectedDept && selectedDept.suggestions.length > 0 && (
          <div style={{ display: 'flex', gap: '4px', overflowX: 'auto', paddingBottom: '2px' }}>
            {selectedDept.suggestions.map((sug, sIdx) => (
              <button
                key={sIdx}
                onClick={() => handleAddTask(sug)}
                style={{
                  background: '#f5f4ef',
                  border: '1px solid #e7e4da',
                  borderRadius: '10px',
                  padding: '2px 8px',
                  fontSize: '9px',
                  fontWeight: 600,
                  color: '#57534e',
                  cursor: 'pointer',
                  whiteSpace: 'nowrap',
                }}
                title="Click to dispatch instantly"
              >
                + {sug}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* System Status Widget Card */}
      <div
        style={{
          background: '#ffffff',
          borderRadius: '16px',
          border: '1px solid #e5e2d8',
          padding: '14px 16px',
          boxShadow: '0 4px 12px rgba(0,0,0,0.03)',
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
        }}
      >
        <div
          style={{
            width: '44px',
            height: '44px',
            borderRadius: '12px',
            background: runningTasks.length > 0 ? '#ecfdf5' : '#f8fafc',
            border: runningTasks.length > 0 ? '1.5px solid #10b981' : '1px solid #e2e8f0',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: runningTasks.length > 0 ? '0 0 12px rgba(16, 185, 129, 0.3)' : 'none',
          }}
        >
          <ThunderboltOutlined
            style={{
              color: runningTasks.length > 0 ? '#16a34a' : '#94a3b8',
              fontSize: '20px',
              animation: runningTasks.length > 0 ? 'spin 3s linear infinite' : 'none',
            }}
          />
        </div>

        <div style={{ flex: 1 }}>
          <div style={{ fontSize: '11px', fontWeight: 800, color: '#1c1917', letterSpacing: '0.6px' }}>
            ORCHESTRATION ENGINE
          </div>
          <div style={{ fontSize: '10px', color: '#78716c', marginTop: '2px' }}>
            {agents.length === 0 ? (
              <span>No agents registered • 0 departments</span>
            ) : runningTasks.length > 0 ? (
              <span style={{ color: '#10b981', fontWeight: 700 }}>
                ⚡ {runningTasks.length} task in flight across {departmentList.length} dept{departmentList.length === 1 ? '' : 's'}
              </span>
            ) : (
              <span>
                {agents.length} agent{agents.length === 1 ? '' : 's'} registered · {departmentList.length} department{departmentList.length === 1 ? '' : 's'}
              </span>
            )}
          </div>
          {(() => {
            const rootAgent =
              agents.find((a) => a.role_type === 'ROOT_ORCHESTRATOR') ||
              agents.find((a) => a.role_type === 'MANAGER') ||
              agents[0];
            if (rootAgent && onSelectAgent) {
              return (
                <div
                  onClick={() => onSelectAgent(rootAgent)}
                  style={{ fontSize: '10px', fontWeight: 700, color: '#059669', marginTop: '3px', cursor: 'pointer' }}
                >
                  Open {rootAgent.name} ({rootAgent.role_type || 'Agent'}) →
                </div>
              );
            }
            return null;
          })()}
        </div>
      </div>

      {/* TASK STATUS Section Header */}
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '13px', fontWeight: 800, color: '#1c1917', letterSpacing: '0.8px' }}>
              TASK STATUS
            </span>
            <span
              style={{
                fontSize: '9px',
                fontWeight: 800,
                color: runningTasks.length > 0 ? '#10b981' : '#78716c',
                border: runningTasks.length > 0 ? '1px solid #10b981' : '1px solid #d6d3c8',
                borderRadius: '6px',
                padding: '1px 5px',
                display: 'flex',
                alignItems: 'center',
                gap: '3px',
              }}
            >
              {runningTasks.length > 0 && <SyncOutlined spin />} LIVE
            </span>
          </div>
          <span style={{ fontSize: '10px', fontWeight: 700, color: '#78716c', letterSpacing: '0.5px' }}>
            WHOLE OFFICE
          </span>
        </div>

        {/* Dynamic Task Filters Pills */}
        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '14px' }}>
          {[
            { key: 'ALL', label: `ALL ${displayTasks.length}` },
            { key: 'IN PROGRESS', label: `IN PROGRESS ${runningTasks.length}` },
            { key: 'BACKLOG', label: `BACKLOG ${backlogTasks.length}` },
            { key: 'DONE', label: `DONE ${doneTasks.length}` },
          ].map((tab) => {
            const isSelected = activeFilter === tab.key;
            return (
              <button
                key={tab.key}
                onClick={() => setActiveFilter(tab.key as any)}
                style={{
                  background: isSelected ? '#1c1917' : '#ffffff',
                  color: isSelected ? '#ffffff' : '#78716c',
                  border: `1px solid ${isSelected ? '#1c1917' : '#e5e2d8'}`,
                  borderRadius: '16px',
                  padding: '3px 10px',
                  fontSize: '9px',
                  fontWeight: 800,
                  cursor: 'pointer',
                  letterSpacing: '0.5px',
                  transition: 'all 0.15s ease',
                }}
              >
                {tab.label}
              </button>
            );
          })}
        </div>

        {/* Tasks List Cards */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {filteredTasks.length === 0 ? (
            <div
              style={{
                textAlign: 'center',
                padding: '24px 12px',
                color: '#a8a29e',
                fontSize: '11px',
                background: '#fbfaf8',
                borderRadius: '12px',
                border: '1px dashed #e2ded5',
              }}
            >
              No tasks in {activeFilter}. Type a mission above to start!
            </div>
          ) : (
            filteredTasks.map((t) => (
              <div
                key={t.id}
                onClick={() => {
                  if (t.agentObj && onSelectAgent) onSelectAgent(t.agentObj);
                }}
                style={{
                  background: '#ffffff',
                  borderRadius: '12px',
                  border: t.status === 'IN PROGRESS' ? '1px solid #10b981' : '1px solid #e7e4da',
                  padding: '12px 14px',
                  boxShadow: t.status === 'IN PROGRESS' ? '0 4px 12px rgba(16, 185, 129, 0.08)' : '0 2px 6px rgba(0,0,0,0.02)',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: '10px' }}>
                  {/* Percentage Badge */}
                  <div
                    style={{
                      border: t.status === 'DONE' ? '1.5px solid #10b981' : '1.5px solid #d6d3c8',
                      borderRadius: '12px',
                      padding: '2px 6px',
                      fontSize: '10px',
                      fontWeight: 800,
                      color: t.status === 'DONE' ? '#059669' : '#1c1917',
                      lineHeight: 1,
                      background: t.status === 'DONE' ? '#ecfdf5' : '#ffffff',
                    }}
                  >
                    {t.status === 'DONE' ? '✓' : `${t.percent}%`}
                  </div>

                  {/* Title & Metadata */}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div
                      style={{
                        fontSize: '12px',
                        fontWeight: 700,
                        color: '#1c1917',
                        lineHeight: '1.3',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}
                      title={t.title}
                    >
                      {t.title}
                    </div>
                    <div
                      style={{
                        fontSize: '9px',
                        fontWeight: 700,
                        color: '#a8a29e',
                        letterSpacing: '0.5px',
                        marginTop: '3px',
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                      }}
                    >
                      <span>
                        {t.agentName} · {t.dept}
                      </span>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <span>{t.time}</span>
                        <Tooltip title="Delete task">
                          <DeleteOutlined
                            onClick={(e) => handleDeleteTask(e, t.id)}
                            style={{ color: '#d97706', fontSize: '10px', cursor: 'pointer' }}
                          />
                        </Tooltip>
                      </div>
                    </div>

                    {/* Progress Line */}
                    <div
                      style={{
                        width: '100%',
                        height: '3px',
                        background: '#f5f3ee',
                        borderRadius: '2px',
                        marginTop: '8px',
                        overflow: 'hidden',
                      }}
                    >
                      <div
                        style={{
                          width: `${t.percent}%`,
                          height: '100%',
                          background: t.status === 'DONE' ? '#10b981' : '#1c1917',
                          transition: 'width 0.4s ease-out',
                        }}
                      />
                    </div>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};

export default OfficeRightSidebar;
