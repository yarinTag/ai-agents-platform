"""Additive versioned policy schema. No grants, backfills or legacy record changes."""


def initialize(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS capability_policies (
        organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
        scope_type TEXT NOT NULL CHECK(scope_type IN ('organization','department')),
        scope_id TEXT NOT NULL, revision INTEGER NOT NULL CHECK(revision>0),
        document_json TEXT NOT NULL, updated_by TEXT NOT NULL, updated_at TEXT NOT NULL,
        PRIMARY KEY(organization_id,scope_type,scope_id)
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS capability_policy_revisions (
        organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
        scope_type TEXT NOT NULL CHECK(scope_type IN ('organization','department')),
        scope_id TEXT NOT NULL, revision INTEGER NOT NULL CHECK(revision>0),
        document_json TEXT NOT NULL, updated_by TEXT NOT NULL, updated_at TEXT NOT NULL,
        PRIMARY KEY(organization_id,scope_type,scope_id,revision)
    )''')
