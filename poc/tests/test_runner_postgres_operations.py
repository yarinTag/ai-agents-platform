"""Real PostgreSQL operation intent, uncertainty and late UID contracts."""
import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from governance.sandbox_manifests import build_sandbox_bundle
from runner.models import OwnedResource
from storage.runner_postgres import RunnerConflict
from storage.runner_postgres_operations import PostgresRunnerOperations
from poc.tests.test_runner_postgres import journal, owned, plan


def operation(journal):
    owner = owned(journal)
    ops = PostgresRunnerOperations(journal)
    row = ops.begin('org-a', owner['attempt_id'], owner['claim_token'],
                    owner['owner_epoch'], owner['revision'], 'Provision')
    return ops, row


def namespace():
    item = next(item for item in build_sandbox_bundle(plan().profile, plan().attempt)
                if item['kind'] == 'Namespace')
    return OwnedResource(kind='Namespace', name=item['metadata']['name'], uid='cluster-uid-a')


def test_concurrent_operation_claim_has_one_winner(journal):
    owner = owned(journal)
    def begin(_):
        try:
            return PostgresRunnerOperations(journal).begin('org-a', owner['attempt_id'],
                owner['claim_token'], owner['owner_epoch'], owner['revision'], 'Provision')
        except RunnerConflict:
            return None
    with ThreadPoolExecutor(max_workers=2) as workers:
        rows = [row for row in workers.map(begin, range(2)) if row]
    assert len(rows) == 1 and rows[0]['state'] == 'Preparing'
    assert rows[0]['claim_token'] == owner['claim_token']
    assert rows[0]['operation_token'] != owner['claim_token']


def test_crashed_operation_prevents_lease_takeover(journal):
    _, row = operation(journal)
    with journal.transaction('org-a') as cursor:
        cursor.execute('UPDATE sandbox_runner_attempts SET lease_until=0')
    with pytest.raises(RunnerConflict):
        journal.claim('org-a', row['attempt_id'], row['revision'], 30)


def test_unknown_retains_late_uid_after_recovery_without_revival(journal):
    ops, row = operation(journal)
    args = ('org-a', row['attempt_id'], row['operation_token'])
    ops.finish(*args, outcome='UNKNOWN')
    journal.rotate_recovery_epoch('org-a', 'install-a')
    receipt = ops.record_resource(*args, namespace())
    assert receipt['revoked'] and receipt['operation_state'] == 'UNKNOWN'
    assert receipt['state'] == 'Stopping'
    assert json.loads(receipt['resources_json'])[0]['uid'] == 'cluster-uid-a'
    repeated = ops.record_resource(*args, namespace())
    assert repeated['revision'] == receipt['revision']
    with pytest.raises(RunnerConflict, match='another UID'):
        ops.record_resource(*args, namespace().model_copy(update={'uid':'replacement'}))
    with pytest.raises(RunnerConflict):
        journal.claim('org-a', row['attempt_id'], repeated['revision'], 30)


def test_not_dispatched_restores_idle_without_fabricating_readiness(journal):
    ops, row = operation(journal)
    done = ops.finish('org-a', row['attempt_id'], row['operation_token'], outcome='NOT_DISPATCHED')
    assert done['state'] == 'Requested' and done['operation_state'] == 'IDLE'
    assert done['operation_token'] is None and not done['revoked']
    for outcome in ('Ready','Running','Released','SUCCEEDED'):
        with pytest.raises(RunnerConflict):
            ops.finish('org-a', row['attempt_id'], row['operation_token'], outcome=outcome)


def test_acknowledged_resources_block_not_dispatched_and_wrong_claim(journal):
    ops, row = operation(journal)
    args = ('org-a', row['attempt_id'], row['operation_token'])
    with pytest.raises(RunnerConflict):
        ops.record_resource('org-a', row['attempt_id'], row['claim_token'], namespace())
    ops.record_resource(*args, namespace())
    with pytest.raises(RunnerConflict):
        ops.finish(*args, outcome='NOT_DISPATCHED')
    with pytest.raises(RunnerConflict):
        ops.record_resource(*args, namespace().model_copy(update={'name':'not-in-plan'}))
    with pytest.raises(RunnerConflict):
        ops.record_resource('org-b', *args[1:], namespace())


def test_revocation_does_not_authorize_a_new_operation(journal):
    owner = owned(journal)
    journal.revoke('org-a', owner['attempt_id'])
    with pytest.raises(RunnerConflict):
        PostgresRunnerOperations(journal).begin('org-a', owner['attempt_id'],
            owner['claim_token'], owner['owner_epoch'], owner['revision'], 'Provision')
