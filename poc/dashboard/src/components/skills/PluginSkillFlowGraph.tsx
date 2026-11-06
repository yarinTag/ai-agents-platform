import React, { useId, useMemo, useRef, useState } from 'react';
import { Button, Empty, Input, Select, Space, Spin, Switch, Tag } from 'antd';
import type { CanvasGroupNode, CanvasLeafNode, CanvasRootNode } from '../common/ConnectionCanvas';
import type { PluginSkill } from '../../types/skill';
import { collectPluginGraphEdges, visiblePluginSkills } from './pluginGraphModel';

type Leaf = CanvasLeafNode<PluginSkill | null>;
interface Props {
  rootNode: CanvasRootNode;
  groups: CanvasGroupNode<PluginSkill | null>[];
  loading: boolean;
  onRefresh?: () => void;
  onInspect: (leaf: Leaf) => void;
}
const WIDTH = 244;
const HEIGHT = 96;
const COLUMN = 344;
const ROW = 142;
const panel: React.CSSProperties = {
  background: '#0d1117', border: '1px solid #30363d', borderRadius: 12, padding: 14,
};

/** Evidence-backed declared flow; ordinary references are opt-in and dotted. */
export function PluginSkillFlowGraph({ rootNode, groups, loading, onRefresh, onInspect }: Props) {
  const markerId = useId().replace(/:/g, '');
  const [query, setQuery] = useState('');
  const [pluginId, setPluginId] = useState('ALL');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [includeReferences, setIncludeReferences] = useState(false);
  const focusRequest = useRef(0);
  const [showEdges, setShowEdges] = useState(true);
  const [zoom, setZoom] = useState(0.8);
  const viewport = useRef<HTMLDivElement>(null);
  const drag = useRef<{ x: number; y: number; left: number; top: number } | null>(null);
  const nodes = useMemo(() => groups.flatMap((group) => group.children.map((leaf) => ({ leaf, group }))), [groups]);
  const byId = useMemo(() => new Map(nodes.map((node) => [node.leaf.id, node])), [nodes]);
  const edges = useMemo(() => collectPluginGraphEdges(groups, includeReferences), [groups, includeReferences]);
  const selected = selectedId ? byId.get(selectedId) : undefined;
  const incoming = edges.filter((edge) => edge.target === selected?.leaf.id).map((edge) => edge.source);
  const outgoing = edges.filter((edge) => edge.source === selected?.leaf.id).map((edge) => edge.target);
  const neighbours = new Set([...incoming, ...outgoing]);
  // Package and search filters are strict; focus never reintroduces old package nodes.
  const visible = useMemo(() => visiblePluginSkills(groups, pluginId, query), [groups, pluginId, query]);
  const layout = useMemo(() => {
    const positions = new Map<string, { x: number; y: number }>();
    const headers: Array<{ id: string; title: string; y: number }> = [];
    let top = 24;
    let width = COLUMN;
    groups.forEach((group) => {
      const children = group.children.filter((leaf) => visible.has(leaf.id));
      if (!children.length) return;
      headers.push({ id: group.id, title: group.title, y: top });
      top += 50;
      const columns = new Map<number, number>();
      children.forEach((leaf) => {
        const column = leaf.flowStageIndex ?? 0;
        const row = columns.get(column) || 0;
        columns.set(column, row + 1);
        positions.set(leaf.id, { x: 28 + column * COLUMN, y: top + row * ROW });
        width = Math.max(width, 80 + column * COLUMN + WIDTH);
      });
      top += Math.max(...columns.values()) * ROW + 36;
    });
    return { positions, headers, width, height: Math.max(420, top) };
  }, [groups, visible]);

  const focus = (id: string) => {
    const target = byId.get(id);
    if (!target) return;
    if (pluginId !== 'ALL' && target.group.id !== pluginId) setPluginId(target.group.id);
    setQuery('');
    setSelectedId(id);
    const request = ++focusRequest.current;
    // Cancel pending reveal if the user switches package/search before it completes.
    requestAnimationFrame(() => requestAnimationFrame(() => {
      if (request !== focusRequest.current) return;
      const element = Array.from(viewport.current?.querySelectorAll<HTMLElement>('[data-skill-id]') || [])
        .find((node) => node.dataset.skillId === id);
      if (element && viewport.current) {
        viewport.current.scrollTo({ left: Math.max(0, element.offsetLeft * zoom - 160),
          top: Math.max(0, element.offsetTop * zoom - 120), behavior: 'smooth' });
      }
    }));
  };
  const changePlugin = (value: string) => {
    ++focusRequest.current;
    setPluginId(value);
    setSelectedId(null);
    setQuery('');
    drag.current = null;
    viewport.current?.scrollTo({ left: 0, top: 0, behavior: 'instant' });
  };
  const changeQuery = (value: string) => {
    ++focusRequest.current;
    setSelectedId(null);
    setQuery(value);
  };
  const relationList = (ids: string[], color: string) => ids.length ? ids.map((id) => (
    <Button key={id} size="small" onClick={() => focus(id)} style={{ color, maxWidth: '100%', height: 'auto', whiteSpace: 'normal', textAlign: 'start' }}>
      {byId.get(id)?.leaf.title || id}
    </Button>
  )) : <span style={{ color: '#8b949e' }}>No documented connections</span>;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={panel}>
        <div style={{ color: '#f0f6fc', fontWeight: 700, marginBottom: 10 }}>Skill connections</div>
        <Space wrap>
          <Input aria-label="Search skills" placeholder="Find a skill…" allowClear value={query} onChange={(event) => changeQuery(event.target.value)} style={{ width: 230 }} />
          <Select aria-label="Plugin package" value={pluginId} onChange={changePlugin} style={{ minWidth: 200 }} options={[
            { value: 'ALL', label: 'All plugins' }, ...groups.map((group) => ({ value: group.id, label: group.title })),
          ]} />
          <Space><Switch checked={includeReferences} onChange={setIncludeReferences} size="small" /><span style={{ color: '#c9d1d9' }}>Include references</span></Space>
          <Space><Switch checked={showEdges} onChange={setShowEdges} size="small" /><span style={{ color: '#c9d1d9' }}>Edges</span></Space>
          <Button onClick={() => setZoom((value) => Math.max(0.35, value - 0.1))} aria-label="Zoom out">−</Button>
          <Button onClick={() => setZoom(0.8)}>{Math.round(zoom * 100)}%</Button>
          <Button onClick={() => setZoom((value) => Math.min(1.5, value + 0.1))} aria-label="Zoom in">+</Button>
          {selected && <Button onClick={() => { ++focusRequest.current; setSelectedId(null); }}>Clear focus</Button>}
          {onRefresh && <Button onClick={onRefresh} loading={loading}>Refresh</Button>}
        </Space>
        <div style={{ color: '#8b949e', fontSize: 12, marginTop: 10 }}>
          {rootNode.subtitle} · {visible.size} skills · {edges.filter((edge) => visible.has(edge.source) && visible.has(edge.target)).length} connections
          <br />Solid arrows: explicit handoffs or declared lifecycle transitions. Dashed: conditional handoffs or optional transitions. Dotted: references (opt-in). Columns group roles; this is documented flow, not an execution trace.
          <br /><span style={{ color: '#f59e0b' }}>● Incoming</span> · <span style={{ color: '#38bdf8' }}>● Selected</span> · <span style={{ color: '#10b981' }}>● Outgoing</span> · Click a skill to trace its links. Drag the background to pan.
        </div>
      </div>
      {selected && (
        <div style={{ ...panel, borderColor: '#38bdf8' }}>
          <Space wrap><strong style={{ color: '#f0f6fc' }}>{selected.leaf.title}</strong><Tag color="blue">{selected.group.title}</Tag><Tag>{selected.leaf.flowStageLabel}</Tag>
            {selected.leaf.data && <Button size="small" onClick={() => onInspect(selected.leaf)}>Open SKILL.md</Button>}</Space>
          <div style={{ color: '#8b949e', marginTop: 8 }}>{selected.leaf.subtitle}</div>
          <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap', marginTop: 12 }}>
            <div><div style={{ color: '#f59e0b', marginBottom: 6 }}>Incoming · {incoming.length}</div><Space wrap>{relationList(incoming, '#f59e0b')}</Space></div>
            <div><div style={{ color: '#10b981', marginBottom: 6 }}>Outgoing · {outgoing.length}</div><Space wrap>{relationList(outgoing, '#10b981')}</Space></div>
          </div>
          <details style={{ color: '#c9d1d9', marginTop: 12 }}>
            <summary style={{ cursor: 'pointer' }}>Connection evidence and conditions</summary>
            {edges.filter((edge) => edge.source === selectedId || edge.target === selectedId).map((edge) => (
              <div key={`${edge.source}:${edge.target}`} style={{ marginTop: 12 }}>
                <strong>{edge.source} → {edge.target}</strong>
                {edge.connections.map((connection, index) => <div key={index} style={{ marginTop: 6 }}>
                  <Tag>{connection.kind.replace(/_/g, ' ')}{connection.conditional ? ' (optional)' : ''}</Tag>
                  <span style={{ fontSize: 11, overflowWrap: 'anywhere' }}>{connection.evidence.path}:{connection.evidence.line || connection.evidence.node_id}</span>
                  <pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', fontSize: 11, color: '#8b949e' }}>{connection.evidence.text}</pre>
                </div>)}
              </div>
            ))}
          </details>
          {(selected.leaf.data?.connection_warnings || []).map((warning) => <div key={warning} style={{ color: '#f59e0b', marginTop: 8 }}>{warning}</div>)}
          {selected.leaf.data && !selected.leaf.data.skill_connections && <div style={{ color: '#f59e0b', marginTop: 8 }}>Refresh plugins to load evidence-backed connections. Legacy mentions are not treated as flow.</div>}
        </div>
      )}
      <Spin spinning={loading}>
        <div ref={viewport} onPointerDown={(event) => {
          if (event.button !== 0 || (event.target as HTMLElement).closest('button')) return;
          const el = event.currentTarget;
          drag.current = { x: event.clientX, y: event.clientY, left: el.scrollLeft, top: el.scrollTop };
          el.setPointerCapture(event.pointerId);
        }} onPointerMove={(event) => {
          if (!drag.current) return;
          event.currentTarget.scrollLeft = drag.current.left - event.clientX + drag.current.x;
          event.currentTarget.scrollTop = drag.current.top - event.clientY + drag.current.y;
        }} onPointerUp={() => { drag.current = null; }} onPointerCancel={() => { drag.current = null; }}
          style={{ ...panel, padding: 0, height: '65vh', minHeight: 440, overflow: 'auto', cursor: 'grab', touchAction: 'none',
            backgroundColor: '#070a0f', backgroundImage: 'radial-gradient(#243042 1px, transparent 1px)', backgroundSize: '24px 24px' }}>
          {!layout.positions.size ? <Empty description="No skills match this filter" style={{ padding: 80 }} /> : (
            <div style={{ position: 'relative', width: layout.width * zoom, height: layout.height * zoom }}>
              <div style={{ position: 'absolute', width: layout.width, height: layout.height, transform: `scale(${zoom})`, transformOrigin: 'top left' }}>
                {layout.headers.map((header) => <div key={header.id} style={{ position: 'absolute', left: 28, top: header.y, color: '#c4b5fd', fontWeight: 700 }}>{header.title}</div>)}
                {showEdges && <svg width={layout.width} height={layout.height} aria-label="Documented skill connections" style={{ position: 'absolute', inset: 0, pointerEvents: 'none', overflow: 'visible' }}>
                  <defs>{['#64748b', '#f59e0b', '#10b981'].map((color, index) => <marker key={color} id={`${markerId}-${index}`} markerWidth="10" markerHeight="10" refX="9" refY="5" orient="auto" markerUnits="userSpaceOnUse"><path d="M 0 0 L 10 5 L 0 10 z" fill={color} /></marker>)}</defs>
                  {[...edges].sort((a, b) => Number(a.source === selectedId || a.target === selectedId) - Number(b.source === selectedId || b.target === selectedId)).map(({ source, target, connections, referenceOnly, conditional }) => {
                    const from = layout.positions.get(source), to = layout.positions.get(target);
                    if (!from || !to) return null;
                    const active = source === selectedId || target === selectedId;
                    const index = target === selectedId ? 1 : source === selectedId ? 2 : 0;
                    const color = ['#64748b', '#f59e0b', '#10b981'][index];
                    const forward = to.x > from.x;
                    const x1 = from.x + WIDTH, y1 = from.y + HEIGHT / 2;
                    const x2 = forward ? to.x : to.x + WIDTH, y2 = to.y + HEIGHT / 2;
                    const bend = forward ? Math.max(45, (x2 - x1) / 2) : 55 + Math.abs(y2 - y1) * 0.08;
                    const path = forward ? `M ${x1} ${y1} C ${x1 + bend} ${y1}, ${x2 - bend} ${y2}, ${x2} ${y2}` :
                      `M ${x1} ${y1} C ${Math.max(x1, x2) + bend} ${y1}, ${Math.max(x1, x2) + bend} ${y2}, ${x2} ${y2}`;
                    return <path key={`${source}:${target}`} d={path} fill="none" stroke={color} strokeWidth={active ? 3 : 1.5} strokeDasharray={referenceOnly ? '2 6' : conditional ? '8 5' : undefined} opacity={selected ? active ? 1 : 0.1 : 0.5} markerEnd={`url(#${markerId}-${index})`}><title>{source} → {target}{'\n'}{connections.map((connection) => `${connection.kind}: ${connection.evidence.path}:${connection.evidence.line || connection.evidence.node_id || ''}\n${connection.evidence.text}`).join('\n')}</title></path>;
                  })}
                </svg>}
                {nodes.map(({ leaf, group }) => {
                  const position = layout.positions.get(leaf.id);
                  if (!position) return null;
                  const color = leaf.id === selectedId ? '#38bdf8' : incoming.includes(leaf.id) ? '#f59e0b' : outgoing.includes(leaf.id) ? '#10b981' : '#475569';
                  return <button type="button" key={leaf.id} data-skill-id={leaf.id} aria-pressed={leaf.id === selectedId} onClick={() => focus(leaf.id)} title={`${group.title} / ${leaf.id}\n${leaf.subtitle || ''}`} style={{
                    position: 'absolute', left: position.x, top: position.y, width: WIDTH, height: HEIGHT, boxSizing: 'border-box',
                    border: `2px solid ${color}`, borderRadius: 10, background: '#101923', color: '#f0f6fc', padding: '10px 12px',
                    textAlign: 'start', cursor: 'pointer', opacity: selected && leaf.id !== selectedId && !neighbours.has(leaf.id) ? 0.3 : 1,
                  }}>
                    <div style={{ color: '#a5b4fc', fontSize: 10, marginBottom: 6 }}>{leaf.flowStageLabel}</div>
                    <div style={{ fontWeight: 700, fontSize: 13, overflow: 'hidden', whiteSpace: 'nowrap', textOverflow: 'ellipsis' }}>{leaf.title}</div>
                    <div style={{ color: '#8b949e', fontSize: 10, marginTop: 6, overflow: 'hidden', whiteSpace: 'nowrap', textOverflow: 'ellipsis' }}>{leaf.id}</div>
                  </button>;
                })}
              </div>
            </div>
          )}
        </div>
      </Spin>
    </div>
  );
}
