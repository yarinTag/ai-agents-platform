import { test } from 'node:test';
import assert from 'node:assert/strict';
import { effectivePermissions } from '../src/services/accessPermissions.ts';

test('organization administrator does not require an explicit department membership', () => {
  assert.deepEqual(effectivePermissions('ORG_ADMIN'), { isAdmin: true, canRead: true, canOperate: true, canManage: true, rank: 4 });
});
test('department membership and account role both constrain effective rights', () => {
  assert.equal(effectivePermissions('MANAGER', 'MEMBER').rank, 1);
  assert.equal(effectivePermissions('MEMBER', 'MANAGER').rank, 1);
  assert.equal(effectivePermissions('OPERATOR', 'MANAGER').rank, 2);
  assert.equal(effectivePermissions('MANAGER', 'MANAGER').canManage, true);
});
test('members are read-only, operators may execute but may not configure', () => {
  assert.equal(effectivePermissions('MEMBER', 'MEMBER').canOperate, false);
  assert.equal(effectivePermissions('OPERATOR', 'OPERATOR').canOperate, true);
  assert.equal(effectivePermissions('OPERATOR', 'OPERATOR').canManage, false);
});
test('unassigned and unknown roles fail closed', () => {
  for (const flags of [effectivePermissions('MANAGER'), effectivePermissions('unknown', 'MANAGER'), effectivePermissions('MEMBER', 'unknown')]) {
    assert.equal(flags.canRead, false);
    assert.equal(flags.canOperate, false);
    assert.equal(flags.canManage, false);
  }
});
