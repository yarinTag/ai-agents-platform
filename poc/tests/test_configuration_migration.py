"""Actual SQLite schema and disposable PostgreSQL import, no service mocks.

Source only; not executed. PostgreSQL fixture requires an explicit disposable DSN.
"""
import json
import sqlite3
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest

from governance.models import PolicyDocument
from storage.configuration_postgres import ConfigurationMigration
from storage.configuration_snapshot import MigrationConflict, extract_configuration
from storage.execution_schema import initialize as execution_schema
from storage.integration_schema import initialize as integration_schema
from storage.organization_schema import initialize as organization_schema
from storage.workflow_schema import initialize as workflow_schema
from storage.workflows import WorkflowsRepository
from storage.postgres_configuration_store import PostgresConfigurationStore
from poc.tests.test_runner_postgres import journal  # Shared real PostgreSQL fixture.


@pytest.fixture
def source(tmp_path):
    path = tmp_path / 'source.sqlite'
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA foreign_keys=ON')
    execution_schema(connection)
    integration_schema(connection)
    organization_schema(connection)
    repository = WorkflowsRepository(None)
    workflow_schema(connection, repository._insert_workflow_revision)
    for org in ('org-a', 'org-b'):
        connection.execute('INSERT INTO organizations (id,name,slug) VALUES (?,?,?)',
                           (org, org, org))
        connection.execute('INSERT INTO departments (id,name,organization_id) VALUES (?,?,?)',
                           ('dept-' + org, org, org))
        connection.execute('INSERT INTO users (id,organization_id,email,full_name,role) '
                           'VALUES (?,?,?,?,?)',
                           ('user-' + org, org, org + '@example.invalid', org, 'ORG_ADMIN'))
        connection.execute('INSERT INTO workflows (id,name,department_id,organization_id,'
            'definition_json,is_active) VALUES (?,?,?,?,?,?)',
            ('wf-' + org, org, 'dept-' + org, org, '{"steps":[]}', 0))
        row = dict(connection.execute('SELECT * FROM workflows WHERE id=?',
                                      ('wf-' + org,)).fetchone())
        repository._insert_workflow_revision(connection, row, [], None, 'Fixture', None,
                                             '2026-11-20T00:00:00+00:00')
    policy = PolicyDocument().model_dump_json()
    values = ('org-a', 'organization', 'org-a', 1, policy, 'user-org-a', '2026-11-20')
    connection.execute('INSERT INTO capability_policies VALUES (?,?,?,?,?,?,?)', values)
    connection.execute('INSERT INTO capability_policy_revisions VALUES (?,?,?,?,?,?,?)', values)
    connection.execute('INSERT INTO organization_provider_credentials '
        '(organization_id,provider,ciphertext,nonce,version,updated_at) VALUES (?,?,?,?,?,?)',
        ('org-a', 'fixture', b'ciphertext-not-plaintext', b'nonce', 7, '2026-11-20'))
    connection.commit()
    connection.close()
    return path


@pytest.fixture
def migration(journal):
    namespace = 'configuration_' + uuid.uuid4().hex
    value = ConfigurationMigration(journal.connect, namespace)
    try:
        yield value
    finally:
        from psycopg2 import sql
        with journal.transaction('org-a') as cursor:
            cursor.execute(sql.SQL('DROP SCHEMA IF EXISTS {} CASCADE').format(
                sql.Identifier(namespace)))


def test_preview_is_scoped_repeatable_and_hides_sensitive_payload(source):
    first = extract_configuration(source, 'org-a')
    second = extract_configuration(source, 'org-a')
    assert first.sha256 == second.sha256
    assert {row['id'] for row in first.rows['workflows']} == {'wf-org-a'}
    assert first.rows['organization_provider_credentials'][0]['ciphertext'] == b'ciphertext-not-plaintext'
    rendered = json.dumps(first.report())
    assert 'ciphertext-not-plaintext' not in rendered
    assert not first.report()['cutover_ready']
    assert 'ciphertext-not-plaintext' not in repr(first)


def test_missing_source_is_not_created(tmp_path):
    path = tmp_path / 'missing.sqlite'
    with pytest.raises(FileNotFoundError):
        extract_configuration(path, 'org-a')
    assert not path.exists()


def test_cross_tenant_workflow_department_is_rejected(source):
    with sqlite3.connect(source) as connection:
        connection.execute("UPDATE workflows SET department_id='dept-org-b' WHERE id='wf-org-a'")
    with pytest.raises(MigrationConflict, match='foreign reference'):
        extract_configuration(source, 'org-a')


def test_source_drift_and_missing_history_are_rejected(source):
    with sqlite3.connect(source) as connection:
        connection.execute("DELETE FROM workflow_revisions WHERE workflow_id='wf-org-a'")
    with pytest.raises(MigrationConflict, match='revision is missing'):
        extract_configuration(source, 'org-a')
    with sqlite3.connect(source) as connection:
        connection.execute('ALTER TABLE workflows ADD COLUMN unknown_contract TEXT')
    with pytest.raises(MigrationConflict, match='schema drift'):
        extract_configuration(source, 'org-a')


def test_real_postgres_roundtrip_retains_revision_policy_and_encrypted_bytes(source, migration):
    snapshot = extract_configuration(source, 'org-a')
    first = migration.apply(snapshot, expected_sha256=snapshot.sha256)
    assert first == migration.apply(snapshot, expected_sha256=snapshot.sha256)
    with migration.transaction('org-a') as cursor:
        rows = migration.read_rows(cursor, 'org-a')
    assert rows == snapshot.rows
    assert rows['workflows'][0]['is_active'] == 0


def test_changed_preview_or_target_data_cannot_be_overwritten(source, migration):
    snapshot = extract_configuration(source, 'org-a')
    with pytest.raises(MigrationConflict, match='approved preview'):
        migration.apply(snapshot, expected_sha256='0' * 64)
    migration.apply(snapshot, expected_sha256=snapshot.sha256)
    with migration.transaction('org-a') as cursor:
        cursor.execute("UPDATE workflows SET name='changed' WHERE id='wf-org-a'")
    with pytest.raises(MigrationConflict, match='history is inconsistent'):
        migration.apply(snapshot, expected_sha256=snapshot.sha256)


def test_source_change_requires_new_target_not_merge(source, migration):
    snapshot = extract_configuration(source, 'org-a')
    migration.apply(snapshot, expected_sha256=snapshot.sha256)
    with sqlite3.connect(source) as connection:
        connection.execute("UPDATE organizations SET name='New name' WHERE id='org-a'")
    changed = extract_configuration(source, 'org-a')
    with pytest.raises(MigrationConflict, match='another snapshot'):
        migration.apply(changed, expected_sha256=changed.sha256)


def test_postgres_tenant_boundary_does_not_depend_on_source_filters(source, migration):
    snapshot = extract_configuration(source, 'org-a')
    migration.apply(snapshot, expected_sha256=snapshot.sha256)
    foreign = extract_configuration(source, 'org-b')
    migration.apply(foreign, expected_sha256=foreign.sha256)
    with migration.transaction('org-b') as cursor:
        rows = migration.read_rows(cursor, 'org-b')
    assert {row['id'] for row in rows['workflows']} == {'wf-org-b'}


def authorize_admin(cursor, *_):
    cursor.execute("SELECT role,status FROM users WHERE organization_id='org-a' AND id='user-org-a'")
    user = cursor.fetchone()
    if not user or user['role'] != 'ORG_ADMIN' or user['status'] != 'ACTIVE':
        raise MigrationConflict('Current administrator required.')


def test_workflow_cas_noop_and_revocation_use_current_postgres_state(source, migration):
    snapshot = extract_configuration(source, 'org-a')
    migration.apply(snapshot, expected_sha256=snapshot.sha256)
    store = PostgresConfigurationStore(migration.connect, migration.namespace)
    kwargs = {'actor_id': 'user-org-a', 'actor_label': 'Admin', 'validator': authorize_admin}
    updated = store.update_workflow('org-a', 'wf-org-a', 1, {'name': 'Changed'}, **kwargs)
    assert updated['revision'] == 2
    assert store.update_workflow('org-a', 'wf-org-a', 2, {'name': 'Changed'}, **kwargs)['revision'] == 2
    with pytest.raises(MigrationConflict, match='revision conflict'):
        store.update_workflow('org-a', 'wf-org-a', 1, {'name': 'Stale'}, **kwargs)
    assert store.get_workflow('org-b', 'wf-org-a') is None
    with migration.transaction('org-a') as cursor:
        cursor.execute("UPDATE users SET status='INACTIVE' WHERE id='user-org-a'")
    with pytest.raises(MigrationConflict, match='Current administrator'):
        store.update_workflow('org-a', 'wf-org-a', 2, {'name': 'Blocked'}, **kwargs)


def test_policy_revision_and_atomic_two_layer_capture(source, migration):
    snapshot = extract_configuration(source, 'org-a')
    migration.apply(snapshot, expected_sha256=snapshot.sha256)
    store = PostgresConfigurationStore(migration.connect, migration.namespace)
    revision = store.save_policy('org-a', 'department', 'dept-org-a',
        PolicyDocument(default='deny'), 0, actor_id='user-org-a', validator=authorize_admin)
    assert revision == 1
    captured = store.capture_policies('org-a', 'dept-org-a')
    assert [row['scope_type'] for row in captured['policies']] == ['organization', 'department']
    assert captured['policies'][1]['document']['default'] == 'deny'
    with pytest.raises(MigrationConflict, match='revision conflict'):
        store.save_policy('org-a', 'department', 'dept-org-a', PolicyDocument(), 0,
                          actor_id='user-org-a', validator=authorize_admin)
    with pytest.raises(MigrationConflict, match='not in the organization'):
        store.capture_policies('org-a', 'dept-org-b')


def test_two_first_policy_writes_cannot_overwrite_each_other(source, migration):
    snapshot = extract_configuration(source, 'org-a')
    migration.apply(snapshot, expected_sha256=snapshot.sha256)
    store = PostgresConfigurationStore(migration.connect, migration.namespace)
    def save():
        try:
            return store.save_policy('org-a', 'department', 'dept-org-a',
                PolicyDocument(default='deny'), 0, actor_id='user-org-a', validator=authorize_admin)
        except MigrationConflict:
            return None
    with ThreadPoolExecutor(max_workers=2) as workers:
        assert [value for value in workers.map(lambda _: save(), range(2))
                if value is not None] == [1]


def test_target_constraint_failure_rolls_back_entire_tenant_import(source, migration):
    first = extract_configuration(source, 'org-a')
    migration.apply(first, expected_sha256=first.sha256)
    with migration.transaction('org-a') as cursor:
        cursor.execute("UPDATE users SET email='org-b@example.invalid' WHERE id='user-org-a'")
    second = extract_configuration(source, 'org-b')
    with pytest.raises(MigrationConflict, match='transaction rolled back'):
        migration.apply(second, expected_sha256=second.sha256)
    with migration.transaction('org-b') as cursor:
        cursor.execute("SELECT count(*) AS count FROM organizations WHERE id='org-b'")
        assert cursor.fetchone()['count'] == 0
