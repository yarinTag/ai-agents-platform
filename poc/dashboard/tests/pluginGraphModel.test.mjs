import { test } from 'node:test';
import assert from 'node:assert/strict';
import { collectPluginGraphEdges, visiblePluginSkills } from '../src/components/skills/pluginGraphModel.ts';

const link = (source, target, kind = 'handoff') => ({ source, target, kind, evidence: { path: `${source}/SKILL.md`, text: 'evidence' } });
const groups = [
  { id: 'core', title: 'Core', children: [
    { id: 'review', title: 'Review', data: { skill_connections: [link('review', 'build', 'conditional_handoff'), link('review', 'docs', 'reference')] } },
    { id: 'docs', title: 'Docs', data: { skill_connections: [] } },
  ] },
  { id: 'tech', title: 'Tech', children: [
    { id: 'build', title: 'Build', data: { skill_connections: [link('build', 'review')] } },
  ] },
];

test('switching plugin shows exactly that plugin despite cross-plugin relationships', () => {
  assert.deepEqual([...visiblePluginSkills(groups, 'core', '')], ['review', 'docs']);
  assert.deepEqual([...visiblePluginSkills(groups, 'tech', '')], ['build']);
  assert.deepEqual([...visiblePluginSkills(groups, 'ALL', '')], ['review', 'docs', 'build']);
  assert.deepEqual([...visiblePluginSkills(groups, 'tech', 'Review')], []);
});

test('flow excludes references by default and preserves conditional direction', () => {
  const edges = collectPluginGraphEdges(groups);
  assert.deepEqual(edges.map(edge => [edge.source, edge.target]), [['review', 'build'], ['build', 'review']]);
  assert.equal(edges[0].conditional, true);
  assert.equal(edges[1].conditional, false);
  const references = collectPluginGraphEdges(groups, true).filter(edge => edge.referenceOnly);
  assert.deepEqual(references.map(edge => [edge.source, edge.target]), [['review', 'docs']]);
});

test('multiple declarations aggregate while retaining every source condition', () => {
  const copy = structuredClone(groups);
  copy[0].children[0].data.skill_connections.push(link('review', 'build', 'declared_transition'));
  const [edge] = collectPluginGraphEdges(copy);
  assert.equal(edge.connections.length, 2);
  assert.equal(edge.conditional, true);
});

test('self links, unknown targets, wrong owners and legacy mentions stay out of flow', () => {
  const copy = structuredClone(groups);
  copy[0].children[0].data.skill_connections = [link('review', 'review'), link('review', 'missing'), link('build', 'docs')];
  copy[0].children[1].data = { connected_skills: ['build'] };
  assert.deepEqual(collectPluginGraphEdges(copy).map(edge => [edge.source, edge.target]), [['build', 'review']]);
});
