import React, { useState, useMemo, useRef, useCallback, useEffect } from 'react';
import { Input, Select, Button, Switch, Tag, Space, Empty, Spin } from 'antd';
import {
  SearchOutlined, PlusOutlined, MinusOutlined, AimOutlined, ReloadOutlined,
  NodeExpandOutlined, NodeCollapseOutlined, DownOutlined, RightOutlined,
} from '@ant-design/icons';
import {
  CanvasGroupNode, CanvasLeafNode, CanvasLegendItem, CanvasRootNode, ConnectionCanvasLabels,
} from './connectionCanvasTypes';
import { ConnectionCanvasNodeCard, NodeHighlightState } from './ConnectionCanvasNodeCard';

export interface ConnectionCanvasDiagramProps<T = unknown> {
  rootNode: CanvasRootNode;
  groups: CanvasGroupNode<T>[];
  legend?: CanvasLegendItem[];
  labels: ConnectionCanvasLabels;
  loading?: boolean;
  showStatusFilter?: boolean;
  onRefresh?: () => void;
  onClickLeaf?: (node: CanvasLeafNode<T>) => void;
  onClickStage?: (node: CanvasLeafNode<T>, stageItemId: string) => void;
}

export function ConnectionCanvasDiagram<T = unknown>({
  rootNode, groups, legend = [], labels, loading = false, showStatusFilter = true,
  onRefresh, onClickLeaf, onClickStage,
}: ConnectionCanvasDiagramProps<T>) {
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [groupFilter, setGroupFilter] = useState<string>('ALL');
  const [statusFilter, setStatusFilter] = useState<'all' | 'active' | 'inactive'>('all');
  const [expandedNodeIds, setExpandedNodeIds] = useState<Record<string, boolean>>({});
  const [collapsedGroupIds, setCollapsedGroupIds] = useState<Record<string, boolean>>({});
  const [showLinks, setShowLinks] = useState<boolean>(true);
  const [hoveredNodeId, setHoveredNodeIdRaw] = useState<string | null>(null);
  const hoverTimerRef = useRef<number | null>(null);
  const setHoveredNodeId = useCallback((id: string | null) => {
    if (hoverTimerRef.current !== null) window.clearTimeout(hoverTimerRef.current);
    if (dragStateRef.current.active) return;
    hoverTimerRef.current = window.setTimeout(() => setHoveredNodeIdRaw(id), id ? 90 : 30);
  }, []);

  const viewportRef = useRef<HTMLDivElement | null>(null);
  const canvasLayerRef = useRef<HTMLDivElement | null>(null);
  const topZoomBtnRef = useRef<HTMLSpanElement | null>(null);
  const hudZoomBtnRef = useRef<HTMLSpanElement | null>(null);
  const transformRef = useRef<{ x: number; y: number; zoom: number }>({ x: 0, y: 0, zoom: 1 });
  const dragStateRef = useRef<{ active: boolean; startX: number; startY: number }>({
    active: false, startX: 0, startY: 0,
  });
  const rafIdRef = useRef<number | null>(null);

  useEffect(() => {
    setCollapsedGroupIds((prev) => {
      const next = { ...prev };
      let changed = false;
      groups.forEach((g) => {
        if (next[g.id] === undefined && g.defaultCollapsed) {
          next[g.id] = true;
          changed = true;
        }
      });
      return changed ? next : prev;
    });
  }, [groups]);

  const applyTransformToDom = useCallback(() => {
    const { x, y, zoom } = transformRef.current;
    if (canvasLayerRef.current) {
      canvasLayerRef.current.style.transform = `translate3d(${x}px, ${y}px, 0) scale(${zoom})`;
    }
    const pctText = `${Math.round(zoom * 100)}%`;
    if (topZoomBtnRef.current) topZoomBtnRef.current.textContent = pctText;
    if (hudZoomBtnRef.current) hudZoomBtnRef.current.textContent = pctText;
  }, []);

  const scheduleTransformUpdate = useCallback(() => {
    if (rafIdRef.current !== null) return;
    rafIdRef.current = window.requestAnimationFrame(() => {
      rafIdRef.current = null;
      applyTransformToDom();
    });
  }, [applyTransformToDom]);

  const zoomIn = useCallback(() => {
    transformRef.current.zoom = Math.min(2.0, Number((transformRef.current.zoom + 0.12).toFixed(2)));
    applyTransformToDom();
  }, [applyTransformToDom]);

  const zoomOut = useCallback(() => {
    transformRef.current.zoom = Math.max(0.35, Number((transformRef.current.zoom - 0.12).toFixed(2)));
    applyTransformToDom();
  }, [applyTransformToDom]);

  const resetZoomAndPan = useCallback(() => {
    transformRef.current = { x: 0, y: 0, zoom: 1 };
    applyTransformToDom();
  }, [applyTransformToDom]);

  const handleMouseDown = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    const target = e.target as HTMLElement;
    if (target.closest('button, input, a, .ant-select, .ant-switch, [role="button"]')) return;
    dragStateRef.current = {
      active: true,
      startX: e.clientX - transformRef.current.x,
      startY: e.clientY - transformRef.current.y,
    };
    if (viewportRef.current) viewportRef.current.style.cursor = 'grabbing';
  }, []);

  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if (!dragStateRef.current.active) return;
    transformRef.current.x = e.clientX - dragStateRef.current.startX;
    transformRef.current.y = e.clientY - dragStateRef.current.startY;
    scheduleTransformUpdate();
  }, [scheduleTransformUpdate]);

  const handleMouseUp = useCallback(() => {
    if (!dragStateRef.current.active) return;
    dragStateRef.current.active = false;
    if (viewportRef.current) viewportRef.current.style.cursor = 'grab';
  }, []);

  // React attaches wheel listeners as passive, so preventDefault must use a native non-passive listener.
  useEffect(() => {
    const el = viewportRef.current;
    if (!el) return undefined;
    const onWheel = (e: WheelEvent) => {
      if (!(e.ctrlKey || e.metaKey || e.altKey)) return;
      e.preventDefault();
      const delta = e.deltaY < 0 ? 0.08 : -0.08;
      transformRef.current.zoom = Math.min(2.0, Math.max(0.35, Number((transformRef.current.zoom + delta).toFixed(2))));
      scheduleTransformUpdate();
    };
    el.addEventListener('wheel', onWheel, { passive: false });
    return () => el.removeEventListener('wheel', onWheel);
  }, [scheduleTransformUpdate]);

  const filteredGroups = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    return groups
      .filter((g) => groupFilter === 'ALL' || g.id === groupFilter)
      .map((g) => {
        const matchingChildren = g.children.filter((leaf) => {
          if (statusFilter === 'active' && leaf.isActive === false) return false;
          if (statusFilter === 'inactive' && leaf.isActive !== false) return false;
          if (!q) return true;
          const haystacks: string[] = [
            leaf.title, leaf.subtitle || '', leaf.ownerBadge?.label || '', g.title,
            ...(g.searchKeywords || []),
            ...(leaf.incomingBadges || []).map((b) => b.label),
            ...(leaf.outgoingBadges || []).map((b) => b.label),
          ];
          return haystacks.some((h) => h.toLowerCase().includes(q));
        });
        return { ...g, children: matchingChildren };
      })
      .filter((g) => groupFilter !== 'ALL' || !q || g.children.length > 0 || g.title.toLowerCase().includes(q));
  }, [groups, groupFilter, statusFilter, searchQuery]);

  const connectionMap = useMemo(() => {
    const map = new Map<string, { to: Set<string>; from: Set<string> }>();
    groups.forEach((g) => {
      g.children.forEach((c) => {
        if (!map.has(c.id)) map.set(c.id, { to: new Set(), from: new Set() });
        const entry = map.get(c.id)!;
        (c.connectedToIds || []).forEach((tid) => {
          entry.to.add(tid);
          if (!map.has(tid)) map.set(tid, { to: new Set(), from: new Set() });
          map.get(tid)!.from.add(c.id);
        });
        (c.connectedFromIds || []).forEach((fid) => {
          entry.from.add(fid);
          if (!map.has(fid)) map.set(fid, { to: new Set(), from: new Set() });
          map.get(fid)!.to.add(c.id);
        });
      });
    });
    return map;
  }, [groups]);

  const getHighlightState = useCallback(
    (nodeId: string): NodeHighlightState => {
      if (!hoveredNodeId) return 'none';
      if (nodeId === hoveredNodeId) return 'selected';
      const activeConn = connectionMap.get(hoveredNodeId);
      if (!activeConn || (activeConn.to.size === 0 && activeConn.from.size === 0)) return 'none';
      if (activeConn.to.has(nodeId)) return 'downstream';
      if (activeConn.from.has(nodeId)) return 'upstream';
      return 'dimmed';
    },
    [hoveredNodeId, connectionMap]
  );

  const expandableIds = useMemo(
    () => groups.flatMap((g) => g.children.filter((c) => (c.stages || []).length > 0).map((c) => c.id)),
    [groups]
  );

  const areAllExpanded = expandableIds.length > 0 && expandableIds.every((id) => expandedNodeIds[id]);

  const handleToggleAll = useCallback(() => {
    if (areAllExpanded) {
      setExpandedNodeIds({});
    } else {
      const next: Record<string, boolean> = {};
      expandableIds.forEach((id) => { next[id] = true; });
      setExpandedNodeIds(next);
    }
  }, [areAllExpanded, expandableIds]);

  const handleToggleNodeExpand = useCallback((nodeId: string) => {
    setExpandedNodeIds((prev) => ({ ...prev, [nodeId]: !prev[nodeId] }));
  }, []);

  const toggleGroupCollapse = useCallback((groupId: string) => {
    setCollapsedGroupIds((prev) => ({ ...prev, [groupId]: !prev[groupId] }));
  }, []);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {/* Top Toolbar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 10, background: '#0d1117', border: '1px solid #30363d', borderRadius: 12, padding: '10px 14px' }}>
        <Space size={8} wrap>
          <Input
            allowClear
            prefix={<SearchOutlined style={{ color: '#8b949e' }} />}
            placeholder={labels.searchPlaceholder}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{ width: 270, background: '#161b22', borderColor: '#30363d', color: '#f0f6fc' }}
          />
          <Select
            value={groupFilter}
            onChange={(val) => {
              setGroupFilter(val);
              if (val !== 'ALL') setCollapsedGroupIds((prev) => ({ ...prev, [val]: false }));
            }}
            style={{ minWidth: 195, maxWidth: 260 }}
            options={[
              { value: 'ALL', label: `${labels.allGroupsLabel} (${groups.length})` },
              ...groups.map((g) => ({ value: g.id, label: `${g.title} (${g.children.length})` })),
            ]}
          />
          {showStatusFilter && (
            <Select
              value={statusFilter}
              onChange={setStatusFilter}
              style={{ minWidth: 135 }}
              options={[
                { value: 'all', label: labels.statusAllLabel },
                { value: 'active', label: labels.statusActiveLabel },
                { value: 'inactive', label: labels.statusInactiveLabel },
              ]}
            />
          )}
        </Space>
        <Space size={8} wrap>
          {expandableIds.length > 0 && (
            <Button size="small" icon={areAllExpanded ? <NodeCollapseOutlined /> : <NodeExpandOutlined />} onClick={handleToggleAll} style={{ background: '#161b22', borderColor: '#30363d', color: '#c9d1d9' }}>
              {areAllExpanded ? labels.collapseAllLabel : labels.expandAllLabel}
            </Button>
          )}
          <Space size={5}>
            <span style={{ color: '#8b949e', fontSize: 12 }}>{labels.showLinksLabel}:</span>
            <Switch size="small" checked={showLinks} onChange={setShowLinks} />
          </Space>
          <Space size={4}>
            <Button size="small" title="Zoom Out (-)" icon={<MinusOutlined />} onClick={zoomOut} style={{ background: '#161b22', borderColor: '#30363d', color: '#c9d1d9' }} />
            <Button size="small" title="Reset Zoom (100%)" onClick={resetZoomAndPan} style={{ background: '#161b22', borderColor: '#30363d', color: '#c9d1d9', minWidth: 52, fontWeight: 600 }}>
              <span ref={topZoomBtnRef}>100%</span>
            </Button>
            <Button size="small" title="Zoom In (+)" icon={<PlusOutlined />} onClick={zoomIn} style={{ background: '#161b22', borderColor: '#30363d', color: '#c9d1d9' }} />
          </Space>
          {onRefresh && (
            <Button size="small" icon={<ReloadOutlined spin={loading} />} onClick={onRefresh} style={{ background: '#161b22', borderColor: '#30363d', color: '#c9d1d9' }}>
              {labels.refreshLabel}
            </Button>
          )}
        </Space>
      </div>
      {/* Legend Bar */}
      {legend.length > 0 && (
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8, padding: '6px 12px', background: '#090d13', border: '1px solid #21262d', borderRadius: 8 }}>
          <Space size={8} wrap>
            {legend.map((item, idx) => (
              <React.Fragment key={item.label}>
                <Tag color={item.color} style={{ margin: 0, fontSize: 11 }}>{item.icon ? `${item.icon} ` : ''}{item.label}</Tag>
                {idx < legend.length - 1 && <span style={{ color: '#484f58' }}>➔</span>}
              </React.Fragment>
            ))}
          </Space>
          <span style={{ color: '#6e7681', fontSize: 11 }}>{labels.panHint}</span>
        </div>
      )}
      {/* High-Performance GPU Pan/Zoom Viewport */}
      <Spin spinning={loading}>
        <div style={{ position: 'relative' }}>
          <div
            ref={viewportRef}
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onMouseLeave={handleMouseUp}
            style={{
              minHeight: 600, maxHeight: '76vh', overflow: 'auto', position: 'relative',
              padding: '32px 36px', backgroundColor: '#070a0f',
              backgroundImage: 'radial-gradient(rgba(56, 189, 248, 0.13) 1px, transparent 1px)',
              backgroundSize: '24px 24px', borderRadius: 14, border: '1px solid #30363d',
              cursor: 'grab', userSelect: 'none',
            }}
          >
            {filteredGroups.length === 0 ? (
              <div style={{ padding: '80px 0' }}>
                <Empty description={<span style={{ color: '#8b949e' }}>{labels.emptyLabel}</span>} />
              </div>
            ) : (
              <div
                ref={canvasLayerRef}
                style={{
                  display: 'flex', alignItems: 'center', gap: 0, minWidth: 'max-content',
                  transform: 'translate3d(0px, 0px, 0) scale(1)', transformOrigin: 'top left', willChange: 'transform',
                }}
              >
                <div style={{ width: 245, boxSizing: 'border-box', overflow: 'hidden', background: 'linear-gradient(145deg, #1e1b4b 0%, #0f172a 100%)', border: `2px solid ${rootNode.accentColor || '#a855f7'}`, borderRadius: 16, padding: 15, flexShrink: 0 }}>
                  <Tag color="purple" style={{ fontWeight: 700, fontSize: 10, marginBottom: 6 }}>{rootNode.tag}</Tag>
                  <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, marginBottom: 6, minWidth: 0 }}>
                    {rootNode.icon && <span style={{ flexShrink: 0, marginTop: 2 }}>{rootNode.icon}</span>}
                    <div title={rootNode.title} style={{ color: '#f0f6fc', fontWeight: 800, fontSize: 15, lineHeight: 1.25, wordBreak: 'break-word', overflowWrap: 'anywhere' }}>
                      {rootNode.title}
                    </div>
                  </div>
                  {rootNode.subtitle && (
                    <div title={rootNode.subtitle} style={{ color: '#38bdf8', fontSize: 11, fontFamily: 'monospace', marginBottom: 10, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {rootNode.subtitle}
                    </div>
                  )}
                  {rootNode.metrics.length > 0 && (
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6, background: '#090d13', padding: 8, borderRadius: 8, border: '1px solid #30363d' }}>
                      {rootNode.metrics.map((m, idx) => (
                        <div key={idx} style={{ minWidth: 0, overflow: 'hidden' }}>
                          <div style={{ fontSize: 9, color: '#8b949e', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{m.label}</div>
                          <div style={{ fontSize: 13, fontWeight: 700, color: m.color || '#f0f6fc' }}>{m.value}</div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
                <div style={{ width: 28, height: 2, background: rootNode.accentColor || '#a855f7', flexShrink: 0 }} />
                <div style={{ display: 'flex', flexDirection: 'column', gap: 24, borderLeft: filteredGroups.length > 1 ? '2px solid #58a6ff88' : 'none', paddingLeft: 24 }}>
                  {filteredGroups.map((group) => {
                    const groupBorder = group.accentColor || '#3b82f6';
                    const isGroupCollapsed = Boolean(collapsedGroupIds[group.id]) && groupFilter === 'ALL' && !searchQuery.trim();
                    const stageCols: Array<{ index: number; label: string; items: CanvasLeafNode<T>[] }> = [];
                    if (group.useStageColumnsLayout && group.children.length > 0) {
                      const colMap = new Map<number, { label: string; items: CanvasLeafNode<T>[] }>();
                      group.children.forEach((ch) => {
                        const idx = ch.flowStageIndex ?? 0;
                        if (!colMap.has(idx)) {
                          colMap.set(idx, { label: ch.flowStageLabel || `Stage #${idx + 1}`, items: [] });
                        }
                        colMap.get(idx)!.items.push(ch);
                      });
                      Array.from(colMap.keys()).sort((a, b) => a - b).forEach((k) => stageCols.push({ index: k, ...colMap.get(k)! }));
                    }
                    return (
                      <div key={group.id} style={{ display: 'flex', alignItems: 'center', gap: 0, position: 'relative' }}>
                        <div style={{ position: 'absolute', left: -24, width: 24, height: 2, background: groupBorder }} />
                        {/* LEVEL 2: Group Node Card */}
                        <div style={{ width: 250, boxSizing: 'border-box', overflow: 'hidden', background: 'linear-gradient(145deg, #0f172a 0%, #161b22 100%)', border: `2px solid ${groupBorder}`, borderRadius: 14, padding: 13, flexShrink: 0 }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 6, flexWrap: 'wrap', marginBottom: 6 }}>
                            <Tag color={group.badgeColor || 'blue'} style={{ margin: 0, fontSize: 10, fontWeight: 700 }}>{group.badgeLabel}</Tag>
                            {group.statusBadge && <Tag color="purple" style={{ margin: 0, fontSize: 10 }}>{group.statusBadge}</Tag>}
                          </div>
                          <div title={group.title} style={{ color: '#f0f6fc', fontWeight: 700, fontSize: 14, lineHeight: 1.3, marginBottom: 4, wordBreak: 'break-word', overflowWrap: 'anywhere' }}>
                            {group.icon && <span style={{ marginRight: 6 }}>{group.icon}</span>}
                            {group.title}
                          </div>
                          {group.description && (
                            <div title={group.description} style={{ color: '#8b949e', fontSize: 11, lineHeight: 1.3, marginBottom: 8, wordBreak: 'break-word', overflowWrap: 'anywhere', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                              {group.description}
                            </div>
                          )}
                          {(group.metrics || []).map((m, idx) => (
                            <div key={idx} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 6, background: '#090d13', border: '1px solid #21262d', borderRadius: 6, padding: '4px 8px', fontSize: 11, marginBottom: 6, minWidth: 0, overflow: 'hidden' }}>
                              <span style={{ color: '#8b949e', flexShrink: 0 }}>{m.icon && <span style={{ marginRight: 4 }}>{m.icon}</span>}{m.label}:</span>
                              <span style={{ color: m.color || '#10b981', fontWeight: 700, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{m.value}</span>
                            </div>
                          ))}
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 6, marginTop: 4 }}>
                            {group.footerText && <span style={{ color: '#8b949e', fontSize: 10 }}>{group.footerText}</span>}
                            <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                              {group.footerAction && (
                                <Button size="small" type="link" icon={group.footerAction.icon} onClick={group.footerAction.onClick} style={{ padding: 0, height: 'auto', fontSize: 11 }}>
                                  {group.footerAction.label}
                                </Button>
                              )}
                              {group.children.length > 0 && (
                                <button
                                  type="button"
                                  onClick={() => toggleGroupCollapse(group.id)}
                                  style={{ height: 20, fontSize: 10, padding: '0 6px', borderRadius: 5, cursor: 'pointer', background: isGroupCollapsed ? '#1f2937' : '#21262d', border: '1px solid #30363d', color: '#38bdf8' }}
                                >
                                  {isGroupCollapsed ? <RightOutlined style={{ fontSize: 9 }} /> : <DownOutlined style={{ fontSize: 9 }} />}{' '}
                                  {isGroupCollapsed ? `Expand (${group.children.length})` : 'Hide'}
                                </button>
                              )}
                            </div>
                          </div>
                        </div>
                        <div style={{ width: 24, height: 2, background: groupBorder, flexShrink: 0 }} />
                        {/* LEVEL 3: Children (Collapsed summary OR Multi-Stage Flow Columns OR Standard Stack) */}
                        {isGroupCollapsed ? (
                          <div onClick={() => toggleGroupCollapse(group.id)} style={{ background: '#0d1117', border: '1px dashed #3b82f6', borderRadius: 10, padding: '10px 16px', color: '#58a6ff', fontSize: 12, cursor: 'pointer', fontWeight: 600 }}>
                            ▶ Click to expand {group.children.length} connected items in {group.title}
                          </div>
                        ) : group.children.length === 0 ? (
                          <div style={{ background: '#0d1117', border: '1px dashed #30363d', borderRadius: 10, padding: '10px 16px', color: '#6e7681', fontSize: 12 }}>
                            {group.emptyText || labels.emptyLabel}
                          </div>
                        ) : group.useStageColumnsLayout && stageCols.length > 0 ? (
                          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12, background: 'rgba(13, 17, 23, 0.72)', border: '1px solid #21262d', borderRadius: 14, padding: '14px 16px' }}>
                            {stageCols.map((col, colIdx) => (
                              <React.Fragment key={`col_${col.index}`}>
                                <div style={{ display: 'flex', flexDirection: 'column', gap: 10, width: 255, flexShrink: 0 }}>
                                  <div style={{ fontSize: 10, fontWeight: 700, color: '#a5b4fc', textTransform: 'uppercase', background: '#161b22', border: '1px solid #30363d', borderRadius: 6, padding: '4px 8px', textAlign: 'center', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                    {col.label} ({col.items.length})
                                  </div>
                                  {col.items.map((leaf) => (
                                    <ConnectionCanvasNodeCard
                                      key={leaf.id}
                                      node={leaf}
                                      compactMode
                                      expanded={Boolean(expandedNodeIds[leaf.id])}
                                      showLinks={showLinks}
                                      highlightState={getHighlightState(leaf.id)}
                                      expandTooltip={labels.expandNodeTooltip}
                                      collapseTooltip={labels.collapseNodeTooltip}
                                      onToggleExpand={handleToggleNodeExpand}
                                      onClickNode={onClickLeaf}
                                      onClickStage={onClickStage}
                                      onHoverNode={setHoveredNodeId}
                                    />
                                  ))}
                                </div>
                                {colIdx < stageCols.length - 1 && (
                                  <div style={{ alignSelf: 'center', color: '#38bdf8', fontWeight: 800, fontSize: 18, padding: '0 2px' }}>➔</div>
                                )}
                              </React.Fragment>
                            ))}
                          </div>
                        ) : (
                          <div style={{ display: 'flex', flexDirection: 'column', gap: 14, borderLeft: group.children.length > 1 ? '2px solid #8b5cf688' : 'none', paddingLeft: 20 }}>
                            {group.children.map((leaf) => (
                              <div key={leaf.id} style={{ display: 'flex', alignItems: 'center', position: 'relative' }}>
                                <div style={{ position: 'absolute', left: -20, width: 20, height: 2, background: '#8b5cf6' }} />
                                <ConnectionCanvasNodeCard
                                  node={leaf}
                                  expanded={Boolean(expandedNodeIds[leaf.id])}
                                  showLinks={showLinks}
                                  highlightState={getHighlightState(leaf.id)}
                                  expandTooltip={labels.expandNodeTooltip}
                                  collapseTooltip={labels.collapseNodeTooltip}
                                  onToggleExpand={handleToggleNodeExpand}
                                  onClickNode={onClickLeaf}
                                  onClickStage={onClickStage}
                                  onHoverNode={setHoveredNodeId}
                                />
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
          {/* Floating +/- Zoom Controls Dock on Canvas */}
          <div style={{ position: 'absolute', right: 20, bottom: 20, zIndex: 10, display: 'flex', alignItems: 'center', gap: 4, background: 'rgba(13, 17, 23, 0.92)', border: '1px solid #30363d', borderRadius: 10, padding: '6px 8px', boxShadow: '0 8px 24px rgba(0, 0, 0, 0.55)' }}>
            <Button size="small" title="Zoom Out (-)" icon={<MinusOutlined />} onClick={zoomOut} style={{ background: '#161b22', borderColor: '#30363d', color: '#f0f6fc' }} />
            <Button size="small" title="Reset Zoom (100%)" onClick={resetZoomAndPan} style={{ background: '#161b22', borderColor: '#30363d', color: '#38bdf8', fontWeight: 700, minWidth: 56 }}>
              <span ref={hudZoomBtnRef}>100%</span>
            </Button>
            <Button size="small" title="Zoom In (+)" icon={<PlusOutlined />} onClick={zoomIn} style={{ background: '#161b22', borderColor: '#30363d', color: '#f0f6fc' }} />
            <Button size="small" title="Center & Reset View" icon={<AimOutlined />} onClick={resetZoomAndPan} style={{ background: '#161b22', borderColor: '#30363d', color: '#a855f7' }} />
          </div>
        </div>
      </Spin>
    </div>
  );
}