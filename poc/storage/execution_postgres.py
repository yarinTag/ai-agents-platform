"""Archive-only execution migration, sharing the configuration import engine."""
import json

from . import execution_migration_spec as spec
from .configuration_postgres import ConfigurationMigration
from .configuration_snapshot import MigrationConflict
from .execution_snapshot import recovery_reasons, snapshot_digest, validate_rows


class ExecutionHistoryMigration(ConfigurationMigration):
    tables = spec.TABLES
    references = spec.REFERENCES
    required = spec.REQUIRED
    uniques = spec.UNIQUES
    checks = spec.CHECKS
    format_version = 2
    scope = 'execution_history'
    schema_document = staticmethod(spec.schema_document)
    validate_rows = staticmethod(validate_rows)
    snapshot_digest = staticmethod(snapshot_digest)

    @classmethod
    def report_metadata(cls, rows):
        return {'held_executions': len(rows['workflow_executions']), 'replay_allowed': False}

    @classmethod
    def bootstrap(cls, cursor):
        super().bootstrap(cursor)
        cursor.execute('''CREATE UNIQUE INDEX IF NOT EXISTS history_live_terminal_approval
            ON workflow_approvals(execution_id)
            WHERE status IN ('NOTIFYING','PENDING','RESOLVING','EXPIRING')''')
        cursor.execute('''CREATE UNIQUE INDEX IF NOT EXISTS history_channel_identity
            ON channel_bindings(organization_id,COALESCE(department_id,''),connector_id,channel_id)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS execution_recovery_holds (
            organization_id TEXT NOT NULL, execution_id TEXT NOT NULL,
            source_sha256 TEXT NOT NULL, reasons_json TEXT NOT NULL,
            replay_allowed BOOLEAN NOT NULL DEFAULT FALSE CHECK (replay_allowed=FALSE),
            PRIMARY KEY (organization_id,execution_id),
            FOREIGN KEY (organization_id,execution_id)
                REFERENCES workflow_executions(organization_id,id))''')
        cursor.execute('ALTER TABLE execution_recovery_holds ENABLE ROW LEVEL SECURITY')
        cursor.execute('ALTER TABLE execution_recovery_holds FORCE ROW LEVEL SECURITY')
        cursor.execute("SELECT 1 FROM pg_policies WHERE schemaname=current_schema() "
                       "AND tablename='execution_recovery_holds' AND policyname='history_tenant'")
        if not cursor.fetchone():
            cursor.execute('''CREATE POLICY history_tenant ON execution_recovery_holds
                USING (organization_id=NULLIF(current_setting('app.current_org_id',true),''))
                WITH CHECK (organization_id=NULLIF(current_setting('app.current_org_id',true),''))''')

    @classmethod
    def finalize(cls, cursor, org, rows, *, new_import):
        source_hash = snapshot_digest(org, rows)
        expected = recovery_reasons(rows)
        cursor.execute('SELECT execution_id,source_sha256,reasons_json,replay_allowed '
                       'FROM execution_recovery_holds WHERE organization_id=%s', (org,))
        present = {row['execution_id']: row for row in cursor.fetchall()}
        if set(present) - set(expected):
            raise MigrationConflict('Unexpected execution recovery hold.')
        for execution, reasons in expected.items():
            encoded = json.dumps(reasons, separators=(',', ':'))
            if execution in present:
                row = present[execution]
                if (row['source_sha256'], row['reasons_json'], row['replay_allowed']) != (
                        source_hash, encoded, False):
                    raise MigrationConflict('Execution recovery hold changed.')
            else:
                if not new_import:
                    raise MigrationConflict('Execution recovery hold is missing on import retry.')
                cursor.execute('INSERT INTO execution_recovery_holds '
                    '(organization_id,execution_id,source_sha256,reasons_json) VALUES (%s,%s,%s,%s)',
                    (org, execution, source_hash, encoded))
