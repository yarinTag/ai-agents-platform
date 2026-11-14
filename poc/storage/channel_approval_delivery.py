"""Durable channel delivery and callback receipts for DAG decisions."""
from datetime import datetime
import hashlib
import hmac
import json
import time

from . import dag_approvals
from .external_identities import connector_settings, resolve_user
from integrations.channel_providers import CHANNEL_PROVIDERS
from integrations.identity_proofs import InvalidProof
from integrations.telegram_approval_cards import action_token


def initialize(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS dag_channel_deliveries (
        approval_id TEXT PRIMARY KEY REFERENCES workflow_dag_approvals(id) ON DELETE CASCADE,
        binding_id TEXT NOT NULL, token_digest TEXT UNIQUE, connector_id TEXT, channel_id TEXT,
        message_id TEXT, bot_id TEXT, status TEXT NOT NULL, rendered TEXT,
        retry_at INTEGER NOT NULL DEFAULT 0
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS dag_channel_callbacks (
        approval_id TEXT NOT NULL REFERENCES dag_channel_deliveries(approval_id) ON DELETE CASCADE,
        callback_id TEXT NOT NULL, user_id TEXT NOT NULL, action TEXT NOT NULL,
        created_at INTEGER NOT NULL, PRIMARY KEY(approval_id,callback_id)
    )""")


def _table(approval_id):
    return 'pr_channel_deliveries' if approval_id.startswith('wfa_') else 'dag_channel_deliveries'


def enqueue(conn, approval_id, binding_id):
    table = _table(approval_id)
    conn.execute(f"INSERT INTO {table}(approval_id,binding_id,status) VALUES (?,?,'QUEUED')",
                 (approval_id, binding_id))


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def destination(conn, row):
    binding = conn.execute("""SELECT b.*,c.configuration FROM channel_bindings b
        JOIN mcp_connectors c ON c.id=b.connector_id AND c.organization_id=b.organization_id
        JOIN department_mcp_access g ON g.department_id=b.department_id AND g.connector_id=c.id
        WHERE b.id=? AND b.organization_id=? AND b.department_id=? AND b.provider='telegram'
        AND b.approve_decisions=1 AND b.send_notifications=1 AND c.status='CONNECTED'
        AND lower(c.provider)=b.provider AND g.is_active=1
        AND (g.organization_id IS NULL OR g.organization_id=b.organization_id)""",
        (row["binding_id"], row["organization_id"], row["department_id"])).fetchone()
    if not binding:
        raise InvalidProof("APPROVAL_DESTINATION_UNAVAILABLE")
    config = json.loads(binding["configuration"] or "{}")
    if binding["channel_id"] not in CHANNEL_PROVIDERS["telegram"].configured_ids(config):
        raise InvalidProof("APPROVAL_DESTINATION_UNAVAILABLE")
    _, _, (_, account, _), version = connector_settings(conn, binding["connector_id"], row["organization_id"])
    return binding, config, account, version


def next_delivery(db):
    with dag_approvals._transaction(db) as conn:
        for table, approvals, clock in (
            ('pr_channel_deliveries', 'workflow_approvals', datetime.now().isoformat()),
            ('dag_channel_deliveries', 'workflow_dag_approvals', int(time.time())),
        ):
            step_key = ",s.step_key" if table == 'pr_channel_deliveries' else ""
            step_join = "JOIN workflow_step_runs s ON s.id=a.step_run_id AND s.execution_id=a.execution_id" if step_key else ""
            row = conn.execute(f"""SELECT a.*,d.binding_id,x.workflow_id{step_key} FROM {table} d
                JOIN {approvals} a ON a.id=d.approval_id
                {step_join}
                JOIN workflow_executions x ON x.id=a.execution_id AND x.status='WAITING_APPROVAL'
                JOIN workflows w ON w.id=x.workflow_id AND w.revision=a.workflow_revision
                    AND w.organization_id=a.organization_id AND w.department_id=a.department_id
                WHERE d.status='QUEUED' AND a.status='PENDING' AND a.expires_at>?
                ORDER BY a.expires_at,a.id LIMIT 1""", (clock,)).fetchone()
            if row:
                conn.execute(f"UPDATE {table} SET status='SENDING' WHERE approval_id=?", (row["id"],))
                return dict(row)
        return None


def record_delivery(db, approval_id, status, *, connector=None, channel=None, message=None, bot=None, rendered=None, token=None):
    with dag_approvals._transaction(db) as conn:
        conn.execute(f"""UPDATE {_table(approval_id)} SET status=?,connector_id=?,channel_id=?,
            message_id=?,bot_id=?,rendered=?,token_digest=? WHERE approval_id=? AND status='SENDING'""",
            (status, connector, channel, message, bot, rendered, digest(token) if token else None, approval_id))


def apply_callback(db, connector, version, callback):
    with dag_approvals._transaction(db) as conn:
        row = conn.execute("""SELECT a.*,d.binding_id,d.connector_id,d.channel_id,d.message_id,d.bot_id
            FROM dag_channel_deliveries d JOIN workflow_dag_approvals a ON a.id=d.approval_id
            WHERE d.token_digest=? AND d.status='DELIVERED'""", (digest(callback.token),)).fetchone()
        terminal = row is None
        if terminal:
            row = conn.execute("""SELECT a.*,d.binding_id,d.connector_id,d.channel_id,d.message_id,d.bot_id,d.callback_id
                FROM pr_channel_deliveries d JOIN workflow_approvals a ON a.id=d.approval_id
                WHERE d.token_digest=? AND d.status='DELIVERED'""", (digest(callback.token),)).fetchone()
        if not row or (row["connector_id"], row["channel_id"], row["message_id"], row["bot_id"]) != (
            connector, callback.channel_id, callback.message_id, callback.bot_id,
        ):
            raise InvalidProof("INVALID_APPROVAL_CALLBACK")
        binding, config, account, current_version = destination(conn, row)
        if (binding["connector_id"], binding["channel_id"], account, current_version) != (
            connector, callback.channel_id, callback.bot_id, version,
        ):
            raise InvalidProof("INVALID_APPROVAL_CALLBACK")
        if not hmac.compare_digest(callback.token, action_token(config["bot_token"], row["id"])):
            raise InvalidProof("INVALID_APPROVAL_CALLBACK")
        user = resolve_user(db, row["organization_id"], connector, callback.sender_id, connection=conn)
        if not user:
            raise InvalidProof("INVALID_APPROVAL_CALLBACK")
        if terminal:
            if row["callback_id"] == callback.callback_id and row["resolved_by"] == user:
                return
            from .terminal_channel_approval import claim
            claim(conn, row, user, callback)
            return
        if conn.execute("SELECT 1 FROM dag_channel_callbacks WHERE approval_id=? AND callback_id=?",
                        (row["id"], callback.callback_id)).fetchone():
            return
        dag_approvals.decide_on_connection(conn, row["organization_id"], row["department_id"],
                                          row["id"], user, callback.approve)
        conn.execute("INSERT INTO dag_channel_callbacks VALUES (?,?,?,?,?)",
                     (row["id"], callback.callback_id, user, "approve" if callback.approve else "reject", int(time.time())))


def message_state(conn, row):
    if "config_json" in row.keys():
        return {"PENDING": "PENDING:0/1", "RESOLVING": "DECIDED", "EXPIRED": "TIMED_OUT"}.get(row["status"], row["status"])
    if row["status"] != "PENDING":
        return "APPROVED" if row["status"] == "CLAIMED" else row["status"]
    policy = json.loads(row["policy_json"])
    votes = conn.execute("SELECT user_id FROM workflow_dag_approval_votes WHERE approval_id=? AND decision=1",
                         (row["id"],)).fetchall()
    count = sum(dag_approvals._eligible(conn, row, policy, vote["user_id"]) for vote in votes)
    return f"PENDING:{count}/{policy['quorum']}"


def next_edit(db):
    with dag_approvals._transaction(db) as conn:
        rows = conn.execute("""SELECT a.*, d.binding_id,d.connector_id,d.channel_id,d.message_id,
                d.bot_id,d.token_digest,d.rendered,x.workflow_id
            FROM dag_channel_deliveries d JOIN workflow_dag_approvals a ON a.id=d.approval_id
            JOIN workflow_executions x ON x.id=a.execution_id
            WHERE d.status='DELIVERED' AND d.retry_at<=?
                AND (d.rendered LIKE 'PENDING:%' OR (d.rendered='APPROVED' AND a.status IN ('REJECTED','TIMED_OUT')))
            ORDER BY d.retry_at,a.expires_at LIMIT 50""", (int(time.time()),)).fetchall()
        rows += conn.execute("""SELECT a.*,d.binding_id,d.connector_id,d.channel_id,d.message_id,
                d.bot_id,d.token_digest,d.rendered,x.workflow_id,s.step_key
            FROM pr_channel_deliveries d JOIN workflow_approvals a ON a.id=d.approval_id
            JOIN workflow_step_runs s ON s.id=a.step_run_id AND s.execution_id=a.execution_id
            JOIN workflow_executions x ON x.id=a.execution_id
            WHERE d.status='DELIVERED' AND d.retry_at<=?
                AND (d.rendered LIKE 'PENDING:%' OR d.rendered='DECIDED')
            ORDER BY d.retry_at,a.expires_at LIMIT 50""", (int(time.time()),)).fetchall()
        for row in rows:
            conn.execute(f"UPDATE {_table(row['id'])} SET retry_at=? WHERE approval_id=?",
                         (int(time.time()) + 30, row["id"]))
            state = message_state(conn, row)
            if state != row["rendered"]:
                return dict(row), state
        return None


def record_edit(db, approval_id, state):
    with dag_approvals._transaction(db) as conn:
        conn.execute(f"UPDATE {_table(approval_id)} SET rendered=? WHERE approval_id=?", (state, approval_id))
