"""Explicit transactional configuration import into an isolated PostgreSQL schema.

No live platform switch; executions/approvals/agents/budgets are not migrated here.
"""
import json
import re
from contextlib import contextmanager

from .configuration_migration_spec import CHECKS, REFERENCES, REQUIRED, TABLES, UNIQUES, schema_document
from .configuration_snapshot import (
    MigrationConflict, canonical, digest, snapshot_digest, validate_rows,
)


class ConfigurationMigration:
    tables = TABLES
    references = REFERENCES
    required = REQUIRED
    uniques = UNIQUES
    checks = CHECKS
    format_version = 1
    scope = 'configuration_only'
    schema_document = staticmethod(schema_document)
    validate_rows = staticmethod(validate_rows)
    snapshot_digest = staticmethod(snapshot_digest)

    def __init__(self, connect, namespace):
        if (not isinstance(namespace, str) or
                not re.fullmatch(r'[a-z][a-z0-9_]{0,47}', namespace) or
                namespace == 'public' or namespace.startswith('pg_')):
            raise MigrationConflict('A dedicated PostgreSQL namespace is required.')
        self.connect = connect
        self.namespace = namespace

    @contextmanager
    def transaction(self, org):
        from psycopg2 import sql
        with self.connect() as connection:
            if connection.autocommit:
                raise MigrationConflict('Migration requires an atomic transaction.')
            with connection.cursor() as cursor:
                cursor.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',
                               ('configuration-schema:' + self.namespace,))
                cursor.execute(sql.SQL('CREATE SCHEMA IF NOT EXISTS {}').format(
                    sql.Identifier(self.namespace)))
                cursor.execute(sql.SQL('SET LOCAL search_path TO {}, pg_catalog').format(
                    sql.Identifier(self.namespace)))
                cursor.execute("SELECT set_config('app.current_org_id',%s,true)", (org,))
                yield cursor

    @classmethod
    def bootstrap(cls, cursor):
        from psycopg2 import sql
        signature = digest(cls.schema_document())
        cursor.execute('SELECT tablename FROM pg_tables WHERE schemaname=current_schema()')
        existing = {row['tablename'] for row in cursor.fetchall()}
        if existing and 'configuration_schema_version' not in existing:
            raise MigrationConflict('Target namespace is not an initialized configuration schema.')
        if existing:
            cursor.execute('SELECT version,signature FROM configuration_schema_version')
            versions = cursor.fetchall()
            if len(versions) != 1 or (versions[0]['version'], versions[0]['signature']) != (cls.format_version, signature):
                raise MigrationConflict('Unsupported PostgreSQL configuration schema version.')
        for table in cls.tables:
            columns = list(table.columns)
            if 'organization_id' not in dict(columns):
                columns.insert(0, ('organization_id', 'TEXT'))
            definitions = [sql.SQL('{} {}{}').format(sql.Identifier(name), sql.SQL(kind),
                sql.SQL(' NOT NULL' if name == 'organization_id' or
                        name in cls.required[table.name].split() else ''))
                for name, kind in columns]
            definitions.append(sql.SQL('PRIMARY KEY ({})').format(sql.SQL(',').join(
                sql.Identifier(name) for name in ('organization_id', *table.keys))))
            for unique in cls.uniques.get(table.name, ()):
                definitions.append(sql.SQL('UNIQUE ({})').format(sql.SQL(',').join(
                    sql.Identifier(name) for name in unique)))
            for check in cls.checks.get(table.name, ()):
                definitions.append(sql.SQL('CHECK ({})').format(sql.SQL(check)))
            if table.name != 'organizations':
                definitions.append(sql.SQL('FOREIGN KEY (organization_id) '
                    'REFERENCES organizations (id) DEFERRABLE INITIALLY DEFERRED'))
            else:
                definitions.append(sql.SQL('CHECK (organization_id = id)'))
            for column, parent, parent_column in cls.references.get(table.name, ()):
                definitions.append(sql.SQL('FOREIGN KEY (organization_id,{}) '
                    'REFERENCES {} (organization_id,{}) DEFERRABLE INITIALLY DEFERRED').format(
                    sql.Identifier(column), sql.Identifier(parent), sql.Identifier(parent_column)))
            cursor.execute(sql.SQL('CREATE TABLE IF NOT EXISTS {} ({})').format(
                sql.Identifier(table.name), sql.SQL(',').join(definitions)))
        cursor.execute(sql.SQL('''CREATE TABLE IF NOT EXISTS configuration_migration_runs (
            organization_id TEXT PRIMARY KEY REFERENCES organizations(id),
            format_version BIGINT NOT NULL CHECK (format_version={}),
            source_sha256 TEXT NOT NULL, report_json TEXT NOT NULL,
            imported_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP)''').format(
                sql.Literal(cls.format_version)))
        for name in (*[table.name for table in cls.tables], 'configuration_migration_runs'):
            cursor.execute(sql.SQL('ALTER TABLE {} ENABLE ROW LEVEL SECURITY').format(
                sql.Identifier(name)))
            cursor.execute(sql.SQL('ALTER TABLE {} FORCE ROW LEVEL SECURITY').format(
                sql.Identifier(name)))
            cursor.execute('SELECT 1 FROM pg_policies WHERE schemaname=current_schema() '
                "AND tablename=%s AND policyname='configuration_tenant'", (name,))
            if not cursor.fetchone():
                cursor.execute(sql.SQL('CREATE POLICY configuration_tenant ON {} USING '
                    "(organization_id=NULLIF(current_setting('app.current_org_id',true),'')) "
                    "WITH CHECK (organization_id=NULLIF(current_setting('app.current_org_id',true),''))"
                    ).format(sql.Identifier(name)))
        if not existing:
            cursor.execute('CREATE TABLE configuration_schema_version '
                           '(version BIGINT PRIMARY KEY, signature TEXT NOT NULL)')
            cursor.execute('INSERT INTO configuration_schema_version VALUES (%s,%s)',
                           (cls.format_version, signature))

    @classmethod
    def finalize(cls, cursor, org, rows, *, new_import):
        """Profile-specific derived metadata, never source row rewrites."""

    @classmethod
    def report_metadata(cls, rows):
        return {}

    @classmethod
    def read_rows(cls, cursor, org):
        from psycopg2 import sql
        result = {}
        for table in cls.tables:
            cursor.execute(sql.SQL('SELECT {} FROM {} WHERE organization_id=%s').format(
                sql.SQL(',').join(sql.Identifier(name) for name, _ in table.columns),
                sql.Identifier(table.name)), (org,))
            rows = [{key: bytes(value) if isinstance(value, memoryview) else value
                     for key, value in dict(row).items()} for row in cursor.fetchall()]
            result[table.name] = sorted(rows, key=canonical)
        return result

    def apply(self, snapshot, *, expected_sha256):
        """Explicit write operation. A preview hash must be supplied by the caller."""
        from psycopg2 import sql
        # Copy/validate before transaction so mutable payloads cannot drift mid-import.
        import copy
        rows = copy.deepcopy(snapshot.rows)
        org = snapshot.organization_id
        self.validate_rows(org, rows)
        actual = self.snapshot_digest(org, rows)
        if actual != snapshot.sha256 or actual != expected_sha256:
            raise MigrationConflict('Snapshot changed or differs from approved preview.')
        try:
            with self.transaction(org) as cursor:
                self.bootstrap(cursor)
                cursor.execute('SELECT source_sha256 FROM configuration_migration_runs '
                               'WHERE organization_id=%s FOR UPDATE', (org,))
                previous = cursor.fetchone()
                if previous:
                    if previous['source_sha256'] != actual:
                        raise MigrationConflict('Organization already imported from another snapshot.')
                else:
                    for table in self.tables:
                        cursor.execute(sql.SQL('SELECT 1 FROM {} WHERE organization_id=%s LIMIT 1'
                            ).format(sql.Identifier(table.name)), (org,))
                        if cursor.fetchone():
                            raise MigrationConflict('Target organization is not empty.')
                    for table in self.tables:
                        columns = [name for name, _ in table.columns]
                        inject_org = 'organization_id' not in columns
                        target_columns = ['organization_id', *columns] if inject_org else columns
                        statement = sql.SQL('INSERT INTO {} ({}) VALUES ({})').format(
                            sql.Identifier(table.name), sql.SQL(',').join(map(sql.Identifier, target_columns)),
                            sql.SQL(',').join(sql.Placeholder() for _ in target_columns))
                        for row in rows[table.name]:
                            values = [org] if inject_org else []
                            cursor.execute(statement, values + [row[name] for name in columns])
                imported = self.read_rows(cursor, org)
                self.validate_rows(org, imported)
                if self.snapshot_digest(org, imported) != actual:
                    raise MigrationConflict('Target counts or row checksums differ from source.')
                self.finalize(cursor, org, imported, new_import=not previous)
                report = {'format_version': self.format_version, 'scope': self.scope,
                    'organization_id': org, 'sha256': actual,
                    'counts': {name: len(batch) for name, batch in rows.items()},
                    'cutover_ready': False, **self.report_metadata(imported)}
                if not previous:
                    cursor.execute('INSERT INTO configuration_migration_runs '
                        '(organization_id,format_version,source_sha256,report_json) VALUES (%s,%s,%s,%s)',
                        (org, self.format_version, actual, json.dumps(report, sort_keys=True)))
                return report
        except MigrationConflict:
            raise
        except Exception as exc:
            # SQL/provider exceptions can contain rows, password hashes and credentials.
            import psycopg2
            if isinstance(exc, psycopg2.Error):
                raise MigrationConflict('PostgreSQL configuration import failed; transaction rolled back.') from None
            raise
