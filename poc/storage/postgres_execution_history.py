"""Authorized read-only history views. No decision, dispatch or resume methods."""
import json

from .configuration_snapshot import MigrationConflict
from .execution_migration_spec import schema_document
from .execution_snapshot import json_value
from .postgres_configuration_store import PostgresConfigurationStore


class PostgresExecutionHistory(PostgresConfigurationStore):
    # The shared transaction checks the profile-specific schema signature.
    schema_version = 2
    schema_document = staticmethod(schema_document)

    def get_execution(self, org, execution_id, *, validator):
        """Validator(cursor, raw_execution) enforces current role/department access."""
        if not callable(validator):
            raise MigrationConflict('Current read authorization validator required.')
        with self.transaction(org) as cursor:
            cursor.execute('SELECT * FROM workflow_executions '
                           'WHERE organization_id=%s AND id=%s', (org, execution_id))
            row = cursor.fetchone()
            if row is None:
                return None
            validator(cursor, dict(row))
            cursor.execute('SELECT reasons_json FROM execution_recovery_holds '
                           'WHERE organization_id=%s AND execution_id=%s AND replay_allowed=FALSE',
                           (org, execution_id))
            hold = cursor.fetchone()
            if hold is None:
                raise MigrationConflict('Imported execution recovery hold is missing.')
            fields = ('id', 'workflow_id', 'department_id', 'status', 'trigger_type',
                      'total_input_tokens', 'total_output_tokens', 'total_cost_usd',
                      'started_at', 'completed_at', 'created_at')
            return {**{key: row[key] for key in fields}, 'archive_only': True,
                    'replay_allowed': False, 'recovery_reasons': json.loads(hold['reasons_json'])}

    def load_frozen_context(self, org, execution_id, *, validator):
        """Private inspection only; this raw evidence must not become a live grant."""
        if not callable(validator):
            raise MigrationConflict('Current read authorization validator required.')
        with self.transaction(org) as cursor:
            cursor.execute('SELECT * FROM workflow_executions WHERE organization_id=%s AND id=%s',
                           (org, execution_id))
            row = cursor.fetchone()
            if row is None:
                return None
            validator(cursor, dict(row))
            cursor.execute('SELECT context_json FROM workflow_execution_tool_contexts '
                           'WHERE organization_id=%s AND execution_id=%s', (org, execution_id))
            context = cursor.fetchone()
            return {'archive_only': True, 'replay_allowed': False,
                    'context': json_value(context, 'context_json', dict) if context else None}

    def approval_history(self, org, execution_id, *, validator, limit=50):
        """Bounded evidence summary; no tokens, reports, URLs or resume authority."""
        if not callable(validator) or type(limit) is not int or not 1 <= limit <= 100:
            raise MigrationConflict('Current read validator and bounded limit required.')
        with self.transaction(org) as cursor:
            cursor.execute('SELECT * FROM workflow_executions WHERE organization_id=%s AND id=%s',
                           (org, execution_id))
            execution = cursor.fetchone()
            if execution is None:
                return None
            validator(cursor, dict(execution))
            cursor.execute('SELECT id,status,workflow_revision,position,receipts_json '
                'FROM workflow_approvals WHERE organization_id=%s AND execution_id=%s '
                'ORDER BY position,id LIMIT %s', (org, execution_id, limit))
            terminal = []
            for row in cursor.fetchall():
                receipts = json_value(row, 'receipts_json', list)
                terminal.append({**{key: row[key] for key in ('id', 'status', 'workflow_revision', 'position')},
                    'receipt_states': [item.get('status') for item in receipts[:20]],
                    'omitted_receipts': max(0, len(receipts) - 20)})
            cursor.execute('SELECT id,status,workflow_revision,step_key,decided_at '
                'FROM workflow_dag_approvals WHERE organization_id=%s AND execution_id=%s '
                'ORDER BY id LIMIT %s', (org, execution_id, limit))
            return {'archive_only': True, 'replay_allowed': False,
                    'terminal': terminal, 'dag': [dict(row) for row in cursor.fetchall()]}

    def update_workflow(self, *args, **kwargs):
        raise MigrationConflict('Execution archive is read-only.')

    def get_workflow(self, *args, **kwargs):
        raise MigrationConflict('Use an authorized execution history view.')

    def save_policy(self, *args, **kwargs):
        raise MigrationConflict('Execution archive is read-only.')

    def capture_policies(self, *args, **kwargs):
        raise MigrationConflict('Archived policy is not current execution authority.')
