import { test, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { cachedRequest, invalidateRequestCache } from '../src/services/requestCache.ts';

afterEach(() => invalidateRequestCache());

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

test('different organization keys never share results', async () => {
  assert.equal(await cachedRequest('plugins:org-a', () => Promise.resolve('private-a'), 60000), 'private-a');
  assert.equal(await cachedRequest('plugins:org-b', () => Promise.resolve('private-b'), 60000), 'private-b');
  assert.equal(await cachedRequest('plugins:org-a', () => Promise.resolve('wrong'), 60000), 'private-a');
});

test('prefix invalidation removes one resource family without discarding unrelated state', async () => {
  await cachedRequest('plugins:scan', () => Promise.resolve('old'), 60000);
  await cachedRequest('models:catalog', () => Promise.resolve('keep'), 60000);
  invalidateRequestCache('plugins:');
  assert.equal(await cachedRequest('plugins:scan', () => Promise.resolve('new'), 60000), 'new');
  assert.equal(await cachedRequest('models:catalog', () => Promise.resolve('wrong'), 60000), 'keep');
});

test('late rejection of an invalidated request cannot evict its successful replacement', async () => {
  let reject;
  const old = cachedRequest('race', () => new Promise((_, fail) => { reject = fail; }), 60000);
  const rejected = assert.rejects(old, /old failure/);
  await Promise.resolve();
  invalidateRequestCache('race');
  assert.equal(await cachedRequest('race', () => Promise.resolve('new'), 60000), 'new');
  reject(new Error('old failure'));
  await rejected;
  assert.equal(await cachedRequest('race', () => Promise.resolve('wrong'), 60000), 'new');
});

test('forced overlapping refresh retains the newest value when the older request finishes last', async () => {
  let finish;
  const old = cachedRequest('force-race', () => new Promise(done => { finish = done; }), 60000);
  await Promise.resolve();
  assert.equal(await cachedRequest('force-race', () => Promise.resolve('new'), 60000, true), 'new');
  finish('old');
  assert.equal(await old, 'old');
  assert.equal(await cachedRequest('force-race', () => Promise.resolve('wrong'), 60000), 'new');
});

test('concurrent callers receive the same rejection and a later attempt can recover', async () => {
  let calls = 0;
  const load = () => { calls++; throw new Error('offline'); };
  const first = cachedRequest('offline', load, 60000);
  const second = cachedRequest('offline', load, 60000);
  assert.equal(first, second);
  await Promise.all([assert.rejects(first, /offline/), assert.rejects(second, /offline/)]);
  assert.equal(calls, 1);
  assert.equal(await cachedRequest('offline', () => Promise.resolve('recovered'), 60000), 'recovered');
});

test('bounded cache evicts the oldest entry while preserving recent responses', async () => {
  for (let i = 0; i < 65; i++) await cachedRequest(`key:${i}`, () => Promise.resolve(i), 60000);
  assert.equal(await cachedRequest('key:64', () => Promise.resolve('wrong'), 60000), 64);
  assert.equal(await cachedRequest('key:0', () => Promise.resolve('reloaded'), 60000), 'reloaded');
});

test('default invalidation clears every cached resource family', async () => {
  await cachedRequest('plugins:a', () => Promise.resolve('old'), 60000);
  await cachedRequest('models:a', () => Promise.resolve('old'), 60000);
  invalidateRequestCache();
  for (const key of ['plugins:a', 'models:a']) {
    assert.equal(await cachedRequest(key, () => Promise.resolve('fresh'), 60000), 'fresh');
  }
});
