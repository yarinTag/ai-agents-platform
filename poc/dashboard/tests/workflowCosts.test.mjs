import { test } from 'node:test';
import assert from 'node:assert/strict';
import { asCostSummary, formatCost } from '../src/services/workflowCosts.ts';

for (const [summary, legacy, expected] of [
  [undefined, 0, 'Price unavailable'], [null, 0, 'Price unavailable'],
  [null, 0.25, '$0.250000 · estimated'],
  [{ status: 'free', cost_usd: 0 }, 3, '$0.000000 · free'],
  [{ status: 'no_usage', cost_usd: 0 }, 0, '$0.000000 · no model usage'],
  [{ status: 'estimated', cost_usd: 0.2 }, 0, '$0.200000 · estimated'],
  [{ status: 'reported', cost_usd: 1.5 }, 0, '$1.500000 · reported'],
  [{ status: 'reported', cost_usd: 0.0000001 }, 0, '<$0.000001 · reported'],
  [{ status: 'unavailable', cost_usd: 0 }, 1, 'Price unavailable'],
  [{ status: 'unavailable', cost_usd: null, known_cost_usd: 2 }, 0, 'Price unavailable'],
  [{ status: 'estimated', cost_usd: null }, 0, 'Price unavailable'],
  [{ status: 'free', cost_usd: 0, reference_cost_usd: 0.3 }, 0, '$0.000000 · free · reference $0.300000'],
  [{ status: 'unavailable', cost_usd: null, reference_cost_usd: 0 }, 0, 'Price unavailable · reference $0.000000'],
]) {
  test(`cost presentation: ${expected} (${JSON.stringify(summary)})`, () => assert.equal(formatCost(summary, legacy), expected));
}

test('unknown event values must have both a status and a numeric-or-null cost', () => {
  for (const value of [null, undefined, '', 5, [], {}, { cost_usd: 0 }, { status: 5, cost_usd: 0 },
    { status: 'free', cost_usd: '0' }, { status: 'reported' }]) assert.equal(asCostSummary(value), undefined);
  for (const value of [{ status: 'free', cost_usd: 0 }, { status: 'unavailable', cost_usd: null },
    { status: 'reported', cost_usd: 0.75, calls: 2 }]) assert.deepEqual(asCostSummary(value), value);
});
