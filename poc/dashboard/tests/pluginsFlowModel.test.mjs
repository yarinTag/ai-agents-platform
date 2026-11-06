import { test } from 'node:test';
import assert from 'node:assert/strict';
import { buildPluginSkillFlow } from '../src/components/skills/pluginsFlowModel.ts';

const skill = (id, targets = []) => ({ id, name: id, skill_connections: targets.map(target => ({
  source: id, target, kind: 'handoff', evidence: { path: `${id}/SKILL.md`, line: 1, text: `Invoke ${target}` },
})) });
const pkg = (name, skills) => ({ name, skills });

test('incoming references include other plugins and cycles remain directional', () => {
  const core = pkg('core', [skill('product-eng-review', ['tech-builder'])]);
  const tech = pkg('tech', [skill('tech-builder', ['product-eng-review'])]);
  const [review] = buildPluginSkillFlow(core, [core, tech]);
  assert.deepEqual(review.connectedFromIds, ['tech-builder']);
  assert.deepEqual(review.connectedToIds, ['tech-builder']);
});

test('known core names do not fabricate lifecycle edges or infer from previews', () => {
  const core = pkg('core', [
    { ...skill('product-prd-writer'), content_preview: 'product-eng-review', description: 'product-eng-review' },
    skill('product-eng-review'), skill('product-architecture-designer'),
  ]);
  for (const node of buildPluginSkillFlow(core, [core])) {
    assert.deepEqual(node.connectedToIds, []);
    assert.deepEqual(node.connectedFromIds, []);
  }
});

test('self references, missing targets and duplicate references do not add edges', () => {
  const core = pkg('core', [skill('a', ['a', 'missing', 'b', 'b']), skill('b')]);
  const before = JSON.stringify(core);
  const result = buildPluginSkillFlow(core, [core]);
  assert.deepEqual(result.find(node => node.skill.id === 'a').connectedToIds, ['b']);
  assert.deepEqual(result.find(node => node.skill.id === 'b').connectedFromIds, ['a']);
  assert.equal(JSON.stringify(core), before);
  assert.deepEqual(buildPluginSkillFlow(pkg('empty', []), []), []);
});


test('legacy mentions and documentation references never become flow edges', () => {
  const core = pkg('core', [{ ...skill('a'), connected_skills: ['b'], skill_connections: [
    { source: 'a', target: 'b', kind: 'reference', evidence: { path: 'a/SKILL.md', line: 2, text: 'Read b docs' } },
  ] }, skill('b')]);
  assert.deepEqual(buildPluginSkillFlow(core, [core]).find(node => node.skill.id === 'a').connectedToIds, []);
});
