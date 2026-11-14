"""Policy persistence and execution ceilings; accepts the existing database boundary."""
import json
from datetime import datetime, timezone
from .models import PolicyDocument


class RevisionConflict(ValueError):
    pass


def load(db, organization_id, scope_type, scope_id):
    with db._get_connection() as conn:
        row = conn.execute('SELECT * FROM capability_policies WHERE organization_id=? AND scope_type=? AND scope_id=?',
                           (organization_id, scope_type, scope_id)).fetchone()
    if row:
        result = dict(row)
        result['document'] = PolicyDocument.model_validate_json(result.pop('document_json')).model_dump()
        return result
    return {'organization_id': organization_id, 'scope_type': scope_type, 'scope_id': scope_id,
            'revision': 0, 'document': PolicyDocument().model_dump(), 'updated_by': None, 'updated_at': None}


def history(db, organization_id, scope_type, scope_id):
    with db._get_connection() as conn:
        rows = conn.execute('SELECT * FROM capability_policy_revisions WHERE organization_id=? AND scope_type=? AND scope_id=? ORDER BY revision DESC LIMIT 100',
                            (organization_id, scope_type, scope_id)).fetchall()
    return [{**dict(row), 'document_json': None,
             'document': PolicyDocument.model_validate_json(row['document_json']).model_dump()} for row in rows]


def save(db, organization_id, scope_type, scope_id, document, expected_revision, actor_id, validator=None):
    canonical = document.model_dump_json()
    now = datetime.now(timezone.utc).isoformat()
    with db._get_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute('SELECT revision,document_json FROM capability_policies WHERE organization_id=? AND scope_type=? AND scope_id=?',
                           (organization_id, scope_type, scope_id)).fetchone()
        current = row['revision'] if row else 0
        if expected_revision != current:
            raise RevisionConflict('Policy changed; reload its current revision before saving.')
        if validator:
            validator({'document': json.loads(row['document_json']) if row else PolicyDocument().model_dump()})
        if row and json.loads(row['document_json']) == document.model_dump():
            return current
        revision = current + 1
        values = (organization_id, scope_type, scope_id, revision, canonical, actor_id, now)
        conn.execute('''INSERT INTO capability_policies VALUES (?,?,?,?,?,?,?)
            ON CONFLICT(organization_id,scope_type,scope_id) DO UPDATE SET revision=excluded.revision,
            document_json=excluded.document_json,updated_by=excluded.updated_by,updated_at=excluded.updated_at''', values)
        conn.execute('INSERT INTO capability_policy_revisions VALUES (?,?,?,?,?,?,?)', values)
    return revision


def capture(db, organization_id, department_id):
    records = []
    with db._get_connection() as conn:
        conn.execute('BEGIN')
        for scope_type, scope_id in (('organization', organization_id), ('department', department_id)):
            row = conn.execute('SELECT * FROM capability_policies WHERE organization_id=? AND scope_type=? AND scope_id=?',
                               (organization_id, scope_type, scope_id)).fetchone()
            value = dict(row) if row else {'organization_id': organization_id, 'scope_type': scope_type,
                'scope_id': scope_id, 'revision': 0, 'updated_by': None, 'updated_at': None}
            value['document'] = json.loads(value.pop('document_json')) if row else PolicyDocument().model_dump()
            PolicyDocument.model_validate(value['document'])
            records.append(value)
    return {'organization_id': organization_id, 'department_id': department_id,
            'captured_at': datetime.now(timezone.utc).isoformat(), 'policies': records}
