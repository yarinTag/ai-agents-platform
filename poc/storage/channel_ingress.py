"""SQLite inbox and durable leased outbox for verified channel events."""
import secrets
import time
from uuid import uuid4

from integrations.identity_proofs import InvalidProof
from integrations.channel_ingress import INGRESS_ADAPTERS
from workflows.channel_trigger_rules import sanitize_text
from .external_identities import connector_settings

REPLAY_SECONDS = 2 * 86400
RATE_PER_MINUTE = 120
MAX_PENDING = 1000
MAX_ATTEMPTS = 5
LEASE_SECONDS = 60
TRIGGER_INPUT_SECONDS = 300


def initialize(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS channel_ingress_events (
        id TEXT PRIMARY KEY,
        organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
        connector_id TEXT NOT NULL REFERENCES mcp_connectors(id) ON DELETE CASCADE,
        provider TEXT NOT NULL, account TEXT NOT NULL, event_id TEXT NOT NULL,
        event_type TEXT NOT NULL, channel_id TEXT NOT NULL, message_id TEXT NOT NULL, sender_id TEXT,
        received_at INTEGER NOT NULL,
        UNIQUE(organization_id, connector_id, provider, account, event_id),
        UNIQUE(organization_id, connector_id, provider, account, channel_id, message_id)
    )""")
    conn.execute("""CREATE INDEX IF NOT EXISTS idx_channel_ingress_connector_time
        ON channel_ingress_events(organization_id, connector_id, received_at DESC, id DESC)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS channel_ingress_outbox (
        event_id TEXT PRIMARY KEY REFERENCES channel_ingress_events(id) ON DELETE CASCADE,
        status TEXT NOT NULL CHECK(status IN ('QUEUED','PROCESSING','RETRY','COMPLETED','FAILED')),
        attempts INTEGER NOT NULL DEFAULT 0,
        available_at INTEGER NOT NULL, lease_token TEXT, lease_until INTEGER, finished_at INTEGER
    )""")
    conn.execute("""CREATE INDEX IF NOT EXISTS idx_channel_outbox_work
        ON channel_ingress_outbox(status, available_at, lease_until)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS channel_ingress_trigger_inputs (
        event_id TEXT PRIMARY KEY REFERENCES channel_ingress_events(id) ON DELETE CASCADE,
        text TEXT NOT NULL CHECK(length(text) <= 2048),
        expires_at INTEGER NOT NULL
    )""")
    conn.execute("""CREATE INDEX IF NOT EXISTS idx_channel_trigger_input_expiry
        ON channel_ingress_trigger_inputs(expires_at)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS channel_trigger_dispatches (
        event_id TEXT NOT NULL REFERENCES channel_ingress_events(id) ON DELETE CASCADE,
        workflow_id TEXT NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
        execution_id TEXT NOT NULL UNIQUE REFERENCES workflow_executions(id) ON DELETE CASCADE,
        workflow_revision INTEGER NOT NULL,
        binding_id TEXT NOT NULL,
        principal_id TEXT NOT NULL,
        sender_user_id TEXT NOT NULL,
        PRIMARY KEY(event_id, workflow_id)
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS channel_ingress_limits (
        connector_id TEXT PRIMARY KEY REFERENCES mcp_connectors(id) ON DELETE CASCADE,
        minute INTEGER NOT NULL, count INTEGER NOT NULL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS channel_ingress_failures (
        organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
        connector_id TEXT NOT NULL REFERENCES mcp_connectors(id) ON DELETE CASCADE,
        minute INTEGER NOT NULL, code TEXT NOT NULL, occurred_at INTEGER NOT NULL, count INTEGER NOT NULL,
        PRIMARY KEY(organization_id, connector_id, minute, code)
    )""")


def _stage_trigger_input(conn, identifier, organization_id, connector_id, event, now):
    """Keep text only when an active saved rule is configured on this exact channel."""
    if not event.sender_id or not event.text:
        return
    needs_input = conn.execute("""
        SELECT 1 FROM channel_bindings b
        JOIN workflows w ON w.organization_id=b.organization_id AND w.department_id=b.department_id
        JOIN department_mcp_access g ON g.department_id=b.department_id AND g.connector_id=b.connector_id
        WHERE b.organization_id=? AND b.connector_id=? AND b.channel_id=?
          AND b.trigger_workflows=1 AND w.is_active=1 AND g.is_active=1
          AND (g.organization_id IS NULL OR g.organization_id=b.organization_id)
          AND CASE WHEN json_valid(w.definition_json) THEN
            json_extract(w.definition_json,'$.metadata.channel_trigger.binding_id')=b.id
            AND json_type(w.definition_json,'$.metadata.channel_trigger.enabled')='true'
          ELSE 0 END
        LIMIT 1
    """, (organization_id, connector_id, event.channel_id)).fetchone()
    if needs_input:
        conn.execute("INSERT INTO channel_ingress_trigger_inputs VALUES (?,?,?)",
                     (identifier, sanitize_text(event.text), now + TRIGGER_INPUT_SECONDS))


def stage(db, connector_id, verified_version, event):
    """Commit inbox and outbox together. Duplicate acknowledgement consumes no quota."""
    with db._get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        now = int(time.time())
        org, provider, (_, account, _), current_version = connector_settings(conn, connector_id)
        if current_version != verified_version:
            raise InvalidProof("INVALID_PROOF")
        identity = (connector_id, provider, account)
        exists = conn.execute("""SELECT 1 FROM channel_ingress_events WHERE organization_id=? AND connector_id=? AND provider=? AND account=?
            AND (event_id=? OR (channel_id=? AND message_id=?))""",
            (org, *identity, event.event_id, event.channel_id, event.message_id)).fetchone()
        if exists:
            return False
        minute = now // 60
        counter = conn.execute("SELECT count FROM channel_ingress_limits WHERE connector_id=? AND minute=?",
                               (connector_id, minute)).fetchone()
        if counter and counter[0] >= RATE_PER_MINUTE:
            raise InvalidProof("RATE_LIMITED")
        conn.execute("""DELETE FROM channel_ingress_events WHERE organization_id=? AND connector_id=? AND received_at<?
            AND id IN (SELECT event_id FROM channel_ingress_outbox WHERE status IN ('COMPLETED','FAILED'))""",
            (org, connector_id, now - REPLAY_SECONDS))
        pending = conn.execute("""SELECT count(*) FROM channel_ingress_events e JOIN channel_ingress_outbox o ON o.event_id=e.id
            WHERE e.organization_id=? AND e.connector_id=? AND o.status IN ('QUEUED','PROCESSING','RETRY')""",
            (org, connector_id)).fetchone()[0]
        if pending >= MAX_PENDING:
            raise InvalidProof("QUEUE_FULL")
        identifier = f"ige_{uuid4().hex}"
        conn.execute("""INSERT INTO channel_ingress_events
            (id,organization_id,connector_id,provider,account,event_id,event_type,channel_id,message_id,sender_id,received_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (identifier, org, *identity, event.event_id, event.event_type, event.channel_id, event.message_id, event.sender_id, now))
        conn.execute("INSERT INTO channel_ingress_outbox(event_id,status,available_at) VALUES(?,'QUEUED',?)", (identifier, now))
        conn.execute("DELETE FROM channel_ingress_trigger_inputs WHERE expires_at<=?", (now,))
        _stage_trigger_input(conn, identifier, org, connector_id, event, now)
        conn.execute("""INSERT INTO channel_ingress_limits(connector_id,minute,count) VALUES(?,?,1)
            ON CONFLICT(connector_id) DO UPDATE SET
              count=CASE WHEN minute=excluded.minute THEN count+1 ELSE 1 END, minute=excluded.minute""",
            (connector_id, minute))
        return True


def record_failure(db, connector_id, code):
    """Keep a bounded minute-bucket summary, with no unauthenticated input in the row."""
    with db._get_connection() as conn:
        now = int(time.time())
        minute = now // 60
        row = conn.execute("SELECT organization_id, provider FROM mcp_connectors WHERE id=?",
                           (connector_id,)).fetchone()
        if not row or not row["organization_id"] or row["provider"].lower() not in INGRESS_ADAPTERS:
            return
        org = row["organization_id"]
        conn.execute("DELETE FROM channel_ingress_failures WHERE organization_id=? AND connector_id=? AND minute<?",
                     (org, connector_id, minute - 59))
        conn.execute("""INSERT INTO channel_ingress_failures(organization_id,connector_id,minute,code,occurred_at,count)
            VALUES(?,?,?,?,?,1) ON CONFLICT(organization_id,connector_id,minute,code)
            DO UPDATE SET occurred_at=excluded.occurred_at,count=count+1""", (org, connector_id, minute, code, now))


def diagnostics(db, organization_id, connector_id):
    with db._get_connection() as conn:
        scope = (organization_id, connector_id, int(time.time()) // 60 - 59)
        conn.execute("BEGIN")
        events = [dict(row) for row in conn.execute("""SELECT e.id,e.provider,e.event_type,e.received_at,o.status,
            CASE WHEN o.finished_at IS NOT NULL THEN max(0,o.finished_at-e.received_at)*1000 END AS processing_ms
            FROM channel_ingress_events e JOIN channel_ingress_outbox o ON o.event_id=e.id
            WHERE e.organization_id=? AND e.connector_id=? ORDER BY e.received_at DESC,e.id DESC LIMIT 25""",
            (organization_id, connector_id))]
        failures = [dict(row) for row in conn.execute("""SELECT code,occurred_at FROM channel_ingress_failures
            WHERE organization_id=? AND connector_id=? AND minute>=? ORDER BY occurred_at DESC,code LIMIT 25""", scope)]
        failure_count = conn.execute("""SELECT coalesce(sum(count),0) FROM channel_ingress_failures
            WHERE organization_id=? AND connector_id=? AND minute>=?""", scope).fetchone()[0]
    return {
        "last_verified_at": events[0]["received_at"] if events else None,
        "recent_events": events,
        "recent_failures": failures,
        "dropped_failures": failure_count - len(failures),
    }


def claim(db, now=None):
    """Claim a job for a future trusted consumer. Expired claims can be recovered."""
    now = int(time.time()) if now is None else now
    with db._get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("DELETE FROM channel_ingress_trigger_inputs WHERE expires_at<=?", (now,))
        conn.execute("""UPDATE channel_ingress_outbox SET status='FAILED',finished_at=?,lease_token=NULL,lease_until=NULL
            WHERE status='PROCESSING' AND lease_until<=? AND attempts>=?""", (now, now, MAX_ATTEMPTS))
        row = conn.execute("""SELECT event_id FROM channel_ingress_outbox
            WHERE attempts<? AND ((status IN ('QUEUED','RETRY') AND available_at<=?)
                OR (status='PROCESSING' AND lease_until<=?)) ORDER BY available_at,event_id LIMIT 1""",
            (MAX_ATTEMPTS, now, now)).fetchone()
        if row is None:
            return None
        token = secrets.token_urlsafe(24)
        attempts = conn.execute("""UPDATE channel_ingress_outbox SET status='PROCESSING',attempts=attempts+1,
            lease_token=?,lease_until=? WHERE event_id=? RETURNING attempts""",
            (token, now + LEASE_SECONDS, row["event_id"])).fetchone()[0]
        event = conn.execute("SELECT * FROM channel_ingress_events WHERE id=?", (row["event_id"],)).fetchone()
        trigger_input = conn.execute("SELECT text FROM channel_ingress_trigger_inputs WHERE event_id=?",
                                     (event["id"],)).fetchone()
        return {"event": dict(event), "lease_token": token, "attempt": attempts,
                "trigger_text": trigger_input["text"] if trigger_input else None}


def settle(db, event_id, lease_token, *, success, retryable=False, now=None):
    now = int(time.time()) if now is None else now
    with db._get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("""SELECT attempts FROM channel_ingress_outbox WHERE event_id=? AND status='PROCESSING'
            AND lease_token=? AND lease_until>?""", (event_id, lease_token, now)).fetchone()
        if row is None:
            return False
        retry = not success and retryable and row["attempts"] < MAX_ATTEMPTS
        status = "COMPLETED" if success else "RETRY" if retry else "FAILED"
        available = now + 2**row["attempts"] * 5 if retry else now
        conn.execute("""UPDATE channel_ingress_outbox SET status=?,available_at=?,finished_at=?,
            lease_token=NULL,lease_until=NULL WHERE event_id=?""", (status, available, None if retry else now, event_id))
        if not retry:
            conn.execute("DELETE FROM channel_ingress_trigger_inputs WHERE event_id=?", (event_id,))
        return True
