"""SQLite registry for exact channel identities and independent configured uses."""
from datetime import datetime, timezone
import json
from uuid import uuid4
from integrations.channel_providers import CHANNEL_PROVIDERS


USES = ("send_notifications", "trigger_workflows", "approve_decisions")


class BindingConflict(ValueError):
    pass


def initialize(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS channel_bindings (
            id TEXT PRIMARY KEY,
            organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            department_id TEXT REFERENCES departments(id) ON DELETE CASCADE,
            connector_id TEXT NOT NULL REFERENCES mcp_connectors(id) ON DELETE CASCADE,
            provider TEXT NOT NULL,
            channel_id TEXT NOT NULL,
            send_notifications INTEGER NOT NULL CHECK (send_notifications IN (0, 1)),
            trigger_workflows INTEGER NOT NULL CHECK (trigger_workflows IN (0, 1)),
            approve_decisions INTEGER NOT NULL CHECK (approve_decisions IN (0, 1)),
            revision INTEGER NOT NULL CHECK (revision > 0),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_channel_binding_identity
            ON channel_bindings(organization_id, COALESCE(department_id, ''), connector_id, channel_id)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_channel_binding_scope
            ON channel_bindings(organization_id, department_id, id)
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_channel_binding_connector ON channel_bindings(connector_id)")


def _record(row):
    result = dict(row)
    result["uses"] = {key: bool(result.pop(key)) for key in USES}
    return result


def list_bindings(db, organization_id, department_id, after, limit):
    with db._get_connection() as conn:
        return [_record(row) for row in conn.execute("""
            SELECT * FROM channel_bindings
            WHERE organization_id = ? AND department_id IS ? AND id > ?
            ORDER BY id LIMIT ?
        """, (organization_id, department_id, after, limit))]


def _require_admin(conn, organization_id, actor_id):
    user = conn.execute("""
        SELECT 1 FROM users WHERE id = ? AND organization_id = ?
        AND status = 'ACTIVE' AND role = 'ORG_ADMIN'
    """, (actor_id, organization_id)).fetchone()
    if user is None:
        raise PermissionError("A signed-in organization administrator is required.")


def _audit(conn, action, actor_id, record, timestamp):
    details = {key: record[key] for key in (
        "organization_id", "department_id", "connector_id", "provider", "channel_id", "revision", "uses",
    )}
    conn.execute("""
        INSERT INTO audit_logs (id, action, actor, entity_type, entity_id, details, timestamp)
        VALUES (?, ?, ?, 'channel_binding', ?, ?, ?)
    """, (f"audit_{uuid4().hex}", action, actor_id, record["id"], json.dumps(details), timestamp))


def create(db, organization_id, department_id, actor_id, connector_id, provider, channel_id, uses):
    with db._get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        _require_admin(conn, organization_id, actor_id)
        if department_id is not None and conn.execute(
            "SELECT 1 FROM departments WHERE id = ? AND organization_id = ?", (department_id, organization_id),
        ).fetchone() is None:
            raise LookupError("Department not found in the authorized scope.")
        connector = conn.execute(
            "SELECT provider, configuration FROM mcp_connectors WHERE id = ? AND organization_id = ?",
            (connector_id, organization_id),
        ).fetchone()
        if connector is None:
            raise LookupError("Connector not found in the authorized scope.")
        if connector["provider"].lower() != provider:
            raise ValueError("Channel provider must match the connector.")
        adapter = CHANNEL_PROVIDERS.get(provider)
        if adapter is None or not adapter.valid_id(channel_id):
            raise ValueError("Unsupported provider or invalid channel identity.")
        if channel_id not in adapter.configured_ids(json.loads(connector["configuration"] or "{}")):
            raise ValueError("Select a channel configured on this connector.")
        duplicate = conn.execute("""
            SELECT 1 FROM channel_bindings WHERE organization_id = ? AND department_id IS ?
            AND connector_id = ? AND channel_id = ?
        """, (organization_id, department_id, connector_id, channel_id)).fetchone()
        if duplicate:
            raise BindingConflict("This exact channel is already registered in the selected scope.")
        binding_id = f"chb_{uuid4().hex}"
        now = datetime.now(timezone.utc).isoformat()
        row = conn.execute("""
            INSERT INTO channel_bindings (
                id, organization_id, department_id, connector_id, provider, channel_id,
                send_notifications, trigger_workflows, approve_decisions, revision, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?) RETURNING *
        """, (binding_id, organization_id, department_id, connector_id, provider, channel_id,
              *(uses[key] for key in USES), now, now)).fetchone()
        record = _record(row)
        _audit(conn, "CHANNEL_BINDING_CREATED", actor_id, record, now)
        return record


def change(db, organization_id, department_id, actor_id, binding_id, expected_revision, uses=None):
    """Replace the use flags or remove the exact scoped binding when uses is absent."""
    with db._get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        _require_admin(conn, organization_id, actor_id)
        row = conn.execute("""
            SELECT * FROM channel_bindings WHERE id = ? AND organization_id = ? AND department_id IS ?
        """, (binding_id, organization_id, department_id)).fetchone()
        if row is None:
            raise LookupError("Channel binding not found in the authorized scope.")
        record = _record(row)
        if record["revision"] != expected_revision:
            raise BindingConflict("Channel binding changed. Reload its current revision.")
        now = datetime.now(timezone.utc).isoformat()
        if uses is None:
            conn.execute("DELETE FROM channel_bindings WHERE id = ?", (binding_id,))
            _audit(conn, "CHANNEL_BINDING_REMOVED", actor_id, record, now)
            return None
        if uses == record["uses"]:
            return record
        updated = conn.execute("""
            UPDATE channel_bindings SET send_notifications = ?, trigger_workflows = ?, approve_decisions = ?,
                revision = revision + 1, updated_at = ? WHERE id = ? RETURNING *
        """, (*(uses[key] for key in USES), now, binding_id)).fetchone()
        result = _record(updated)
        _audit(conn, "CHANNEL_BINDING_UPDATED", actor_id, result, now)
        return result
