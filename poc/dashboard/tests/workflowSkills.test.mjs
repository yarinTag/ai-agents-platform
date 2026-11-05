import { test } from 'node:test';
import assert from 'node:assert/strict';
import { collectWorkflowSkills } from '../src/components/workflows/workflowSkillSelection.ts';

test('empty and omitted skill selections stay empty', () => {
  assert.deepEqual(collectWorkflowSkills({}), []);
  assert.deepEqual(collectWorkflowSkills({ skills: [], steps: [{}, { skills: [] }] }), []);
});

test('legacy step skills are promoted, deduplicated and retain stable ordering', () => {
  assert.deepEqual(collectWorkflowSkills({ steps: [{ skills: ['research', 'review'] }, { skills: ['review', 'qa'] }] })
    .map(s => s.id), ['research', 'review', 'qa']);
});

test('root skill metadata wins over duplicate legacy IDs', () => {
  const root = { id: 'review', name: 'Code review', source: 'plugin', location: 'core/review', description: 'Full metadata' };
  assert.deepEqual(collectWorkflowSkills({ skills: [root], steps: [{ skills: ['review', 'qa'] }] }),
    [root, { id: 'qa', name: 'qa', source: 'builtin' }]);
});

test('string and attached-object root skills share one deduplication namespace', () => {
  const selected = collectWorkflowSkills({ skills: ['a', { id: 'b', name: 'B', source: 'local' }, 'a'], steps: [{ skills: ['b', 'c'] }] });
  assert.deepEqual(selected.map(s => s.id), ['a', 'b', 'c']);
  assert.equal(selected[1].name, 'B');
});

test('collecting skills does not mutate frozen root or legacy arrays', () => {
  const original = Object.freeze({ skills: Object.freeze(['a']), steps: Object.freeze([Object.freeze({ skills: Object.freeze(['b']) })]) });
  assert.deepEqual(collectWorkflowSkills(original).map(s => s.id), ['a', 'b']);
});
