"""Read-only, single-snapshot configuration extraction with no facade imports.

Snapshot payloads contain credentials/content. Only report() is safe to display.
This subset is not a complete platform backup or a cutover authorization.
"""
import base64
import hashlib
import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from governance.models import PolicyDocument
from .configuration_migration_spec import REFERENCES, REQUIRED, TABLES, UNIQUES, WORKFLOW_FIELDS


class MigrationConflict(ValueError):
    pass


def canonical(value):
    def encode(item):
        if isinstance(item, bytes):
            return {'sqlite_blob_base64': base64.b64encode(item).decode('ascii')}
        raise TypeError('Unsupported snapshot value.')
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                      allow_nan=False, default=encode)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


@dataclass(frozen=True)
class ConfigurationSnapshot:
    organization_id: str
    rows: dict = field(repr=False)
    sha256: str

    def report(self):
        return {'format_version': 1, 'scope': 'configuration_only',
                'organization_id': self.organization_id, 'sha256': self.sha256,
                'tables': {name: {'count': len(rows), 'sha256': digest(rows)}
                           for name, rows in self.rows.items()},
                'cutover_ready': False}


def validate_inventory(org, rows, tables=TABLES, references=REFERENCES,
                       required=REQUIRED, uniques=UNIQUES):
    if not isinstance(org, str) or not org or org != org.strip():
        raise MigrationConflict('Exact organization identity required.')
    if set(rows) != {table.name for table in tables}:
        raise MigrationConflict('Snapshot table inventory differs from its migration profile.')
    indexes = {}
    for table in tables:
        expected = {key for key, _ in table.columns}
        seen = set()
        for row in rows[table.name]:
            if set(row) != expected:
                raise MigrationConflict(f'Unsupported columns in {table.name}.')
            if any(row[name] is None for name in required[table.name].split()):
                raise MigrationConflict(f'Missing required value in {table.name}.')
            for name, kind in table.columns:
                value = row[name]
                allowed = {'TEXT': (str,), 'BIGINT': (int,),
                           'DOUBLE PRECISION': (float, int), 'BYTEA': (bytes,)}[kind]
                if value is not None and type(value) not in allowed:
                    raise MigrationConflict(f'Unsupported value type in {table.name}.{name}.')
            if 'organization_id' in expected and row['organization_id'] != org:
                raise MigrationConflict(f'Tenant ownership conflict in {table.name}.')
            key = tuple(row[column] for column in table.keys)
            if any(value is None for value in key) or key in seen:
                raise MigrationConflict(f'Invalid or duplicate key in {table.name}.')
            seen.add(key)
        for unique in uniques.get(table.name, ()):
            values = [tuple(row[column] for column in unique) for row in rows[table.name]
                      if all(row[column] is not None for column in unique)]
            if len(values) != len(set(values)):
                raise MigrationConflict(f'Uniqueness conflict in {table.name}.')
        indexes[table.name] = {row['id'] for row in rows[table.name] if 'id' in row}
    if len(rows['organizations']) != 1 or indexes['organizations'] != {org}:
        raise MigrationConflict('Exact source organization required.')
    reference_indexes = {(parent, column): {record[column] for record in rows[parent]}
                         for relationships in references.values()
                         for _, parent, column in relationships}
    for name, relationships in references.items():
        for row in rows[name]:
            for column, parent, parent_column in relationships:
                parent_values = reference_indexes[parent, parent_column]
                if row[column] is not None and row[column] not in parent_values:
                    raise MigrationConflict(f'Missing or foreign reference in {name}.{column}.')
    return indexes


def validate_rows(org, rows):
    indexes = validate_inventory(org, rows)
    policies = {(r['scope_type'], r['scope_id'], r['revision']): r
                for r in rows['capability_policy_revisions']}
    for name in ('capability_policies', 'capability_policy_revisions'):
        for row in rows[name]:
            if (row['scope_type'] == 'organization' and row['scope_id'] != org or
                row['scope_type'] == 'department' and row['scope_id'] not in indexes['departments'] or
                row['scope_type'] not in {'organization', 'department'} or
                type(row['revision']) is not int or row['revision'] < 1):
                raise MigrationConflict('Invalid capability policy scope or revision.')
            try:
                PolicyDocument.model_validate_json(row['document_json'])
            except ValueError:
                raise MigrationConflict('Invalid capability policy document.') from None
            if name == 'capability_policies' and policies.get(
                    (row['scope_type'], row['scope_id'], row['revision'])) != row:
                raise MigrationConflict('Current policy does not match its immutable revision.')
            if name == 'capability_policies' and max(
                    revision for scope, key, revision in policies
                    if scope == row['scope_type'] and key == row['scope_id']) != row['revision']:
                raise MigrationConflict('Policy head is behind its immutable history.')
    revisions = {(r['workflow_id'], r['revision']): r for r in rows['workflow_revisions']}
    for revision in rows['workflow_revisions']:
        try:
            snapshot = json.loads(revision['snapshot_json'])
            changes = json.loads(revision['changed_fields_json'])
            if (not isinstance(snapshot, dict) or not isinstance(changes, list) or
                    set(WORKFLOW_FIELDS) - set(snapshot) or
                    snapshot.get('organization_id') not in {None, org} or
                    revision['revision'] < 1):
                raise ValueError()
        except (ValueError, TypeError):
            raise MigrationConflict('Invalid workflow revision snapshot.') from None
    for row in rows['workflows']:
        if type(row['revision']) is not int or row['revision'] < 1 or (
                row['id'], row['revision']) not in revisions:
            raise MigrationConflict('Workflow current revision is missing.')
        try:
            if not isinstance(json.loads(row['definition_json']), dict):
                raise ValueError()
            current = json.loads(revisions[(row['id'], row['revision'])]['snapshot_json'])
            if any(current[key] != row[key] for key in WORKFLOW_FIELDS) or max(
                    r['revision'] for r in rows['workflow_revisions']
                    if r['workflow_id'] == row['id']) != row['revision']:
                raise ValueError()
        except (ValueError, TypeError):
            raise MigrationConflict('Workflow definition or current history is inconsistent.') from None
    # Canonicalization rejects unsupported scalars and non-finite numbers.
    canonical(rows)


def snapshot_digest(org, rows):
    return digest({'format_version': 1, 'organization_id': org, 'rows': rows})


def extract_rows(source_path, organization_id, *, tables=TABLES, max_rows=100000,
                 source_validator=None):
    if not isinstance(organization_id, str) or not organization_id.strip():
        raise MigrationConflict('Explicit organization required.')
    if type(max_rows) is not int or max_rows < 1:
        raise MigrationConflict('Positive row bound required.')
    path = Path(source_path).resolve(strict=True)
    connection = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute('PRAGMA query_only=ON')
        connection.execute('BEGIN')
        rows, total = {}, 0
        for table in tables:
            # Identifiers and SELECT statements are fixed application inventory.
            columns = {r['name'] for r in connection.execute(
                f'PRAGMA table_info({table.name})')}
            if columns != {name for name, _ in table.columns}:
                raise MigrationConflict(f'Source schema drift in {table.name}.')
            cursor = connection.execute(table.query,
                (organization_id,) * table.query.count('?'))
            batch = cursor.fetchmany(max_rows - total + 1)
            total += len(batch)
            if total > max_rows:
                raise MigrationConflict('Snapshot exceeds configured row limit.')
            rows[table.name] = sorted((dict(row) for row in batch), key=canonical)
        if source_validator:
            source_validator(connection, organization_id, rows)
        return rows
    except sqlite3.Error:
        raise MigrationConflict('Source SQLite snapshot could not be read.') from None
    finally:
        connection.rollback()
        connection.close()


def extract_configuration(source_path, organization_id, *, max_rows=100000):
    rows = extract_rows(source_path, organization_id, max_rows=max_rows)
    validate_rows(organization_id, rows)
    return ConfigurationSnapshot(organization_id, rows, snapshot_digest(organization_id, rows))
