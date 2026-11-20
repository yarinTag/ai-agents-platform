"""Execution evidence extraction. Imported contexts and decisions never grant replay."""
import json
from dataclasses import dataclass

from governance.models import PolicyDocument
from . import configuration_migration_spec as config
from . import execution_migration_spec as spec
from .configuration_snapshot import (
    ConfigurationSnapshot, MigrationConflict, digest, extract_rows,
    validate_inventory, validate_rows as validate_configuration,
)

LIVE_APPROVALS = {'NOTIFYING', 'PENDING', 'RESOLVING', 'EXPIRING'}
TERMINAL_EXECUTIONS = {'COMPLETED', 'FAILED', 'CANCELLED'}


def json_value(row, column, expected):
    def reject_constant(_):
        raise ValueError('Non-finite JSON value.')

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate JSON key.')
            result[key] = value
        return result
    try:
        value = json.loads(row[column], object_pairs_hook=pairs, parse_constant=reject_constant)
        if not isinstance(value, expected):
            raise ValueError()
        return value
    except (ValueError, TypeError, RecursionError):
        raise MigrationConflict(f'Invalid historical JSON in {column}.') from None


def validate_rows(org, rows):
    validate_inventory(org, rows, spec.TABLES, spec.REFERENCES, spec.REQUIRED, spec.UNIQUES)
    validate_configuration(org, {table.name: rows[table.name] for table in config.TABLES})
    executions = {r['id']: r for r in rows['workflow_executions']}
    steps = {r['id']: r for r in rows['workflow_step_runs']}
    revisions = {(r['workflow_id'], r['revision']) for r in rows['workflow_revisions']}
    active = set()
    for table in ('workflow_approvals', 'workflow_dag_approvals'):
        for row in rows[table]:
            execution = executions[row['execution_id']]
            if row['department_id'] != execution['department_id'] or (
                    execution['workflow_id'], row['workflow_revision']) not in revisions:
                raise MigrationConflict('Approval execution scope or pinned revision is inconsistent.')
            if table == 'workflow_approvals':
                step = steps[row['step_run_id']]
                if step['execution_id'] != row['execution_id'] or (
                        step['task_run_id'] is not None and step['task_run_id'] != row['task_id']):
                    raise MigrationConflict('Approval step/task belongs to another execution.')
                if row['position'] < 0 or row['advance_pending'] not in (0, 1):
                    raise MigrationConflict('Invalid approval sequence metadata.')
                if row['status'] in LIVE_APPROVALS:
                    if row['execution_id'] in active:
                        raise MigrationConflict('Multiple live terminal approvals in one execution.')
                    active.add(row['execution_id'])
                json_value(row, 'config_json', dict)
                for column in ('subjects_json', 'remaining_json', 'receipts_json'):
                    if any(not isinstance(item, dict) for item in json_value(row, column, list)):
                        raise MigrationConflict('Invalid structured approval evidence.')
            else:
                if row['status'] not in {'PENDING', 'APPROVED', 'REJECTED', 'TIMED_OUT', 'CLAIMED'}:
                    raise MigrationConflict('Unsupported DAG approval state.')
                json_value(row, 'policy_json', dict)
                json_value(row, 'checkpoint_json', dict)
    for row in rows['run_evaluations']:
        if row['workflow_id'] != executions[row['execution_id']]['workflow_id']:
            raise MigrationConflict('Evaluation refers to another workflow.')
    for row in rows['workflow_dag_approval_votes']:
        if row['decision'] not in (0, 1):
            raise MigrationConflict('Invalid recorded approval vote.')
    channel_ids = set()
    for row in rows['channel_bindings']:
        identity = (row['department_id'] or '', row['connector_id'], row['channel_id'])
        if identity in channel_ids or row['revision'] < 1 or any(
                row[name] not in (0, 1) for name in (
                    'send_notifications', 'trigger_workflows', 'approve_decisions')):
            raise MigrationConflict('Invalid or duplicate channel binding.')
        channel_ids.add(identity)
    for table, column in (('workflow_execution_tool_contexts', 'context_json'),
                          ('workflow_tool_scopes', 'scope_json'),
                          ('workflow_repo_workspaces', 'workspace_json')):
        for row in rows[table]:
            value = json_value(row, column, dict)
            execution = executions[row['execution_id']]
            expected = {'organization_id': org, 'department_id': execution['department_id'],
                        'workflow_id': execution['workflow_id'], 'execution_id': execution['id']}
            if any(key in value and value[key] != wanted for key, wanted in expected.items()):
                raise MigrationConflict('Frozen context belongs to another execution scope.')
            if 'workflow_revision' in value:
                revision = value['workflow_revision']
                if type(revision) is not int or (execution['workflow_id'], revision) not in revisions:
                    raise MigrationConflict('Frozen context pinned revision is missing.')
            if 'governance' in value:
                governance = value['governance']
                if not isinstance(governance, dict) or any(
                    governance.get(key) != expected[key] for key in ('organization_id', 'department_id')):
                    raise MigrationConflict('Frozen governance ownership differs from execution.')
                policies = governance.get('policies')
                if not isinstance(policies, list):
                    raise MigrationConflict('Invalid frozen policy collection.')
                scopes = set()
                for policy in policies:
                    if not isinstance(policy, dict) or policy.get('organization_id') != org:
                        raise MigrationConflict('Invalid frozen policy ownership.')
                    scope = policy.get('scope_type')
                    expected_scope = org if scope == 'organization' else execution['department_id']
                    if (not isinstance(scope, str) or scope not in {'organization', 'department'} or scope in scopes or
                            policy.get('scope_id') != expected_scope or
                            type(policy.get('revision')) is not int or policy['revision'] < 0):
                        raise MigrationConflict('Invalid frozen policy scope or revision.')
                    scopes.add(scope)
                    try:
                        PolicyDocument.model_validate(policy['document'])
                    except (ValueError, KeyError, TypeError):
                        raise MigrationConflict('Invalid frozen policy document.') from None


def recovery_reasons(rows):
    reasons = {r['id']: {'ARCHIVE_ONLY'} for r in rows['workflow_executions']}
    contexts = {r['execution_id'] for r in rows['workflow_execution_tool_contexts']}
    for row in rows['workflow_executions']:
        if row['status'] not in TERMINAL_EXECUTIONS:
            reasons[row['id']].add('ACTIVE_OR_UNRECOGNIZED_SOURCE_STATE')
        if row['id'] not in contexts:
            reasons[row['id']].add('MISSING_FROZEN_CONTEXT')
    for row in rows['workflow_execution_tool_contexts']:
        value = json_value(row, 'context_json', dict)
        governance = value.get('governance') or {}
        if (not {'organization_id', 'department_id', 'workflow_revision', 'governance'} <= value.keys()
                or len(governance.get('policies', [])) != 2):
            reasons[row['execution_id']].add('LEGACY_OR_INCOMPLETE_FROZEN_CONTEXT')
    for row in rows['workflow_approvals']:
        if row['status'] in LIVE_APPROVALS or row['advance_pending']:
            reasons[row['execution_id']].add('APPROVAL_OR_ADVANCEMENT_PENDING')
        if any(receipt.get('status') in {'STARTED', 'UNKNOWN'}
               for receipt in json_value(row, 'receipts_json', list)):
            reasons[row['execution_id']].add('UNRESOLVED_EXTERNAL_EFFECT')
    for row in rows['workflow_dag_approvals']:
        if row['status'] in {'PENDING', 'APPROVED', 'CLAIMED'}:
            reasons[row['execution_id']].add('DAG_CONTINUATION_REQUIRES_RECONCILIATION')
    for table, parent in (('pr_channel_deliveries', 'workflow_approvals'),
                          ('dag_channel_deliveries', 'workflow_dag_approvals')):
        approvals = {r['id']: r['execution_id'] for r in rows[parent]}
        for row in rows[table]:
            if row['status'] in {'QUEUED', 'SENDING', 'UNCONFIRMED'}:
                reasons[approvals[row['approval_id']]].add('DELIVERY_REQUIRES_RECONCILIATION')
    return {key: sorted(value) for key, value in reasons.items()}


def snapshot_digest(org, rows):
    return digest({'format_version': 2, 'organization_id': org, 'rows': rows})


@dataclass(frozen=True)
class ExecutionSnapshot(ConfigurationSnapshot):
    def report(self):
        report = super().report()
        return {**report, 'format_version': 2, 'scope': 'execution_history',
                'held_executions': len(self.rows['workflow_executions']), 'replay_allowed': False}


def extract_execution_history(source_path, organization_id, *, max_rows=100000):
    from .execution_source_ownership import validate_source_ownership
    rows = extract_rows(source_path, organization_id, tables=spec.TABLES,
                        max_rows=max_rows, source_validator=validate_source_ownership)
    validate_rows(organization_id, rows)
    return ExecutionSnapshot(organization_id, rows, snapshot_digest(organization_id, rows))
