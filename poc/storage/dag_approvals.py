"""Durable checkpoints and fenced decisions for dashboard DAG approvals."""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import time
from uuid import uuid4


def initialize(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS workflow_dag_approvals (
        id TEXT PRIMARY KEY,
        execution_id TEXT NOT NULL REFERENCES workflow_executions(id) ON DELETE CASCADE,
        step_key TEXT NOT NULL, workflow_revision INTEGER NOT NULL,
        organization_id TEXT NOT NULL, department_id TEXT NOT NULL,
        initiator_id TEXT NOT NULL, policy_json TEXT NOT NULL, checkpoint_json TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('PENDING','APPROVED','REJECTED','TIMED_OUT','CLAIMED')),
        expires_at INTEGER NOT NULL, decided_at INTEGER, decided_by TEXT,
        UNIQUE(execution_id, step_key)
    )""")
    conn.execute("""CREATE INDEX IF NOT EXISTS idx_dag_approval_state
        ON workflow_dag_approvals(status, expires_at, organization_id, department_id)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS workflow_dag_approval_votes (
        approval_id TEXT NOT NULL REFERENCES workflow_dag_approvals(id) ON DELETE CASCADE,
        user_id TEXT NOT NULL, decision INTEGER NOT NULL CHECK(decision IN (0,1)),
        created_at INTEGER NOT NULL, PRIMARY KEY(approval_id,user_id)
    )""")


class ApprovalConflict(ValueError):
    pass


@contextmanager
def _transaction(db):
    with db._get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        yield conn


def suspend(db, *, execution_id, step_key, revision, initiator_id, policy, checkpoint):
    """Publish the wait and its complete predecessor checkpoint in one commit."""
    identifier = f"dga_{uuid4().hex}"
    with _transaction(db) as conn:
        owner = conn.execute("""SELECT w.organization_id,w.department_id
            FROM workflow_executions x JOIN workflows w ON w.id=x.workflow_id
            WHERE x.id=? AND x.status='RUNNING' AND w.revision=?
            AND x.department_id=w.department_id AND w.organization_id IS NOT NULL""",
            (execution_id, revision)).fetchone()
        if owner is None:
            raise ApprovalConflict("Execution or workflow revision changed before suspension.")
        conn.execute("""INSERT INTO workflow_dag_approvals
            (id,execution_id,step_key,workflow_revision,organization_id,department_id,
             initiator_id,policy_json,checkpoint_json,status,expires_at)
            VALUES (?,?,?,?,?,?,?,?,?,'PENDING',?)""",
            (identifier, execution_id, step_key, revision, owner["organization_id"], owner["department_id"],
             initiator_id, json.dumps(policy), json.dumps(checkpoint, ensure_ascii=False),
             int(time.time()) + policy["timeout_seconds"]))
        conn.execute("""INSERT INTO workflow_step_runs(id,execution_id,step_key,status,started_at)
            VALUES (?,?,?,'WAITING_APPROVAL',?)""",
            (identifier, execution_id, step_key, datetime.now(timezone.utc).isoformat()))
        conn.execute("""UPDATE workflow_executions SET status='WAITING_APPROVAL',
            total_input_tokens=?,total_output_tokens=?,total_cost_usd=? WHERE id=?""",
            (checkpoint["input_tokens"], checkpoint["output_tokens"], checkpoint["cost_usd"], execution_id))
    return identifier


def _role(conn, row, user_id):
    account = conn.execute("""SELECT u.role, m.role AS membership FROM users u
        LEFT JOIN department_members m ON m.user_id=u.id AND m.department_id=?
        WHERE u.id=? AND u.organization_id=? AND u.status='ACTIVE'""",
        (row["department_id"], user_id, row["organization_id"])).fetchone()
    if account is None:
        return None
    if account["role"] == "ORG_ADMIN":
        return "ORG_ADMIN"
    roles = ("MEMBER", "OPERATOR", "MANAGER", "ORG_ADMIN")
    if account["role"] not in roles or account["membership"] not in roles:
        return None
    return roles[min(roles.index(account["role"]), roles.index(account["membership"]))]


def _eligible(conn, row, policy, user_id):
    if _role(conn, row, user_id) not in policy["approver_roles"] or user_id == row["initiator_id"]:
        return False
    authored = conn.execute("""SELECT 1 FROM workflow_revisions r
        JOIN workflow_executions x ON x.workflow_id=r.workflow_id
        WHERE x.id=? AND r.revision=? AND r.actor_id=?""",
        (row["execution_id"], row["workflow_revision"], user_id)).fetchone()
    return authored is None


def _finish(conn, row, status, now, actor=None):
    conn.execute("""UPDATE workflow_dag_approvals SET status=?,decided_by=?,decided_at=?
        WHERE id=? AND status IN ('PENDING','APPROVED')""", (status, actor, now, row["id"]))
    if status != "APPROVED":
        conn.execute("""UPDATE workflow_step_runs SET status='FAILED',completed_at=CURRENT_TIMESTAMP
            WHERE id=? AND status='WAITING_APPROVAL'""", (row["id"],))
        conn.execute("""UPDATE workflow_executions SET status='FAILED', completed_at=?, error_message=?
            WHERE id=? AND status='WAITING_APPROVAL'""",
            (datetime.now(timezone.utc).isoformat(), f"DAG approval {status.lower()}.", row["execution_id"]))


def decide(db, organization_id, department_id, identifier, user_id, approve):
    """Record one personal vote and recheck every counted approval against current roles."""
    with _transaction(db) as conn:
        now = int(time.time())
        row = conn.execute("""SELECT a.* FROM workflow_dag_approvals a
            JOIN workflow_executions x ON x.id=a.execution_id AND x.status='WAITING_APPROVAL'
            JOIN workflows w ON w.id=x.workflow_id AND w.revision=a.workflow_revision
                AND w.organization_id=a.organization_id AND w.department_id=a.department_id
            WHERE a.id=? AND a.organization_id=? AND a.department_id=? AND a.status='PENDING'""",
            (identifier, organization_id, department_id)).fetchone()
        if row is None:
            raise ApprovalConflict("Approval is unavailable or no longer pending.")
        policy = json.loads(row["policy_json"])
        if not _eligible(conn, row, policy, user_id):
            raise PermissionError("Current user is not eligible to decide this approval.")
        if row["expires_at"] <= now:
            _finish(conn, row, "TIMED_OUT", now)
            return "TIMED_OUT"
        result = conn.execute("""INSERT INTO workflow_dag_approval_votes
            (approval_id,user_id,decision,created_at) VALUES (?,?,?,?)
            ON CONFLICT(approval_id,user_id) DO NOTHING""", (identifier, user_id, int(approve), now))
        if not result.rowcount:
            raise ApprovalConflict("This user already voted.")
        if not approve:
            _finish(conn, row, "REJECTED", now, user_id)
            return "REJECTED"
        votes = conn.execute("SELECT user_id FROM workflow_dag_approval_votes WHERE approval_id=? AND decision=1",
                             (identifier,)).fetchall()
        if sum(_eligible(conn, row, policy, vote["user_id"]) for vote in votes) >= policy["quorum"]:
            _finish(conn, row, "APPROVED", now, user_id)
            return "APPROVED"
        return "PENDING"


def claim_resume(db, identifier, workflow_id, revision):
    """Claim an approved barrier once and release only the saved continuation."""
    with _transaction(db) as conn:
        row = conn.execute("""SELECT a.* FROM workflow_dag_approvals a
            JOIN workflow_executions x ON x.id=a.execution_id AND x.status='WAITING_APPROVAL'
            JOIN workflows w ON w.id=x.workflow_id AND w.revision=a.workflow_revision
                AND w.organization_id=a.organization_id AND w.department_id=a.department_id
            WHERE a.id=? AND w.id=? AND w.revision=? AND a.status='APPROVED' AND a.expires_at>?""",
            (identifier, workflow_id, revision, int(time.time()))).fetchone()
        if row is None:
            return None
        policy = json.loads(row["policy_json"])
        votes = conn.execute("SELECT user_id FROM workflow_dag_approval_votes WHERE approval_id=? AND decision=1",
                             (identifier,)).fetchall()
        if (sum(_eligible(conn, row, policy, vote["user_id"]) for vote in votes) < policy["quorum"]
                or _role(conn, row, row["initiator_id"]) not in ("OPERATOR", "MANAGER", "ORG_ADMIN")):
            return None
        conn.execute("UPDATE workflow_dag_approvals SET status='CLAIMED' WHERE id=?", (identifier,))
        conn.execute("UPDATE workflow_executions SET status='RUNNING' WHERE id=?", (row["execution_id"],))
        conn.execute("""UPDATE workflow_step_runs SET status='COMPLETED', output_data='Approved',
            completed_at=CURRENT_TIMESTAMP WHERE id=? AND status='WAITING_APPROVAL'""", (identifier,))
        checkpoint = json.loads(row["checkpoint_json"])
        checkpoint["outputs"][row["step_key"]] = "Approved"
        return {**checkpoint, "execution_id": row["execution_id"],
                "user_context": {"sub": row["initiator_id"], "org_id": row["organization_id"]}}


def expire(db):
    """Close expired waits, including approvals not yet claimed by a worker."""
    with _transaction(db) as conn:
        now = int(time.time())
        rows = conn.execute("""SELECT * FROM workflow_dag_approvals
            WHERE status IN ('PENDING','APPROVED') AND expires_at<=?
            ORDER BY expires_at LIMIT 100""", (now,)).fetchall()
        for row in rows:
            _finish(conn, row, "TIMED_OUT", now)


def next_approved(db):
    with db._get_connection() as conn:
        row = conn.execute("""SELECT a.id,a.execution_id,x.workflow_id
            FROM workflow_dag_approvals a JOIN workflow_executions x
                ON x.id=a.execution_id AND x.status='WAITING_APPROVAL'
            WHERE a.status='APPROVED' AND a.expires_at>?
            ORDER BY a.decided_at,a.id LIMIT 1""", (int(time.time()),)).fetchone()
        return dict(row) if row else None


def fail_resume(db, identifier):
    """Fail closed when approval authority changed before a continuation could start."""
    with _transaction(db) as conn:
        row = conn.execute("SELECT * FROM workflow_dag_approvals WHERE id=? AND status='APPROVED'",
                           (identifier,)).fetchone()
        if row:
            _finish(conn, row, "REJECTED", int(time.time()))


def inbox(db, organization_id, department_id, user_id, *, after=""):
    with db._get_connection() as conn:
        rows = conn.execute("""SELECT a.*,w.id AS workflow_id,w.name AS workflow_name
            FROM workflow_dag_approvals a
            JOIN workflow_executions x ON x.id=a.execution_id AND x.status='WAITING_APPROVAL'
            JOIN workflows w ON w.id=x.workflow_id AND w.organization_id=a.organization_id
                AND w.department_id=a.department_id AND w.revision=a.workflow_revision
            WHERE a.organization_id=? AND a.department_id=? AND a.status='PENDING'
                AND a.expires_at>? AND a.id>? ORDER BY a.id LIMIT 51""",
            (organization_id, department_id, int(time.time()), after)).fetchall()
        items = []
        for row in rows[:50]:
            policy = json.loads(row["policy_json"])
            checkpoint = json.loads(row["checkpoint_json"])
            votes = conn.execute("SELECT user_id,decision FROM workflow_dag_approval_votes WHERE approval_id=?",
                                 (row["id"],)).fetchall()
            outputs = checkpoint["outputs"]
            items.append({
                **{key: row[key] for key in (
                    "id", "execution_id", "workflow_id", "workflow_name", "step_key", "expires_at",
                )},
                "approver_roles": policy["approver_roles"], "quorum": policy["quorum"],
                "approvals": sum(v["decision"] and _eligible(conn, row, policy, v["user_id"]) for v in votes),
                "can_decide": _eligible(conn, row, policy, user_id) and not any(v["user_id"] == user_id for v in votes),
                "cost_usd": checkpoint["cost_usd"],
                "outputs": [{"step_key": key, "excerpt": value[:4000], "truncated": len(value) > 4000}
                            for key, value in list(outputs.items())[-12:]],
                "omitted_outputs": max(0, len(outputs) - 12),
            })
        return {"items": items, "next_after": rows[49]["id"] if len(rows) > 50 else None}
