"""Unexecuted AI-56 real SQLite journal contracts; no cluster/provider mocks."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import hashlib
import sqlite3
import time

import pytest

from governance.sandbox_profile import SandboxAttempt, SandboxProfile
from runner.models import OwnedResource, RunnerPlan
from storage.sandbox_runner import RunnerConflict, RunnerJournal, initialize


def make_plan(org='org-a'):
    profile = SandboxProfile(
        profile_id='test-only', revision=1, isolation='vm-isolated',
        runtime_class='test-vm', kubernetes_minor='v1.35',
        image='registry.invalid/agent@sha256:' + 'a' * 64,
        uid=1000, gid=1000, cpu_millis=500, memory_mib=512, scratch_mib=32,
        runtime_cpu_overhead_millis=100, runtime_memory_overhead_mib=64,
        deadline_seconds=3600)
    now = int(time.time())
    return RunnerPlan(
        attempt=SandboxAttempt(organization_id=org, attempt_id='b' * 32,
                               profile_sha256=profile.fingerprint()),
        profile=profile, initiator_id='user', agent_id='agent', environment_id='env',
        domain_id='domain', base_version=0, config_revision=1,
        input_sha256=hashlib.sha256(b'').hexdigest(), requested_at=now,
        deadline_at=now + 3600)


@pytest.fixture
def journal(tmp_path):
    path = tmp_path / 'runner.db'

    @contextmanager
    def connect():
        conn = sqlite3.connect(path, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    with connect() as conn:
        initialize(conn)
    return RunnerJournal(connect)


def test_plan_idempotency_does_not_allow_rebinding(journal):
    plan = make_plan()
    assert journal.create(plan) == journal.create(plan)
    with pytest.raises(RunnerConflict, match='different plan'):
        journal.create(plan.model_copy(update={'base_version': 1}))


def test_other_tenant_cannot_read_or_cancel_attempt(journal):
    plan = make_plan()
    journal.create(plan)
    with pytest.raises(RunnerConflict, match='not found'):
        journal.request_stop('org-b', plan.attempt.attempt_id)
    assert journal.get('org-a', plan.attempt.attempt_id)['state'] == 'Requested'


def test_concurrent_provision_claim_has_one_winner(journal):
    plan = make_plan()
    journal.create(plan)

    def claim(_):
        try:
            return journal.claim('org-a', plan.attempt.attempt_id, 1, 'Provision')
        except RunnerConflict:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        winners = [token for token in pool.map(claim, range(2)) if token]
    assert len(winners) == 1


def test_cancellation_preserves_late_receipt_and_fence(journal):
    plan = make_plan()
    journal.create(plan)
    token = journal.claim('org-a', plan.attempt.attempt_id, 1, 'Provision')
    stopped = journal.request_stop('org-a', plan.attempt.attempt_id)
    tenant = hashlib.sha256(b'org-a').hexdigest()[:24]
    resource = OwnedResource(kind='Namespace', name=f'sbx-{tenant}-' + 'b' * 32, uid='uid-1')
    journal.record_resource('org-a', plan.attempt.attempt_id, token, resource)
    with pytest.raises(RunnerConflict):
        journal.claim('org-a', plan.attempt.attempt_id, stopped['revision'], 'Delete')
    with pytest.raises(RunnerConflict):
        journal.finish('org-a', plan.attempt.attempt_id, token, outcome='NOT_DISPATCHED')
    assert journal.get('org-a', plan.attempt.attempt_id)['revoked'] == 1


def test_unknown_effect_cannot_be_reclaimed_or_declared_success(journal):
    plan = make_plan()
    journal.create(plan)
    token = journal.claim('org-a', plan.attempt.attempt_id, 1, 'Provision')
    journal.finish('org-a', plan.attempt.attempt_id, token, outcome='UNKNOWN')
    row = journal.get('org-a', plan.attempt.attempt_id)
    assert row['operation_state'] == 'UNKNOWN'
    with pytest.raises(RunnerConflict):
        journal.claim('org-a', plan.attempt.attempt_id, row['revision'], 'Delete')
    with pytest.raises(RunnerConflict):
        journal.finish('org-a', plan.attempt.attempt_id, token, outcome='Released')


def test_undispatched_provision_after_stop_cannot_restore_requested(journal):
    plan = make_plan()
    journal.create(plan)
    token = journal.claim('org-a', plan.attempt.attempt_id, 1, 'Provision')
    journal.request_stop('org-a', plan.attempt.attempt_id)
    journal.finish('org-a', plan.attempt.attempt_id, token, outcome='NOT_DISPATCHED')
    row = journal.get('org-a', plan.attempt.attempt_id)
    assert row['state'] == 'Stopping'
    assert row['revoked'] == 1


def test_late_uid_after_unknown_is_preserved_without_unfencing(journal):
    plan = make_plan()
    journal.create(plan)
    token = journal.claim('org-a', plan.attempt.attempt_id, 1, 'Provision')
    journal.finish('org-a', plan.attempt.attempt_id, token, outcome='UNKNOWN')
    tenant = hashlib.sha256(b'org-a').hexdigest()[:24]
    resource = OwnedResource(kind='Namespace', name=f'sbx-{tenant}-' + 'b' * 32, uid='late-uid')
    journal.record_resource('org-a', plan.attempt.attempt_id, token, resource)
    row = journal.get('org-a', plan.attempt.attempt_id)
    assert 'late-uid' in row['resources_json']
    assert row['operation_state'] == 'UNKNOWN'
    assert row['revoked'] == 1
    with pytest.raises(RunnerConflict):
        journal.claim('org-a', plan.attempt.attempt_id, row['revision'], 'Delete')


