import { WorkflowStepInspector } from './WorkflowStepInspector';
import React, { useState, useMemo } from 'react';
import { Tag, Button, Typography, Space, Tooltip } from 'antd';
import { SendOutlined, SlackOutlined, ThunderboltOutlined, ClockCircleOutlined, ToolOutlined, FileTextOutlined, ZoomInOutlined, ZoomOutOutlined, ReloadOutlined, ApartmentOutlined, DeleteOutlined } from '@ant-design/icons';

const { Text, Paragraph } = Typography;

import type { WorkflowCanvasStep, WorkflowCanvasSkill, WorkflowCanvasGraphProps } from './workflowGraphTypes';
export type { WorkflowCanvasStep, WorkflowCanvasSkill } from './workflowGraphTypes';

const AGENT_COLORS: Record<string, { bg: string; border: string; text: string; icon: string }> = {
  'software-architect': { bg: 'rgba(99, 102, 241, 0.15)', border: '#6366f1', text: '#a5b4fc', icon: '🏛️' },
  'qa-test-engineer': { bg: 'rgba(16, 185, 129, 0.15)', border: '#10b981', text: '#6ee7b7', icon: '🧪' },
  'release-security-reviewer': { bg: 'rgba(239, 68, 68, 0.15)', border: '#ef4444', text: '#fca5a5', icon: '🔒' },
  'backend-developer': { bg: 'rgba(14, 165, 233, 0.15)', border: '#0ea5e9', text: '#7dd3fc', icon: '⚙️' },
  'frontend-developer': { bg: 'rgba(245, 158, 11, 0.15)', border: '#f59e0b', text: '#fcd34d', icon: '🎨' },
  'ceo-orchestrator': { bg: 'rgba(168, 85, 247, 0.15)', border: '#a855f7', text: '#d8b4fe', icon: '👑' },
  'auto-agent': { bg: 'rgba(56, 189, 248, 0.15)', border: '#38bdf8', text: '#bae6fd', icon: '⚡' },
};

export const WorkflowCanvasGraph: React.FC<WorkflowCanvasGraphProps> = ({
  workflowName = 'Workflow DAG Pipeline',
  steps = [],
  channelBinding,
  skills = [],
  allowedMcps = [],
  onSelectStep,
  onDeleteStep,
  height = 540,
}) => {
  const [zoom, setZoom] = useState<number>(1);
  const [selectedStep, setSelectedStep] = useState<WorkflowCanvasStep | null>(null);
  const [detailModalVisible, setDetailModalVisible] = useState<boolean>(false);

  // Calculate DAG columns based on dependency depth
  const dagColumns = useMemo(() => {
    const depths: Record<string, number> = {};

    const getDepth = (key: string, visited = new Set<string>()): number => {
      if (visited.has(key)) return 0;
      visited.add(key);
      const st = steps.find((s) => s.key === key);
      if (!st || !st.depends_on || st.depends_on.length === 0) return 0;
      let maxParent = 0;
      for (const parentKey of st.depends_on) {
        maxParent = Math.max(maxParent, getDepth(parentKey, new Set(visited)) + 1);
      }
      return maxParent;
    };

    steps.forEach((s) => {
      depths[s.key] = getDepth(s.key);
    });

    const maxDepth = Math.max(0, ...Object.values(depths));
    const cols: WorkflowCanvasStep[][] = [];
    for (let i = 0; i <= maxDepth; i++) {
      cols.push(steps.filter((s) => (depths[s.key] ?? 0) === i));
    }
    return cols;
  }, [steps]);

  // Click handler
  const handleNodeClick = (step: WorkflowCanvasStep) => {
    setSelectedStep(step);
    setDetailModalVisible(true);
    if (onSelectStep) onSelectStep(step);
  };

  const isTelegram = channelBinding?.provider === 'telegram';
  const isSlack = channelBinding?.provider === 'slack';
  const channelName = channelBinding?.channel_id || 'Hermes_test';

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        background: '#090d13',
        borderRadius: '16px',
        border: '1px solid #30363d',
        overflow: 'hidden',
        boxShadow: '0 12px 36px rgba(0, 0, 0, 0.6)',
      }}
    >
      {/* Canvas Top Bar */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '12px 20px',
          background: '#0d1117',
          borderBottom: '1px solid #21262d',
          flexWrap: 'wrap',
          gap: '12px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <ApartmentOutlined style={{ color: '#38bdf8', fontSize: '18px' }} />
          <div>
            <div style={{ color: '#f0f6fc', fontWeight: 700, fontSize: '14px' }}>
              {workflowName}
            </div>
            <div style={{ color: '#8b949e', fontSize: '11px' }}>
              Multi-Agent DAG Execution Graph • {steps.length} Steps • {skills.length} Attached Skills
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {channelBinding && channelBinding.channel_id && (
            <Tag
              icon={isTelegram ? <SendOutlined /> : isSlack ? <SlackOutlined /> : <ThunderboltOutlined />}
              color={isTelegram ? 'blue' : isSlack ? 'gold' : 'green'}
              style={{ fontWeight: 600, borderRadius: '8px', padding: '3px 10px', fontSize: '12px' }}
            >
              Trigger: {channelBinding.provider?.toUpperCase()} #{channelName}
            </Tag>
          )}

          {allowedMcps && allowedMcps.length > 0 && (
            <Tag color="cyan" style={{ borderRadius: '8px', padding: '3px 8px' }}>
              <ToolOutlined /> {allowedMcps.join(', ')}
            </Tag>
          )}

          <Tag color="purple" style={{ borderRadius: '8px', padding: '3px 8px', fontWeight: 600 }}>
            ⚡ Dual HITL (Slack & Telegram)
          </Tag>

          {/* Zoom controls */}
          <Space size="small">
            <Button
              size="small"
              icon={<ZoomInOutlined />}
              onClick={() => setZoom((z) => Math.min(1.4, z + 0.1))}
              style={{ background: '#161b22', borderColor: '#30363d', color: '#c9d1d9' }}
            />
            <Button
              size="small"
              icon={<ZoomOutOutlined />}
              onClick={() => setZoom((z) => Math.max(0.6, z - 0.1))}
              style={{ background: '#161b22', borderColor: '#30363d', color: '#c9d1d9' }}
            />
            <Button
              size="small"
              icon={<ReloadOutlined />}
              onClick={() => setZoom(1)}
              style={{ background: '#161b22', borderColor: '#30363d', color: '#c9d1d9' }}
            >
              100%
            </Button>
          </Space>
        </div>
      </div>

      {/* Main Canvas Viewport with Cyber Grid Pattern */}
      <div
        style={{
          height,
          position: 'relative',
          overflow: 'auto',
          padding: '40px',
          backgroundColor: '#070a0f',
          backgroundImage:
            'radial-gradient(rgba(56, 189, 248, 0.12) 1px, transparent 1px), radial-gradient(rgba(255, 255, 255, 0.03) 1px, transparent 1px)',
          backgroundSize: '24px 24px',
          backgroundPosition: '0 0, 12px 12px',
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '50px',
            minWidth: 'max-content',
            transform: `scale(${zoom})`,
            transformOrigin: 'top left',
            transition: 'transform 0.15s ease-out',
          }}
        >
          {/* 1. Ingestion / Trigger Node */}
          <div
            style={{
              width: '240px',
              background: 'linear-gradient(145deg, #0f172a 0%, #1e1b4b 100%)',
              border: '2px solid #3b82f6',
              borderRadius: '14px',
              padding: '16px',
              boxShadow: '0 8px 24px rgba(59, 130, 246, 0.25)',
              position: 'relative',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
              <span style={{ fontSize: '18px' }}>{isTelegram ? '✈️' : isSlack ? '💬' : '⚡'}</span>
              <div>
                <Tag color="processing" style={{ fontWeight: 700, margin: 0, fontSize: '10px' }}>
                  DAG ENTRY TRIGGER
                </Tag>
                <div style={{ fontWeight: 800, color: '#f0f6fc', fontSize: '13px', marginTop: '2px' }}>
                  {isTelegram ? 'Telegram Channel Listener' : isSlack ? 'Slack Event Ingest' : 'Webhook / Cron Ingest'}
                </div>
              </div>
            </div>

            <div style={{ background: '#090d13', borderRadius: '8px', padding: '8px 10px', marginTop: '8px', border: '1px solid #30363d' }}>
              <div style={{ fontSize: '11px', color: '#8b949e' }}>Target Channel / Chat:</div>
              <div style={{ fontSize: '12px', color: '#38bdf8', fontWeight: 700, fontFamily: 'monospace' }}>
                #{channelName}
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '4px' }}>
                <span
                  style={{
                    display: 'inline-block',
                    width: '8px',
                    height: '8px',
                    borderRadius: '50%',
                    background: '#10b981',
                    boxShadow: '0 0 8px #10b981',
                  }}
                />
                <span style={{ fontSize: '10px', color: '#10b981', fontWeight: 600 }}>Active Auto-Trigger</span>
              </div>
            </div>

            {/* Connecting right arrow */}
            <div
              style={{
                position: 'absolute',
                right: '-36px',
                top: '50%',
                transform: 'translateY(-50%)',
                color: '#38bdf8',
                fontSize: '22px',
                fontWeight: 'bold',
              }}
            >
              ➔
            </div>
          </div>

          {/* 2. DAG Columns & Step Nodes */}
          {dagColumns.map((colSteps, colIdx) => (
            <div
              key={`col_${colIdx}`}
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: '24px',
                position: 'relative',
              }}
            >
              <div style={{ fontSize: '11px', fontWeight: 700, color: '#64748b', textAlign: 'center', textTransform: 'uppercase' }}>
                Stage #{colIdx + 1} ({colSteps.length} {colSteps.length === 1 ? 'Step' : 'Steps'})
              </div>

              {colSteps.map((step) => {
                const agColor = AGENT_COLORS[step.agent_id] || {
                  bg: 'rgba(56, 189, 248, 0.15)',
                  border: '#38bdf8',
                  text: '#38bdf8',
                  icon: '🤖',
                };
                const stepSkills = (step.skills || []).map((skId) => {
                  const found = skills.find((s) => s.id === skId);
                  return found ? found.name : skId;
                });

                return (
                  <div
                    key={step.key}
                    onClick={() => handleNodeClick(step)}
                    style={{
                      width: '260px',
                      background: '#161b22',
                      border: `1.5px solid ${agColor.border}`,
                      borderRadius: '14px',
                      padding: '14px',
                      cursor: 'pointer',
                      transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
                      boxShadow: '0 6px 18px rgba(0, 0, 0, 0.4)',
                      position: 'relative',
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.transform = 'translateY(-3px)';
                      e.currentTarget.style.boxShadow = `0 10px 24px ${agColor.border}44`;
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.transform = 'translateY(0)';
                      e.currentTarget.style.boxShadow = '0 6px 18px rgba(0, 0, 0, 0.4)';
                    }}
                  >
                    {/* Header */}
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
                      <Tag color="cyan" style={{ borderRadius: '6px', fontSize: '10px', margin: 0, fontWeight: 700 }}>
                        {step.key}
                      </Tag>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <Tag style={{ background: '#21262d', color: '#8b949e', border: 'none', fontSize: '10px', margin: 0 }}>
                          <ClockCircleOutlined /> {step.timeout_seconds || 300}s
                        </Tag>
                        {onDeleteStep && (
                          <Tooltip title="Delete Step from Workflow">
                            <Button type="text" size="small" danger
                              icon={<DeleteOutlined style={{ fontSize: '12px' }} />}
                              onClick={event => { event.stopPropagation(); onDeleteStep(step.key); }}
                              style={{ padding: '0 4px', height: '20px', minWidth: '20px' }} />
                          </Tooltip>
                        )}
                      </div>
                    </div>

                    {/* Step Title */}
                    <div style={{ color: '#f0f6fc', fontWeight: 700, fontSize: '13px', marginBottom: '8px', lineHeight: 1.3 }}>
                      {step.name}
                    </div>

                    {/* Assigned Agent */}
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px',
                        background: agColor.bg,
                        border: `1px solid ${agColor.border}55`,
                        borderRadius: '8px',
                        padding: '4px 8px',
                        marginBottom: '8px',
                      }}
                    >
                      <span style={{ fontSize: '14px' }}>{agColor.icon}</span>
                      <span style={{ fontSize: '11px', color: agColor.text, fontWeight: 600 }}>
                        {step.agent_id}
                      </span>
                    </div>

                    {/* MCP Servers Badges */}
                    {step.mcp_servers && step.mcp_servers.length > 0 && (
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', marginBottom: '6px' }}>
                        {step.mcp_servers.map((mcp) => (
                          <Tag
                            key={mcp}
                            color={mcp === 'github' ? 'purple' : mcp === 'telegram' ? 'blue' : 'default'}
                            style={{ fontSize: '10px', borderRadius: '4px', margin: 0, padding: '0 6px' }}
                          >
                            <ToolOutlined /> {mcp.toUpperCase()} MCP
                          </Tag>
                        ))}
                      </div>
                    )}

                    {/* Skills attached */}
                    {stepSkills.length > 0 && (
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', marginBottom: '6px' }}>
                        {stepSkills.map((skName, sIdx) => (
                          <Tag
                            key={sIdx}
                            color="gold"
                            style={{ fontSize: '10px', borderRadius: '4px', margin: 0, padding: '0 6px' }}
                          >
                            <FileTextOutlined /> {skName}
                          </Tag>
                        ))}
                      </div>
                    )}

                    {/* Prompt Snippet */}
                    <div
                      style={{
                        background: '#0d1117',
                        border: '1px solid #21262d',
                        borderRadius: '6px',
                        padding: '6px 8px',
                        fontSize: '11px',
                        color: '#8b949e',
                        fontFamily: 'monospace',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}
                      title={step.prompt_template}
                    >
                      {step.prompt_template}
                    </div>

                    {/* Depends On note */}
                    {step.depends_on && step.depends_on.length > 0 && (
                      <div style={{ fontSize: '10px', color: '#64748b', marginTop: '6px' }}>
                        ↳ Depends on: {step.depends_on.join(', ')}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          ))}

          {/* 3. Terminal Delivery Node */}
          <div
            style={{
              width: '230px',
              background: 'linear-gradient(145deg, #064e3b 0%, #022c22 100%)',
              border: '2px solid #10b981',
              borderRadius: '14px',
              padding: '16px',
              boxShadow: '0 8px 24px rgba(16, 185, 129, 0.25)',
              position: 'relative',
            }}
          >
            {/* Connecting left arrow */}
            <div
              style={{
                position: 'absolute',
                left: '-32px',
                top: '50%',
                transform: 'translateY(-50%)',
                color: '#10b981',
                fontSize: '22px',
                fontWeight: 'bold',
              }}
            >
              ➔
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
              <span style={{ fontSize: '20px' }}>🚀</span>
              <div>
                <Tag color="success" style={{ fontWeight: 700, margin: 0, fontSize: '10px' }}>
                  WORKFLOW COMPLETE
                </Tag>
                <div style={{ fontWeight: 800, color: '#f0f6fc', fontSize: '13px', marginTop: '2px' }}>
                  Final Dispatch & Delivery
                </div>
              </div>
            </div>

            <div style={{ background: '#090d13', borderRadius: '8px', padding: '8px 10px', marginTop: '8px', border: '1px solid #30363d' }}>
              <div style={{ fontSize: '11px', color: '#8b949e' }}>Delivery Destination:</div>
              <div style={{ fontSize: '12px', color: '#34d399', fontWeight: 700 }}>
                {channelBinding && channelBinding.channel_id ? `Publish to #${channelBinding.channel_id}` : 'Platform Audit & Sandbox Log'}
              </div>
              <div style={{ fontSize: '10px', color: '#94a3b8', marginTop: '4px' }}>
                Mode: {channelBinding?.notify_mode || 'ON_COMPLETE'}
              </div>
            </div>
          </div>
        </div>
      </div>

      <WorkflowStepInspector onDeleteStep={onDeleteStep} selectedStep={selectedStep} detailModalVisible={detailModalVisible} setDetailModalVisible={setDetailModalVisible} />
    </div>
  );
};
