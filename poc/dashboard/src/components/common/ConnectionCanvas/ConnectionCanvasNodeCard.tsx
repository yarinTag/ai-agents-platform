import React from 'react';
import { DownOutlined, RightOutlined } from '@ant-design/icons';
import { CanvasBadgeItem, CanvasLeafNode } from './connectionCanvasTypes';

export type NodeHighlightState = 'none' | 'selected' | 'upstream' | 'downstream' | 'dimmed';

export interface ConnectionCanvasNodeCardProps<T = unknown> {
  node: CanvasLeafNode<T>;
  expanded: boolean;
  showLinks: boolean;
  compactMode?: boolean;
  highlightState?: NodeHighlightState;
  expandTooltip: string;
  collapseTooltip: string;
  onToggleExpand: (nodeId: string) => void;
  onClickNode?: (node: CanvasLeafNode<T>) => void;
  onClickStage?: (node: CanvasLeafNode<T>, stageItemId: string) => void;
  onHoverNode?: (nodeId: string | null) => void;
}

const BADGE_PALETTE: Record<string, { bg: string; border: string; text: string }> = {
  blue: { bg: 'rgba(59, 130, 246, 0.14)', border: 'rgba(59, 130, 246, 0.45)', text: '#93c5fd' },
  geekblue: { bg: 'rgba(99, 102, 241, 0.14)', border: 'rgba(99, 102, 241, 0.45)', text: '#a5b4fc' },
  purple: { bg: 'rgba(168, 85, 247, 0.14)', border: 'rgba(168, 85, 247, 0.45)', text: '#d8b4fe' },
  cyan: { bg: 'rgba(6, 182, 212, 0.14)', border: 'rgba(6, 182, 212, 0.45)', text: '#67e8f9' },
  green: { bg: 'rgba(16, 185, 129, 0.14)', border: 'rgba(16, 185, 129, 0.45)', text: '#6ee7b7' },
  success: { bg: 'rgba(16, 185, 129, 0.16)', border: 'rgba(16, 185, 129, 0.5)', text: '#34d399' },
  gold: { bg: 'rgba(245, 158, 11, 0.14)', border: 'rgba(245, 158, 11, 0.45)', text: '#fcd34d' },
  orange: { bg: 'rgba(249, 115, 22, 0.14)', border: 'rgba(249, 115, 22, 0.45)', text: '#fdba74' },
  default: { bg: '#21262d', border: '#30363d', text: '#8b949e' },
};

export const ConnectorEdge: React.FC<{ color?: string; width?: number }> = ({
  color = '#38bdf8',
  width = 20,
}) => (
  <div style={{ display: 'flex', alignItems: 'center', width, flexShrink: 0 }}>
    <div style={{ height: 2, width: '100%', background: color, opacity: 0.75 }} />
    <div style={{ width: 5, height: 5, borderRadius: '50%', background: color, flexShrink: 0 }} />
  </div>
);

export const ContainedTag: React.FC<{ badge: CanvasBadgeItem; maxWidth?: number | string }> = ({
  badge,
  maxWidth = '100%',
}) => {
  const pal = BADGE_PALETTE[badge.color || 'default'] || BADGE_PALETTE.default;
  return (
    <span
      title={badge.tooltip || badge.label}
      style={{
        fontSize: 10, lineHeight: '16px', borderRadius: 5, padding: '1px 6px', maxWidth,
        background: pal.bg, border: `1px solid ${pal.border}`, color: pal.text,
        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
        display: 'inline-block', verticalAlign: 'middle', boxSizing: 'border-box',
      }}
    >
      {badge.icon && <span style={{ marginRight: 4 }}>{badge.icon}</span>}
      {badge.label}
    </span>
  );
};

function ConnectionCanvasNodeCardInner<T = unknown>({
  node, expanded, showLinks, compactMode = false, highlightState = 'none',
  expandTooltip, collapseTooltip, onToggleExpand, onClickNode, onClickStage, onHoverNode,
}: ConnectionCanvasNodeCardProps<T>) {
  const isActive = node.isActive !== false;
  const incoming = node.incomingBadges || [];
  const outgoing = node.outgoingBadges || [];
  const stages = node.stages || [];
  const hasStages = stages.length > 0;

  let borderColor = node.accentColor || (isActive ? '#8b5cf6' : '#30363d');
  let boxShadow = isActive ? '0 4px 14px rgba(0, 0, 0, 0.35)' : '0 2px 8px rgba(0, 0, 0, 0.25)';
  let opacity = 1;

  if (highlightState === 'selected') {
    borderColor = '#38bdf8';
    boxShadow = '0 0 0 2px rgba(56, 189, 248, 0.45), 0 8px 24px rgba(56, 189, 248, 0.3)';
  } else if (highlightState === 'downstream') {
    borderColor = '#10b981';
    boxShadow = '0 0 0 2px rgba(16, 185, 129, 0.4), 0 6px 20px rgba(16, 185, 129, 0.25)';
  } else if (highlightState === 'upstream') {
    borderColor = '#f59e0b';
    boxShadow = '0 0 0 2px rgba(245, 158, 11, 0.4), 0 6px 20px rgba(245, 158, 11, 0.25)';
  } else if (highlightState === 'dimmed') {
    opacity = 0.35;
  }

  const cardWidth = compactMode ? 255 : 320;

  return (
    <div
      onMouseEnter={() => onHoverNode?.(node.id)}
      onMouseLeave={() => onHoverNode?.(null)}
      style={{ display: 'flex', alignItems: 'center', gap: 0, opacity, transition: 'opacity 0.15s ease', contain: 'layout style' }}
    >
      {/* 1. Left Incoming Badges Box */}
      {showLinks && !compactMode && incoming.length > 0 && (
        <>
          <div style={{ background: '#0d1117', border: '1px solid #1d4ed8', borderRadius: 10, padding: '7px 9px', width: 155, boxSizing: 'border-box', overflow: 'hidden', flexShrink: 0 }}>
            {node.incomingTitle && (
              <div style={{ fontSize: 9, fontWeight: 700, color: '#60a5fa', textTransform: 'uppercase', marginBottom: 4, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {node.incomingTitle}
              </div>
            )}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 3, minWidth: 0 }}>
              {incoming.slice(0, 4).map((b) => (
                <ContainedTag key={b.id} badge={b} maxWidth="100%" />
              ))}
            </div>
          </div>
          <ConnectorEdge color="#3b82f6" width={18} />
        </>
      )}

      {/* 2. Center Main Node Card */}
      <div
        style={{
          background: '#161b22', border: `1.5px solid ${borderColor}`, borderRadius: 11,
          padding: compactMode ? '9px 11px' : '11px 13px',
          width: expanded && hasStages ? 'auto' : cardWidth,
          minWidth: expanded && hasStages ? 360 : cardWidth,
          maxWidth: expanded && hasStages ? 860 : cardWidth,
          boxSizing: 'border-box', overflow: 'hidden', flexShrink: 0, boxShadow,
        }}
      >
        {(highlightState === 'upstream' || highlightState === 'downstream') && (
          <div style={{ fontSize: 9, fontWeight: 700, color: highlightState === 'downstream' ? '#34d399' : '#fbbf24', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.4px' }}>
            {highlightState === 'downstream' ? '➔ Downstream Connected Skill' : '⬅ Upstream Input Skill'}
          </div>
        )}

        {/* Header Bar */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 4, flexWrap: 'wrap', marginBottom: 6 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 5, minWidth: 0 }}>
            {node.statusLabel && (
              <>
                <span style={{ width: 7, height: 7, borderRadius: '50%', display: 'inline-block', flexShrink: 0, background: isActive ? '#10b981' : '#6e7681' }} />
                <ContainedTag badge={{ id: 'status', label: node.statusLabel, color: isActive ? 'success' : 'default' }} />
              </>
            )}
            {node.versionBadge && <ContainedTag badge={{ id: 'ver', label: node.versionBadge, color: 'default' }} />}
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            {hasStages && node.stagesButtonLabel && (
              <button
                type="button"
                title={expanded ? collapseTooltip : expandTooltip}
                onClick={(e) => { e.stopPropagation(); onToggleExpand(node.id); }}
                style={{
                  height: 21, fontSize: 10, padding: '0 6px', borderRadius: 5, cursor: 'pointer',
                  display: 'inline-flex', alignItems: 'center', gap: 4,
                  background: expanded ? '#8b5cf6' : '#21262d', border: `1px solid ${expanded ? '#8b5cf6' : '#30363d'}`, color: '#f0f6fc',
                }}
              >
                {expanded ? <DownOutlined style={{ fontSize: 9 }} /> : <RightOutlined style={{ fontSize: 9 }} />}
                <span>{node.stagesButtonLabel}</span>
              </button>
            )}
            {(node.actions || []).map((act) => (
              <button
                key={act.key}
                type="button"
                title={act.tooltip}
                onClick={(e) => { e.stopPropagation(); act.onClick(); }}
                style={{
                  height: 21, padding: '0 6px', borderRadius: 5, cursor: 'pointer', display: 'inline-flex',
                  alignItems: 'center', background: '#21262d', border: '1px solid #30363d', color: act.color || '#c9d1d9',
                }}
              >
                {act.icon}
              </button>
            ))}
          </div>
        </div>

        {/* Body: Title + Subtitle + Connected Badges */}
        <div onClick={() => onClickNode?.(node)} style={{ cursor: onClickNode ? 'pointer' : 'default', minWidth: 0 }}>
          <div title={node.title} style={{ color: '#f0f6fc', fontWeight: 700, fontSize: compactMode ? 12 : 13, lineHeight: 1.3, display: 'flex', alignItems: 'flex-start', gap: 6, minWidth: 0 }}>
            {node.titleIcon && <span style={{ flexShrink: 0, marginTop: 1 }}>{node.titleIcon}</span>}
            <span style={{ wordBreak: 'break-word', overflowWrap: 'anywhere', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
              {node.title}
            </span>
          </div>

          {node.subtitle && (
            <div title={node.subtitle} style={{ color: '#8b949e', fontSize: 11, lineHeight: 1.3, marginTop: 3, wordBreak: 'break-word', overflowWrap: 'anywhere', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
              {node.subtitle}
            </div>
          )}

          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 6, minWidth: 0 }}>
            {node.ownerBadge && (
              <ContainedTag badge={{ id: 'owner', label: node.ownerBadge.label, icon: node.ownerBadge.icon, color: 'cyan' }} maxWidth="100%" />
            )}
            {compactMode && showLinks && outgoing.slice(0, 3).map((b) => (
              <ContainedTag key={b.id} badge={b} maxWidth="100%" />
            ))}
            {compactMode && showLinks && outgoing.length > 3 && (
              <ContainedTag
                badge={{
                  id: 'more', label: `+${outgoing.length - 3} more`, color: 'green',
                  tooltip: outgoing.slice(3).map((x) => x.label).join(', '),
                }}
              />
            )}
          </div>
        </div>

        {/* Expanded Inner Pipeline Stages */}
        {expanded && hasStages && (
          <div style={{ marginTop: 9, paddingTop: 9, borderTop: '1px dashed #30363d', overflowX: 'auto', maxWidth: '100%' }}>
            {node.stagesTitle && (
              <div style={{ fontSize: 9, fontWeight: 700, color: '#a5b4fc', textTransform: 'uppercase', marginBottom: 6 }}>
                {node.stagesTitle}
              </div>
            )}
            <div style={{ display: 'flex', alignItems: 'stretch', gap: 8 }}>
              {stages.map((stage, stageIdx) => (
                <React.Fragment key={stage.id}>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 5, background: '#090d13', border: '1px solid #21262d', borderRadius: 8, padding: 7, width: 190, minWidth: 190, maxWidth: 190, boxSizing: 'border-box', overflow: 'hidden', flexShrink: 0 }}>
                    <div style={{ fontSize: 9, fontWeight: 700, color: '#6e7681', textTransform: 'uppercase', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {stage.label}
                    </div>
                    {stage.items.map((item) => (
                      <div
                        key={item.id}
                        onClick={() => onClickStage?.(node, item.id)}
                        style={{ background: '#161b22', border: '1px solid #30363d', borderLeft: `3px solid ${item.accentColor || '#38bdf8'}`, borderRadius: 6, padding: '5px 7px', cursor: onClickStage ? 'pointer' : 'default', boxSizing: 'border-box', overflow: 'hidden', minWidth: 0 }}
                      >
                        <div title={item.title} style={{ color: '#f0f6fc', fontSize: 11, fontWeight: 600, lineHeight: 1.25, wordBreak: 'break-word', overflowWrap: 'anywhere', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                          {item.title}
                        </div>
                        {item.subtitle && (
                          <div title={item.subtitle} style={{ color: '#38bdf8', fontSize: 10, marginTop: 2, fontFamily: 'monospace', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {item.subtitle}
                          </div>
                        )}
                        {item.meta && (
                          <div title={item.meta} style={{ color: '#8b949e', fontSize: 9, marginTop: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {item.meta}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                  {stageIdx < stages.length - 1 && (
                    <div style={{ display: 'flex', alignItems: 'center', color: '#38bdf8', fontWeight: 700, fontSize: 13 }}>➔</div>
                  )}
                </React.Fragment>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* 3. Right Outgoing Badges Box (Standard non-compact mode) */}
      {showLinks && !compactMode && outgoing.length > 0 && (
        <>
          <ConnectorEdge color="#10b981" width={18} />
          <div style={{ background: '#0d1117', border: '1px solid #059669', borderRadius: 10, padding: '7px 9px', width: 210, boxSizing: 'border-box', overflow: 'hidden', flexShrink: 0, display: 'flex', flexDirection: 'column', gap: 4 }}>
            {node.outgoingTitle && (
              <div style={{ fontSize: 9, fontWeight: 700, color: '#34d399', textTransform: 'uppercase', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {node.outgoingTitle}
              </div>
            )}
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 3, minWidth: 0 }}>
              {outgoing.slice(0, 6).map((b) => (
                <ContainedTag key={b.id} badge={b} maxWidth="100%" />
              ))}
              {outgoing.length > 6 && (
                <ContainedTag
                  badge={{
                    id: 'more_out', label: `+${outgoing.length - 6} more`, color: 'green',
                    tooltip: outgoing.slice(6).map((x) => x.label).join(', '),
                  }}
                />
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

export const ConnectionCanvasNodeCard = React.memo(
  ConnectionCanvasNodeCardInner
) as typeof ConnectionCanvasNodeCardInner;
