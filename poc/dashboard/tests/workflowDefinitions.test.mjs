import { test } from 'node:test';
import assert from 'node:assert/strict';
import { removeWorkflowStep } from '../src/services/workflowDefinitions.ts';

const remove = (definition, key) => JSON.parse(removeWorkflowStep(JSON.stringify(definition), key).definitionJson);

test('removing a middle stage reconnects consumers to its prerequisites and deduplicates', () => {
  const original = { name: 'Review', custom: { preserve: true }, steps: [
    { key: 'research', depends_on: [], extra: 'keep' },
    { key: 'review', name: 'Review stage', depends_on: ['research'] },
    { key: 'publish', depends_on: ['review', 'research'], params: { required_outcome: 'pull_request' } },
  ] };
  const result = removeWorkflowStep(JSON.stringify(original), 'review');
  const changed = JSON.parse(result.definitionJson);
  assert.equal(result.deletedName, 'Review stage');
  assert.deepEqual(changed.steps.map(s => s.key), ['research', 'publish']);
  assert.deepEqual(changed.steps[1].depends_on, ['research']);
  assert.deepEqual(changed.steps[1].params, { required_outcome: 'pull_request' });
  assert.deepEqual(changed.custom, { preserve: true });
  assert.deepEqual(original.steps[2].depends_on, ['review', 'research']);
});

test('fan-in prerequisites are inherited by every downstream consumer', () => {
  const result = remove({ steps: [
    { key: 'a' }, { key: 'b' }, { key: 'join', depends_on: ['a', 'b'] },
    { key: 'x', depends_on: ['join'] }, { key: 'y', depends_on: ['b', 'join'] },
  ] }, 'join');
  assert.deepEqual(result.steps.find(s => s.key === 'x').depends_on, ['a', 'b']);
  assert.deepEqual(result.steps.find(s => s.key === 'y').depends_on, ['b', 'a']);
});

test('removing a root clears dependencies and prunes only dangling visual edges', () => {
  const result = remove({ steps: [{ key: 'a' }, { key: 'b', depends_on: ['a'] }, { key: 'c' }],
    flow: [{ from: '', to: 'b' }, { from: 'a', to: 'b' }, { from: 'b', to: 'c' }, { from: 'c', to: 'absent' }],
  }, 'a');
  assert.deepEqual(result.steps[0].depends_on, []);
  assert.deepEqual(result.flow, [{ from: '', to: 'b' }, { from: 'b', to: 'c' }]);
});

test('legacy id-based steps retain their identities and reconnect correctly', () => {
  assert.deepEqual(remove({ steps: [{ id: 'a' }, { id: 'b', depends_on: ['a'] }] }, 'a'),
    { steps: [{ id: 'b', depends_on: [] }] });
});

test('removal never adds a self-dependency even for malformed existing cycles', () => {
  const result = remove({ steps: [{ key: 'a', depends_on: ['b'] }, { key: 'b', depends_on: ['a'] }] }, 'a');
  assert.deepEqual(result.steps, [{ key: 'b', depends_on: [] }]);
});

test('removing the only step yields an empty definition without losing metadata', () => {
  assert.deepEqual(remove({ metadata: { channel_binding: { notify_mode: 'NONE' } }, steps: [{ key: 'only' }], flow: [] }, 'only'),
    { metadata: { channel_binding: { notify_mode: 'NONE' } }, steps: [], flow: [] });
});

test('missing steps and missing keys are safe no-ops for valid existing graphs', () => {
  assert.deepEqual(remove({}, 'absent'), { steps: [] });
  const original = { steps: [{ key: 'keep', custom: { enabled: false } }] };
  assert.deepEqual(remove(original, 'absent'), original);
  assert.equal(removeWorkflowStep(JSON.stringify(original), 'absent').deletedName, 'absent');
});

for (const input of ['not JSON', '{', '{"steps":{}}', '{"steps":"bad"}']) {
  test(`invalid workflow definition is rejected: ${input}`, () => {
    assert.throws(() => removeWorkflowStep(input, 'a'));
  });
}
