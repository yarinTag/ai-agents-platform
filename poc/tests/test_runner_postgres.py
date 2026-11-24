"""Real disposable PostgreSQL contracts. Never uses platform/default databases.

Explicit RUNNER_TEST_POSTGRES_DSN is required; each case uses a unique schema.
CI requires a restricted role; no default platform database is ever selected.
"""
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager

import pytest

from governance.sandbox_profile import SandboxAttempt, SandboxProfile
from runner.models import RunnerPlan
from storage.runner_postgres import PostgresRunnerJournal, RunnerConflict, initialize
from storage.runner_postgres_effects import PostgresRunnerEffects


@pytest.fixture
def journal():
    required = os.environ.get('RUNNER_TEST_REQUIRE_RLS') == '1'
    dsn = os.environ.get('RUNNER_TEST_POSTGRES_DSN')
    if not dsn:
        if required:
            pytest.fail('Required disposable PostgreSQL DSN missing.')
        pytest.skip('Explicit disposable PostgreSQL DSN required.')
    if required:
        import psycopg2
    else:
        psycopg2 = pytest.importorskip('psycopg2')
    from psycopg2 import sql
    from psycopg2.extras import RealDictCursor
    schema = 'runner_test_' + uuid.uuid4().hex
    admin = psycopg2.connect(dsn)
    try:
        with admin.cursor() as cursor:
            if required:
                cursor.execute('SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user')
                assert cursor.fetchone() == (False, False), 'CI requires non-superuser, non-BYPASSRLS role'
            cursor.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
        admin.commit()

        @contextmanager
        def connect():
            connection = psycopg2.connect(dsn, cursor_factory=RealDictCursor)
            try:
                with connection.cursor() as cursor:
                    cursor.execute(sql.SQL('SET LOCAL search_path TO {}').format(
                        sql.Identifier(schema)))
                yield connection
                connection.commit()
            except BaseException:
                connection.rollback()
                raise
            finally:
                connection.close()

        with connect() as connection:
            initialize(connection)
            initialize(connection)
        yield PostgresRunnerJournal(connect)
    finally:
        admin.rollback()
        with admin.cursor() as cursor:
            cursor.execute(sql.SQL('DROP SCHEMA IF EXISTS {} CASCADE').format(
                sql.Identifier(schema)))
        admin.commit()
        admin.close()


def plan(org='org-a', attempt='b' * 32):
    profile = SandboxProfile(
        profile_id='test-only', revision=1, isolation='vm-isolated',
        runtime_class='test-vm', kubernetes_minor='v1.35',
        image='registry.invalid/worker@sha256:' + 'a' * 64,
        uid=1000, gid=1000, cpu_millis=500, memory_mib=512,
        scratch_mib=32, deadline_seconds=300,
        runtime_cpu_overhead_millis=100, runtime_memory_overhead_mib=64)
    now = int(time.time())
    return RunnerPlan(attempt=SandboxAttempt(organization_id=org, attempt_id=attempt,
        profile_sha256=profile.fingerprint()), profile=profile, initiator_id='user-a',
        agent_id='agent-a', environment_id='env-a', domain_id='domain-a', base_version=0,
        config_revision=1, input_sha256='c' * 64, requested_at=now, deadline_at=now + 300)


def owned(journal):
    journal.register_installation('org-a', 'install-a')
    row = journal.create(plan(), 'install-a', 'execution-a')
    return journal.claim('org-a', row['attempt_id'], row['revision'], 30)


def test_two_claimants_have_exactly_one_owner(journal):
    journal.register_installation('org-a', 'install-a')
    row = journal.create(plan(), 'install-a', 'execution-a')
    def claim():
        try:
            return journal.claim('org-a', row['attempt_id'], 1, 30)['owner_epoch']
        except RunnerConflict:
            return None
    with ThreadPoolExecutor(max_workers=2) as workers:
        assert sorted(value for value in workers.map(lambda _: claim(), range(2))
                      if value is not None) == [1]


def test_unknown_blocks_replay_and_expired_lease_takeover(journal):
    owner = owned(journal)
    effects = PostgresRunnerEffects(journal)
    args = ('org-a', owner['attempt_id'], owner['claim_token'], owner['owner_epoch'])
    effects.reserve(*args, 'publish-a', 'd' * 64)
    effects.begin(*args, 'publish-a')
    effects.settle(*args, 'publish-a', 'UNKNOWN')
    with journal.transaction("org-a") as cursor:
        cursor.execute('UPDATE sandbox_runner_attempts SET lease_until=0')
    with pytest.raises(RunnerConflict):
        journal.claim('org-a', owner['attempt_id'], owner['revision'], 30)
    assert journal.get('org-a', owner['attempt_id'])['revoked']
    with pytest.raises(RunnerConflict):
        effects.begin(*args, 'publish-a')
    # Late acknowledgement can add evidence even after ownership expires.
    effects.settle(*args, 'publish-a', 'SUCCEEDED', {'provider_receipt_id': 'receipt-a'})


def test_recovery_revokes_dispatch_but_keeps_late_receipts(journal):
    owner = owned(journal)
    effects = PostgresRunnerEffects(journal)
    args = ('org-a', owner['attempt_id'], owner['claim_token'], owner['owner_epoch'])
    effects.reserve(*args, 'publish-a', 'd' * 64)
    effects.begin(*args, 'publish-a')
    assert journal.rotate_recovery_epoch('org-a', 'install-a') == 2
    with pytest.raises(RunnerConflict):
        effects.reserve(*args, 'publish-b', 'e' * 64)
    result = effects.settle(*args, 'publish-a', 'SUCCEEDED', {'provider_receipt_id': 'r'})
    assert result['state'] == 'SUCCEEDED'


def test_tenant_scope_and_effect_payload_are_immutable(journal):
    owner = owned(journal)
    effects = PostgresRunnerEffects(journal)
    args = ('org-a', owner['attempt_id'], owner['claim_token'], owner['owner_epoch'])
    effects.reserve(*args, 'publish-a', 'd' * 64)
    with pytest.raises(RunnerConflict, match='another request'):
        effects.reserve(*args, 'publish-a', 'e' * 64)
    with pytest.raises(RunnerConflict, match='not found'):
        effects.reserve('org-b', *args[1:], 'publish-a', 'd' * 64)


def test_same_effect_in_new_attempt_cannot_dispatch_twice(journal):
    first = owned(journal)
    effects = PostgresRunnerEffects(journal)
    original = ('org-a', first['attempt_id'], first['claim_token'], first['owner_epoch'])
    effects.reserve(*original, 'publish-a', 'd' * 64)
    effects.begin(*original, 'publish-a')
    second_plan = plan(attempt='e' * 32)
    journal.create(second_plan, 'install-a', 'execution-a')
    second = journal.claim('org-a', 'e' * 32, 1, 30)
    retry = ('org-a', second['attempt_id'], second['claim_token'], second['owner_epoch'])
    existing = effects.reserve(*retry, 'publish-a', 'd' * 64)
    assert existing['state'] == 'IN_FLIGHT'
    assert existing['attempt_id'] == first['attempt_id']
    with pytest.raises(RunnerConflict, match='again'):
        effects.begin(*retry, 'publish-a')


def test_crash_after_begin_remains_fenced_without_settlement(journal):
    owner = owned(journal)
    effects = PostgresRunnerEffects(journal)
    args = ('org-a', owner['attempt_id'], owner['claim_token'], owner['owner_epoch'])
    effects.reserve(*args, 'publish-a', 'd' * 64)
    effects.begin(*args, 'publish-a')
    with journal.transaction("org-a") as cursor:
        cursor.execute('UPDATE sandbox_runner_attempts SET lease_until=0')
    with pytest.raises(RunnerConflict, match='Unresolved'):
        journal.claim('org-a', owner['attempt_id'], owner['revision'], 30)


def test_stale_owner_and_changed_plan_cannot_modify_attempt(journal):
    owner = owned(journal)
    immutable = RunnerPlan.model_validate_json(owner['plan_json'])
    assert journal.create(immutable, 'install-a', 'execution-a')['owner_epoch'] == 1
    with pytest.raises(RunnerConflict, match='immutable'):
        journal.create(immutable.model_copy(update={'config_revision': 2}),
                       'install-a', 'execution-a')
    with journal.transaction("org-a") as cursor:
        cursor.execute('UPDATE sandbox_runner_attempts SET lease_until=0')
    successor = journal.claim('org-a', owner['attempt_id'], owner['revision'], 30)
    assert successor['owner_epoch'] == 2
    with pytest.raises(RunnerConflict, match='ownership'):
        journal.renew('org-a', owner['attempt_id'], owner['claim_token'], 1, 30)


def test_revoke_blocks_new_effect_and_terminal_receipt_is_immutable(journal):
    owner = owned(journal)
    effects = PostgresRunnerEffects(journal)
    args = ('org-a', owner['attempt_id'], owner['claim_token'], owner['owner_epoch'])
    effects.reserve(*args, 'publish-a', 'd' * 64)
    effects.begin(*args, 'publish-a')
    journal.revoke('org-a', owner['attempt_id'])
    with pytest.raises(RunnerConflict):
        effects.reserve(*args, 'publish-b', 'e' * 64)
    receipt = {'provider_receipt_id': 'r'}
    effects.settle(*args, 'publish-a', 'SUCCEEDED', receipt)
    effects.settle(*args, 'publish-a', 'SUCCEEDED', receipt)
    with pytest.raises(RunnerConflict, match='immutable'):
        effects.settle(*args, 'publish-a', 'FAILED', receipt)


def test_failed_transaction_rolls_back_history(journal):
    owner = owned(journal)
    with pytest.raises(RuntimeError):
        with journal.transaction("org-a") as cursor:
            journal.history(cursor, owner, 'MUST_ROLL_BACK')
            raise RuntimeError('intentional transaction abort')
    with journal.transaction("org-a") as cursor:
        cursor.execute("SELECT count(*) AS total FROM sandbox_runner_history "
                       "WHERE event='MUST_ROLL_BACK'")
        assert cursor.fetchone()['total'] == 0


def test_rls_blocks_unscoped_sql_for_restricted_test_role(journal):
    owned(journal)
    journal.register_installation('org-b', 'install-b')
    with journal.transaction('org-a') as cursor:
        cursor.execute('SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user')
        role = cursor.fetchone()
        if role['rolsuper'] or role['rolbypassrls']:
            pytest.skip('RLS evidence requires a non-superuser non-BYPASSRLS test role.')
        cursor.execute('SELECT organization_id FROM sandbox_runner_installations')
        assert {row['organization_id'] for row in cursor.fetchall()} == {'org-a'}
        cursor.execute("UPDATE sandbox_runner_installations SET recovery_epoch=999 "
                       "WHERE organization_id='org-b'")
        assert cursor.rowcount == 0
