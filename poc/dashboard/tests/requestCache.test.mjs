import { test } from 'node:test';
import assert from 'node:assert/strict';
import { cachedRequest, invalidateRequestCache } from '../src/services/requestCache.ts';

test('navigation requests share in-flight work and reuse the response', async () => {
  invalidateRequestCache();
  let resolve, loads = 0;
  const load = () => { loads++; return new Promise(done => { resolve = done; }); };
  const first = cachedRequest('catalog:a', load, 60_000);
  const second = cachedRequest('catalog:a', load, 60_000);
  assert.equal(first, second);
  await Promise.resolve(); resolve({ packages: 3 });
  await first;
  assert.deepEqual(await cachedRequest('catalog:a', load, 60_000), { packages: 3 });
  assert.equal(loads, 1);
});

test('failure is retried and zero TTL expires', async () => {
  await assert.rejects(cachedRequest('retry', () => Promise.reject(new Error('offline')), 60_000));
  assert.equal(await cachedRequest('retry', () => Promise.resolve('ok'), 0), 'ok');
  assert.equal(await cachedRequest('retry', () => Promise.resolve('fresh'), 0), 'fresh');
});

test('configuration invalidation prevents an older response replacing a fresh one', async () => {
  let finish;
  const old = cachedRequest('plugins:scan', () => new Promise(done => { finish = done; }), 60_000);
  await Promise.resolve();
  invalidateRequestCache('plugins:');
  assert.equal(await cachedRequest('plugins:scan', () => Promise.resolve('new source'), 60_000), 'new source');
  finish('old source'); await old;
  assert.equal(await cachedRequest('plugins:scan', () => Promise.resolve('unexpected'), 60_000), 'new source');
});

test('forced refresh bypasses a cached result', async () => {
  assert.equal(await cachedRequest('force', () => Promise.resolve('old'), 60_000), 'old');
  assert.equal(await cachedRequest('force', () => Promise.resolve('new'), 60_000, true), 'new');
});
