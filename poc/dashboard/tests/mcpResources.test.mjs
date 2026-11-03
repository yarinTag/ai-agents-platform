import { test } from 'node:test';
import assert from 'node:assert/strict';
import { configuredResourceValues } from '../src/services/mcpResources.ts';

const values = connectors => configuredResourceValues(connectors, 'telegram', 'allowed_channels', 'chat_id');

test('resource projection never invents destinations for an empty catalog', () => {
  assert.deepEqual(values([]), []);
  assert.deepEqual(values([{ id: 't', provider: 'telegram' }]), []);
  assert.deepEqual(values([{ id: 't', provider: 'telegram', configuration: null }]), []);
});

test('only matching connector providers or exact catalog IDs contribute destinations', () => {
  assert.deepEqual(values([
    { id: 'slack', provider: 'slack', configuration: { allowed_channels: ['C123'] } },
    { id: 'custom', provider: 'telegram', configuration: { allowed_channels: ['-1001'] } },
    { id: 'telegram', provider: 'custom', configuration: { chat_id: '-1002' } },
  ]), ['-1001', '-1002']);
});

test('canonical resource IDs are trimmed and deduplicated while keeping array and legacy destinations', () => {
  const connectors = [{ id: 't', provider: 'telegram', configuration: {
    allowed_channels: [' -1001 ', '-1002', '-1001', null, 42, '', '  ', { id: 'forged' }], chat_id: '-1003',
  } }];
  const before = JSON.stringify(connectors);
  assert.deepEqual(values(connectors), ['-1001', '-1002', '-1003']);
  assert.equal(JSON.stringify(connectors), before);
});

test('malformed resource arrays are ignored without fabricating selections', () => {
  for (const list of ['-1001', { id: '-1001' }, 3, null]) {
    assert.deepEqual(values([{ provider: 'telegram', configuration: { allowed_channels: list, chat_id: '-1002' } }]), ['-1002']);
  }
});

test('resources from independent connectors are merged once in stable catalog order', () => {
  assert.deepEqual(values([
    { provider: 'telegram', configuration: { allowed_channels: ['a', 'b'] } },
    { provider: 'telegram', configuration: { allowed_channels: ['b', 'c'], chat_id: 'a' } },
  ]), ['a', 'b', 'c']);
});
