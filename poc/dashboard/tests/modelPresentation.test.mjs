import { test } from 'node:test';
import assert from 'node:assert/strict';
import { formatContextWindow, getModelTierLabel, getModelTierColor, AI_MODELS, MODEL_GROUPS } from '../src/constants/models.ts';

for (const [tokens, expected] of [[0, '0'], [999, '999'], [1000, '1K'], [128000, '128K'], [1000000, '1M'], [2000000, '2M']]) {
  test(`context window presentation at ${tokens}`, () => assert.equal(formatContextWindow(tokens), expected));
}
for (const [tier, label, color] of [['executive', 'Executive', '#eab308'], ['architect', 'Architect', '#a855f7'],
  ['developer', 'Coding', '#3b82f6'], ['coding', 'Coding', '#3b82f6'], ['worker', 'Fast Worker', '#10b981'],
  ['default', 'Default', '#0ea5e9']]) {
  test(`tier presentation is case-insensitive: ${tier}`, () => {
    assert.equal(getModelTierLabel(tier.toUpperCase()), label);
    assert.equal(getModelTierColor(tier.toUpperCase()), color);
  });
}

test('unknown tiers retain their label and use neutral styling', () => {
  assert.equal(getModelTierLabel('Custom'), 'Custom');
  assert.equal(getModelTierColor('Custom'), '#8b949e');
  assert.equal(getModelTierLabel(), 'General');
  assert.equal(getModelTierLabel(''), 'General');
});

test('static catalog entries have unique IDs and occur in exactly one matching provider group', () => {
  assert.equal(new Set(AI_MODELS.map(m => m.value)).size, AI_MODELS.length);
  const grouped = MODEL_GROUPS.flatMap(g => g.options);
  assert.deepEqual(grouped.map(m => m.value).sort(), AI_MODELS.map(m => m.value).sort());
  for (const group of MODEL_GROUPS) assert.ok(group.options.every(m => m.provider === group.label));
});
