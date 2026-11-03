import { test } from 'node:test';
import assert from 'node:assert/strict';
import { AxiosError } from 'axios';
import { secretNameProblem, secretValueBytes, isSecretArn, normalizeHosts, isValidHost,
  toModelValue, fromModelValue, formatMemory, formatTimestamp, describeApiFailure,
  MAX_SECRET_VALUE_BYTES } from '../src/components/workflows/workflowSettingsRules.ts';

for (const name of ['API_KEY', '_TOKEN', 'A', 'A'.repeat(64), 'MY_API_KEY_2']) {
  test(`valid secret name: ${name}`, () => assert.equal(secretNameProblem(name), null));
}
for (const name of ['', 'lowercase', '2TOKEN', 'MY-KEY', ' KEY', 'KEY ', 'A'.repeat(65), 'מפתח']) {
  test(`invalid secret name: ${JSON.stringify(name)}`, () => assert.equal(secretNameProblem(name), 'format'));
}
for (const name of ['PATH', 'HOME', 'HTTP_PROXY', 'LD_PRELOAD', 'PYTHONPATH', 'NODE_OPTIONS', 'BASH_ENV',
  'PLATFORM_SECRETS_KEY', 'DOCKER_HOST', 'DOCKER_CONFIG']) {
  test(`reserved environment variable: ${name}`, () => assert.equal(secretNameProblem(name), 'reserved'));
}

test('secret size is measured as UTF-8 bytes, including multibyte boundary cases', () => {
  assert.equal(secretValueBytes(''), 0);
  assert.equal(secretValueBytes('שלום'), 8);
  assert.equal(secretValueBytes('🚀'), 4);
  assert.equal(secretValueBytes('x'.repeat(MAX_SECRET_VALUE_BYTES)), MAX_SECRET_VALUE_BYTES);
  assert.equal(secretValueBytes('🚀'.repeat(MAX_SECRET_VALUE_BYTES / 4)), MAX_SECRET_VALUE_BYTES);
  assert.ok(secretValueBytes('🚀'.repeat(MAX_SECRET_VALUE_BYTES / 4) + 'x') > MAX_SECRET_VALUE_BYTES);
});

for (const ref of ['arn:aws:secretsmanager:us-east-1:123456789012:secret:platform/key-Ab12',
  'arn:aws:secretsmanager:eu-west-1:123456789012:secret:token_+=.@-']) {
  test(`accepts Secrets Manager ARN: ${ref}`, () => assert.equal(isSecretArn(ref), true));
}
for (const ref of ['', 'https://example.com/key', 'arn:aws:s3:us-east-1:123456789012:secret:key',
  'arn:aws:secretsmanager:us-east-1:123:secret:key',
  'arn:aws:secretsmanager:us-east-1:123456789012:secret:',
  'arn:aws:secretsmanager:us-east-1:123456789012:secret:' + 'x'.repeat(513)]) {
  test(`rejects invalid secret reference: ${ref.slice(0, 75)}`, () => assert.equal(isSecretArn(ref), false));
}

test('host normalization trims, folds case, strips trailing dots and deduplicates in order', () => {
  const input = [' API.GITHUB.COM. ', '', 'api.github.com', 'example.org...', ' EXAMPLE.ORG '];
  assert.deepEqual(normalizeHosts(input), ['api.github.com', 'example.org']);
  assert.equal(input[0], ' API.GITHUB.COM. ');
  assert.deepEqual(normalizeHosts(normalizeHosts(input)), normalizeHosts(input));
});
for (const host of ['api.github.com', 'a.co', 'my-service.example.org']) {
  test(`accepts exact hostname: ${host}`, () => assert.equal(isValidHost(host), true));
}
for (const host of ['', 'localhost', '*.example.com', 'https://example.com', 'example.com:443',
  'example.com/path', '127.0.0.1', '[::1]', '-a.example.com', 'a-.example.com', 'a..example.com',
  'a'.repeat(64) + '.com', 'example.com\n']) {
  test(`rejects unsafe hostname: ${JSON.stringify(host)}`, () => assert.equal(isValidHost(host), false));
}

test('model default roundtrip distinguishes null from explicit provider model IDs', () => {
  for (const model of [null, undefined, '', 'default']) assert.equal(toModelValue(model), 'default');
  assert.equal(fromModelValue('default'), null);
  for (const model of ['tier:developer', 'openai/gpt-model', 'custom/model']) {
    assert.equal(fromModelValue(toModelValue(model)), model);
  }
});
for (const [input, expected] of [['4g', '4 GB'], [' 512M ', '512 MB'], ['1GiB', '1GiB'], ['', '']]) {
  test(`memory display: ${JSON.stringify(input)}`, () => assert.equal(formatMemory(input), expected));
}

test('invalid timestamps are preserved rather than displayed as Invalid Date', () => {
  assert.equal(formatTimestamp('unknown'), 'unknown');
  const date = '2026-01-02T03:04:05Z';
  assert.equal(formatTimestamp(date), new Date(date).toLocaleString());
});

const failure = (detail, status = 422) => new AxiosError('Request failed', 'ERR_BAD_REQUEST',
  { data: 'private-request-secret' }, undefined, { status, data: { detail }, headers: {}, config: {} });

test('API validation errors expose messages but never submitted secret inputs or request bodies', () => {
  const result = describeApiFailure(failure([
    { msg: 'Invalid field', input: 'private-submitted-key', loc: ['body', 'api_key'] },
    { msg: 'Missing field', input: { secret: 'nested-private-key' } },
    null, { msg: 17 }, { input: 'another-secret' },
  ]));
  assert.deepEqual(result, { status: 422, detail: 'Invalid field; Missing field' });
  assert.doesNotMatch(JSON.stringify(result), /private|secret|api_key/);
});

test('API failures support plain and structured details without stringifying unknown values', () => {
  assert.deepEqual(describeApiFailure(failure('Forbidden', 403)), { status: 403, detail: 'Forbidden' });
  assert.deepEqual(describeApiFailure(failure({ message: 'Conflict', token: 'hidden' }, 409)), { status: 409, detail: 'Conflict' });
  assert.deepEqual(describeApiFailure(failure([{ input: 'hidden' }])), { status: 422, detail: undefined });
  assert.deepEqual(describeApiFailure(failure({ input: 'hidden' })), { status: 422 });
  for (const error of [null, undefined, 'offline', new Error('private')]) assert.deepEqual(describeApiFailure(error), {});
  assert.deepEqual(describeApiFailure(new AxiosError('offline')), { status: undefined });
});
