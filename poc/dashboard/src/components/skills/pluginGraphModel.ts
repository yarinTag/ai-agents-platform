import type { CanvasGroupNode, CanvasLeafNode } from '../common/ConnectionCanvas/connectionCanvasTypes';
import type { PluginSkill, PluginSkillConnection } from '../../types/skill';

export type PluginGraphLeaf = CanvasLeafNode<PluginSkill | null>;
export interface PluginGraphEdge {
  source: string;
  target: string;
  connections: PluginSkillConnection[];
  referenceOnly: boolean;
  conditional: boolean;
}

export function collectPluginGraphEdges(groups: CanvasGroupNode<PluginSkill | null>[], includeReferences = false): PluginGraphEdge[] {
  const leaves = groups.flatMap((group) => group.children);
  const known = new Set(leaves.map((leaf) => leaf.id));
  const edges = new Map<string, PluginGraphEdge>();
  leaves.forEach((leaf) => (leaf.data?.skill_connections || []).forEach((connection) => {
    if (connection.source !== leaf.id || connection.source === connection.target || !known.has(connection.target)) return;
    if (connection.kind === 'reference' && !includeReferences) return;
    const key = JSON.stringify([connection.source, connection.target]);
    let edge = edges.get(key);
    if (!edge) {
      edge = { source: connection.source, target: connection.target, connections: [], referenceOnly: true, conditional: false };
      edges.set(key, edge);
    }
    edge.connections.push(connection);
    edge.referenceOnly &&= connection.kind === 'reference';
    // Do not hide a documented condition when another source declares the same edge.
    edge.conditional ||= connection.conditional === true || connection.kind === 'conditional_handoff';
  }));
  return [...edges.values()];
}

export function visiblePluginSkills(groups: CanvasGroupNode<PluginSkill | null>[], pluginId: string, query: string): Set<string> {
  const search = query.trim().toLowerCase();
  return new Set(groups.filter((group) => pluginId === 'ALL' || pluginId === group.id)
    .flatMap((group) => group.children.filter((leaf) => !search ||
      `${leaf.id} ${leaf.title} ${leaf.subtitle || ''} ${group.title}`.toLowerCase().includes(search)).map((leaf) => leaf.id)));
}
