"""Execution evidence migration with real SQLite/PostgreSQL; source only, unrun."""
import json
import sqlite3
import uuid

import pytest

from governance.models import PolicyDocument
from storage.configuration_snapshot import MigrationConflict
from storage.execution_snapshot import extract_execution_history
from storage.execution_postgres import ExecutionHistoryMigration
from storage.postgres_execution_history import PostgresExecutionHistory
from poc.tests.test_configuration_migration import source, authorize_admin
from poc.tests.test_runner_postgres import journal


@pytest.fixture
def history_source(source):
    with sqlite3.connect(source) as connection:
        connection.execute('PRAGMA foreign_keys=ON')
        connection.execute('INSERT INTO agents (id,name,system_prompt,organization_id,department_id) '
            "VALUES ('agent-a','Agent','Fixture','org-a','dept-org-a')")
        connection.execute('INSERT INTO task_runs (run_id,agent_id,prompt,status,created_at,organization_id) '
            "VALUES ('task-a','agent-a','Fixture','WAITING_APPROVAL','2026-11-20','org-a')")
        connection.execute('INSERT INTO workflow_executions (id,workflow_id,trigger_type,status,department_id) '
            "VALUES ('exec-a','wf-org-a','MANUAL','WAITING_APPROVAL','dept-org-a')")
        connection.execute('INSERT INTO workflow_step_runs (id,execution_id,step_key,agent_id,status,task_run_id) '
            "VALUES ('step-a','exec-a','review','agent-a','WAITING_APPROVAL','task-a')")
        policy = PolicyDocument().model_dump()
        context = {'organization_id': 'org-a', 'department_id': 'dept-org-a', 'workflow_revision': 1,
            'initiator_id': 'user-org-a', 'governance': {'organization_id': 'org-a',
                'department_id': 'dept-org-a', 'policies': [
                    {'organization_id': 'org-a', 'scope_type': 'organization', 'scope_id': 'org-a',
                     'revision': 1, 'document': policy},
                    {'organization_id': 'org-a', 'scope_type': 'department', 'scope_id': 'dept-org-a',
                     'revision': 0, 'document': policy}]}}
        connection.execute('INSERT INTO workflow_execution_tool_contexts VALUES (?,?)',
                           ('exec-a', json.dumps(context)))
        scope = {'organization_id': 'org-a', 'department_id': 'dept-org-a',
                 'workflow_id': 'wf-org-a', 'agent_id': 'agent-a', 'entries': []}
        connection.execute('INSERT INTO workflow_tool_scopes VALUES (?,?,?)',
                           ('task-a', 'exec-a', json.dumps(scope)))
        connection.execute('INSERT INTO workflow_approvals '
            '(id,execution_id,step_run_id,task_id,organization_id,department_id,workflow_revision,'
            'status,config_json,subjects_json,report,created_at,expires_at,receipts_json) '
            "VALUES ('wfa_a','exec-a','step-a','task-a','org-a','dept-org-a',1,'RESOLVING',"
            "'{}','[]','Private report','2026-11-20','2026-11-21',?)",
            (json.dumps([{'status': 'UNKNOWN', 'operation': 'merge', 'opaque': 'retain-exactly'}]),))
        connection.execute('INSERT INTO workflow_dag_approvals '
            '(id,execution_id,step_key,workflow_revision,organization_id,department_id,initiator_id,'
            'policy_json,checkpoint_json,status,expires_at) '
            "VALUES ('dag-a','exec-a','gate',1,'org-a','dept-org-a','user-org-a','{}','{}','APPROVED',9999999999)")
        connection.execute('INSERT INTO workflow_dag_approval_votes VALUES (?,?,?,?)',
                           ('dag-a', 'user-org-a', 1, 1795132800))
        # Binding/link may legitimately have been removed; receipts must survive.
        connection.execute('INSERT INTO pr_channel_deliveries '
            '(approval_id,binding_id,status,retry_at,token_digest) VALUES (?,?,?,?,?)',
            ('wfa_a', 'deleted-binding', 'UNCONFIRMED', 0, 'private-token-digest'))
    return source


@pytest.fixture
def history_migration(journal):
    value = ExecutionHistoryMigration(journal.connect, 'history_' + uuid.uuid4().hex)
    try:
        yield value
    finally:
        from psycopg2 import sql
        with journal.transaction('org-a') as cursor:
            cursor.execute(sql.SQL('DROP SCHEMA IF EXISTS {} CASCADE').format(
                sql.Identifier(value.namespace)))


def test_history_preview_preserves_opaque_receipt_without_exposing_private_data(history_source):
    snapshot = extract_execution_history(history_source, 'org-a')
    assert len(snapshot.rows) == 29
    receipt = snapshot.rows['workflow_approvals'][0]['receipts_json']
    assert json.loads(receipt)[0]['opaque'] == 'retain-exactly'
    report = snapshot.report()
    assert report['format_version'] == 2 and not report['replay_allowed']
    assert report['held_executions'] == 1
    assert 'private-token-digest' not in json.dumps(report)
    assert 'Private report' not in repr(snapshot)


def test_frozen_context_tenant_mismatch_is_rejected(history_source):
    with sqlite3.connect(history_source) as connection:
        connection.execute('UPDATE workflow_execution_tool_contexts SET context_json=?',
            (json.dumps({'organization_id': 'org-b'}),))
    with pytest.raises(MigrationConflict, match='another execution scope'):
        extract_execution_history(history_source, 'org-a')


def test_duplicate_json_keys_cannot_hide_another_organization(history_source):
    with sqlite3.connect(history_source) as connection:
        connection.execute('UPDATE workflow_execution_tool_contexts SET context_json=?',
            ('{"organization_id":"org-b","organization_id":"org-a"}',))
    with pytest.raises(MigrationConflict, match='Invalid historical JSON'):
        extract_execution_history(history_source, 'org-a')


def test_surviving_foreign_task_is_not_misclassified_as_deleted(history_source):
    with sqlite3.connect(history_source) as connection:
        connection.execute("UPDATE task_runs SET organization_id='org-b' WHERE run_id='task-a'")
    with pytest.raises(MigrationConflict, match='another organization in task_runs'):
        extract_execution_history(history_source, 'org-a')


def test_approval_cannot_reference_step_from_another_execution(history_source):
    with sqlite3.connect(history_source) as connection:
        connection.execute('INSERT INTO workflow_executions (id,workflow_id,trigger_type,department_id) '
            "VALUES ('exec-other','wf-org-a','MANUAL','dept-org-a')")
        connection.execute("UPDATE workflow_step_runs SET execution_id='exec-other' WHERE id='step-a'")
    with pytest.raises(MigrationConflict, match='another execution'):
        extract_execution_history(history_source, 'org-a')


def test_import_preserves_states_and_quarantines_all_replay(history_source, history_migration):
    snapshot = extract_execution_history(history_source, 'org-a')
    result = history_migration.apply(snapshot, expected_sha256=snapshot.sha256)
    assert result == history_migration.apply(snapshot, expected_sha256=snapshot.sha256)
    assert not result['replay_allowed'] and not result['cutover_ready']
    with history_migration.transaction('org-a') as cursor:
        assert history_migration.read_rows(cursor, 'org-a') == snapshot.rows
        cursor.execute('SELECT * FROM execution_recovery_holds')
        hold = cursor.fetchone()
        assert not hold['replay_allowed']
        assert 'UNRESOLVED_EXTERNAL_EFFECT' in json.loads(hold['reasons_json'])
    view = PostgresExecutionHistory(history_migration.connect, history_migration.namespace)
    execution = view.get_execution('org-a', 'exec-a', validator=authorize_admin)
    assert execution['status'] == 'WAITING_APPROVAL' and execution['archive_only']
    summary = view.approval_history('org-a', 'exec-a', validator=authorize_admin)
    assert summary['terminal'][0]['receipt_states'] == ['UNKNOWN']
    assert 'Private report' not in json.dumps(summary)
    assert view.get_execution('org-b', 'exec-a', validator=authorize_admin) is None
    with pytest.raises(MigrationConflict, match='read-only'):
        view.update_workflow()
    with pytest.raises(MigrationConflict, match='not current execution authority'):
        view.capture_policies()
    with pytest.raises(MigrationConflict, match='authorized execution history'):
        view.get_workflow('org-a', 'wf-org-a')


def test_missing_hold_is_not_automatically_repaired_on_retry(history_source, history_migration):
    snapshot = extract_execution_history(history_source, 'org-a')
    history_migration.apply(snapshot, expected_sha256=snapshot.sha256)
    with history_migration.transaction('org-a') as cursor:
        cursor.execute('DELETE FROM execution_recovery_holds')
    with pytest.raises(MigrationConflict, match='hold is missing'):
        history_migration.apply(snapshot, expected_sha256=snapshot.sha256)


def test_historical_approval_does_not_override_revoked_reader(history_source, history_migration):
    snapshot = extract_execution_history(history_source, 'org-a')
    history_migration.apply(snapshot, expected_sha256=snapshot.sha256)
    view = PostgresExecutionHistory(history_migration.connect, history_migration.namespace)
    with history_migration.transaction('org-a') as cursor:
        cursor.execute("UPDATE users SET status='INACTIVE' WHERE id='user-org-a'")
    with pytest.raises(MigrationConflict, match='Current administrator'):
        view.get_execution('org-a', 'exec-a', validator=authorize_admin)
