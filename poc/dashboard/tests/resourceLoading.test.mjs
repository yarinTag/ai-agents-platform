import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readResource } from '../src/services/resourceLoading.ts';

test('successful empty results are applied and remain distinct from a failed request', async () => {
  let current = ['old'];
  assert.equal(await readResource(Promise.resolve([]), value => { current = value; }, 'Channels'), null);
  assert.deepEqual(current, []);
});

test('failed reads preserve existing state and expose a retry warning without private error details', async () => {
  const warning = await readResource(Promise.reject(new Error('private-token')), () => assert.fail('Must not overwrite state'), 'Channels');
  assert.equal(warning, 'Channels is unavailable. Retry to refresh this section.');
  assert.doesNotMatch(warning, /private-token/);
});

test('response-application errors are contained as resource warnings', async () => {
  const warning = await readResource(Promise.resolve({}), () => { throw new Error('malformed'); }, 'Agents');
  assert.equal(warning, 'Agents is unavailable. Retry to refresh this section.');
});

test('independent resource reads preserve the successful section when another read fails', async () => {
  let agents = [];
  const results = await Promise.all([
    readResource(Promise.resolve(['agent-a']), value => { agents = value; }, 'Agents'),
    readResource(Promise.reject(new Error('offline')), () => assert.fail(), 'Channels'),
  ]);
  assert.deepEqual(agents, ['agent-a']);
  assert.deepEqual(results, [null, 'Channels is unavailable. Retry to refresh this section.']);
});
