"""Scoped PostgreSQL configuration operations, not active DatabaseManager wiring."""
import json
import re
from contextlib import contextmanager
from datetime import datetime, timezone

from governance.models import PolicyDocument
from .configuration_snapshot import MigrationConflict, digest
from .configuration_migration_spec import WORKFLOW_FIELDS, schema_document


EDITABLE_FIELDS = set(WORKFLOW_FIELDS) - {'organization_id'}


class PostgresConfigurationStore:
    schema_version = 1
    schema_document = staticmethod(schema_document)

    def __init__(self, connect, namespace):
        if (not isinstance(namespace, str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,47}', namespace)
                or namespace == 'public' or namespace.startswith('pg_')):
            raise MigrationConflict('Dedicated configuration namespace required.')
        self.connect = connect
        self.namespace = namespace

    @contextmanager
    def transaction(self, organization_id):
        from psycopg2 import sql
        if not isinstance(organization_id, str) or not organization_id.strip():
            raise MigrationConflict('Explicit current organization required.')
        with self.connect() as connection:
            if connection.autocommit:
                raise MigrationConflict('Atomic configuration transaction required.')
            with connection.cursor() as cursor:
                cursor.execute(sql.SQL('SET LOCAL search_path TO {}, pg_catalog').format(
                    sql.Identifier(self.namespace)))
                cursor.execute("SELECT set_config('app.current_org_id',%s,true)", (organization_id,))
                cursor.execute('SELECT version,signature FROM configuration_schema_version')
                versions = cursor.fetchall()
                if len(versions) != 1 or (versions[0]['version'], versions[0]['signature']) != (
                        self.schema_version, digest(self.schema_document())):
                    raise MigrationConflict('Configuration schema is not initialized.')
                yield cursor

    def get_workflow(self, org, workflow_id):
        with self.transaction(org) as cursor:
            cursor.execute('SELECT * FROM workflows WHERE organization_id=%s AND id=%s',
                           (org, workflow_id))
            row = cursor.fetchone()
            return dict(row) if row else None

    def update_workflow(self, org, workflow_id, expected_revision, changes, *,
                        actor_id, actor_label, validator):
        """Validator must check current identity/grants using this same cursor.

        It receives (cursor, current_row, proposed_changes); no default bypass.
        """
        from psycopg2 import sql
        if not callable(validator) or type(expected_revision) is not int or expected_revision < 1:
            raise MigrationConflict('Current-policy validator and exact revision required.')
        if not isinstance(changes, dict) or set(changes) - EDITABLE_FIELDS:
            raise MigrationConflict('Unsupported workflow mutation.')
        if not isinstance(actor_id, str) or not actor_id or not actor_label:
            raise MigrationConflict('Recorded actor identity required.')
        with self.transaction(org) as cursor:
            cursor.execute('SELECT * FROM workflows WHERE organization_id=%s AND id=%s FOR UPDATE',
                           (org, workflow_id))
            row = cursor.fetchone()
            if row is None:
                raise MigrationConflict('Workflow not found.')
            current = dict(row)
            if row['revision'] != expected_revision:
                raise MigrationConflict('Workflow revision conflict.')
            validator(cursor, dict(current), dict(changes))
            effective = {}
            for name, value in changes.items():
                if name in {'webhook_enabled', 'is_active'}:
                    if type(value) not in {bool, int} or value not in (0, 1):
                        raise MigrationConflict('Workflow flags must be explicit booleans or 0/1.')
                    value = int(value)
                if name == 'definition_json':
                    try:
                        if not isinstance(json.loads(value), dict):
                            raise ValueError()
                        if json.loads(current[name]) == json.loads(value):
                            continue
                    except (TypeError, ValueError):
                        raise MigrationConflict('Workflow definition must be a JSON object.') from None
                if current[name] != value:
                    effective[name] = value
            if not effective:
                return current
            now = datetime.now(timezone.utc).isoformat()
            updated = {**current, **effective, 'revision': expected_revision + 1, 'updated_at': now}
            values = {**effective, 'revision': updated['revision'], 'updated_at': now}
            cursor.execute(sql.SQL('UPDATE workflows SET {} WHERE organization_id=%s AND id=%s'
                ).format(sql.SQL(',').join(sql.SQL('{}=%s').format(sql.Identifier(name))
                                          for name in values)),
                (*values.values(), org, workflow_id))
            cursor.execute('INSERT INTO workflow_revisions (organization_id,workflow_id,revision,'
                'snapshot_json,changed_fields_json,actor_id,actor_label,change_summary,created_at) '
                'VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                (org, workflow_id, updated['revision'],
                 json.dumps({name: updated[name] for name in WORKFLOW_FIELDS}, ensure_ascii=False),
                 json.dumps(sorted(effective)), actor_id, actor_label, 'Configuration updated', now))
            return updated

    @staticmethod
    def scope(cursor, org, scope_type, scope_id):
        if scope_type == 'organization' and scope_id == org:
            return
        if scope_type == 'department':
            cursor.execute('SELECT 1 FROM departments WHERE organization_id=%s AND id=%s FOR SHARE',
                           (org, scope_id))
            if cursor.fetchone():
                return
        raise MigrationConflict('Policy scope is not in the organization.')

    def capture_policies(self, org, department_id):
        """One SQL statement captures both policy layers in one MVCC snapshot."""
        with self.transaction(org) as cursor:
            self.scope(cursor, org, 'department', department_id)
            cursor.execute('SELECT s.scope_type,s.scope_id,p.revision,p.document_json,'
                'p.updated_by,p.updated_at FROM (VALUES (%s,%s),(%s,%s)) '
                'AS s(scope_type,scope_id) LEFT JOIN capability_policies p ON '
                'p.organization_id=%s AND p.scope_type=s.scope_type AND p.scope_id=s.scope_id '
                'ORDER BY s.scope_type DESC',
                ('organization', org, 'department', department_id, org))
            records = []
            for row in cursor.fetchall():
                document = PolicyDocument.model_validate_json(row['document_json']) if (
                    row['document_json'] is not None) else PolicyDocument()
                records.append({'organization_id': org, 'scope_type': row['scope_type'],
                    'scope_id': row['scope_id'], 'revision': row['revision'] or 0,
                    'document': document.model_dump(), 'updated_by': row['updated_by'],
                    'updated_at': row['updated_at']})
            return {'organization_id': org, 'department_id': department_id,
                    'captured_at': datetime.now(timezone.utc).isoformat(), 'policies': records}

    def save_policy(self, org, scope_type, scope_id, document, expected_revision, *,
                    actor_id, validator):
        """Locked current-state validator is mandatory, including no-op writes."""
        if (not callable(validator) or type(expected_revision) is not int or
                expected_revision < 0 or not actor_id):
            raise MigrationConflict('Policy validator, actor and expected revision required.')
        document = PolicyDocument.model_validate(document.model_dump())
        with self.transaction(org) as cursor:
            # A parent row also serializes concurrent first writes (no child yet).
            cursor.execute('SELECT id FROM organizations WHERE organization_id=%s AND id=%s FOR UPDATE',
                           (org, org))
            if not cursor.fetchone():
                raise MigrationConflict('Organization not found.')
            self.scope(cursor, org, scope_type, scope_id)
            cursor.execute('SELECT * FROM capability_policies WHERE organization_id=%s '
                'AND scope_type=%s AND scope_id=%s FOR UPDATE', (org, scope_type, scope_id))
            row = cursor.fetchone()
            current = row['revision'] if row else 0
            if current != expected_revision:
                raise MigrationConflict('Policy revision conflict.')
            previous = PolicyDocument.model_validate_json(row['document_json']) if row else PolicyDocument()
            validator(cursor, {'revision': current, 'document': previous.model_dump()}, document)
            if row and previous.model_dump() == document.model_dump():
                return current
            revision = current + 1
            now = datetime.now(timezone.utc).isoformat()
            values = (org, scope_type, scope_id, revision, document.model_dump_json(), actor_id, now)
            columns = '(organization_id,scope_type,scope_id,revision,document_json,updated_by,updated_at)'
            cursor.execute('INSERT INTO capability_policies ' + columns +
                ' VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (organization_id,scope_type,scope_id) '
                'DO UPDATE SET revision=excluded.revision,document_json=excluded.document_json,'
                'updated_by=excluded.updated_by,updated_at=excluded.updated_at', values)
            cursor.execute('INSERT INTO capability_policy_revisions ' + columns +
                           ' VALUES (%s,%s,%s,%s,%s,%s,%s)', values)
            return revision
