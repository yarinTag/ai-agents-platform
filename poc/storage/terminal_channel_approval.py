"""Claim verified terminal approval decisions without exposing merge authority to chat."""
from datetime import datetime

from .dag_approvals import ApprovalConflict, _role


def claim(conn, row, user_id, callback):
    if _role(conn, row, user_id) not in ("MANAGER", "ORG_ADMIN"):
        raise PermissionError("Current department approval authority is required.")
    identity = conn.execute("""SELECT id FROM external_identity_links
        WHERE organization_id=? AND connector_id=? AND user_id=?
          AND provider='telegram' AND account=? AND subject=?""",
        (row["organization_id"], row["connector_id"], user_id, row["bot_id"], callback.sender_id)).fetchone()
    if not identity:
        raise PermissionError("The verified identity link is unavailable.")
    now = datetime.now().isoformat()
    result = conn.execute("""UPDATE workflow_approvals SET status='RESOLVING',resolved_by=?
        WHERE id=? AND status='PENDING' AND expires_at>? AND EXISTS (
            SELECT 1 FROM workflow_executions x JOIN workflows w ON w.id=x.workflow_id
            WHERE x.id=workflow_approvals.execution_id AND x.status='WAITING_APPROVAL'
                AND w.revision=workflow_approvals.workflow_revision
                AND w.organization_id=workflow_approvals.organization_id
                AND w.department_id=workflow_approvals.department_id
        )""", (user_id, row["id"], now))
    if not result.rowcount:
        raise ApprovalConflict("Approval is unavailable or no longer pending.")
    conn.execute("""UPDATE pr_channel_deliveries SET callback_id=?,decision=?,identity_link_id=?
        WHERE approval_id=?""", (callback.callback_id, int(callback.approve), identity["id"], row["id"]))


def consume(db):
    from workflows.human_approval import expire_if_due, resolve
    with db._get_connection() as conn:
        expired = conn.execute("""SELECT a.* FROM workflow_approvals a
            JOIN pr_channel_deliveries d ON d.approval_id=a.id
            WHERE a.status='PENDING' AND a.expires_at<=? LIMIT 50""",
            (datetime.now().isoformat(),)).fetchall()
    for row in expired:
        expire_if_due(db, row)
    with db._get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("""SELECT a.*,d.decision,d.connector_id,d.channel_id,d.binding_id,d.bot_id,d.identity_link_id
            FROM workflow_approvals a JOIN pr_channel_deliveries d ON d.approval_id=a.id
            WHERE a.status='RESOLVING' AND d.decision IN (0,1)
            ORDER BY a.created_at LIMIT 1""").fetchone()
        if not row:
            return
        # Never automatically retry a merge attempt after an interrupted worker.
        conn.execute("UPDATE pr_channel_deliveries SET decision=NULL WHERE approval_id=?", (row["id"],))

    def authorize():
        from .channel_approval_delivery import destination
        with db._get_connection() as conn:
            if _role(conn, row, row["resolved_by"]) not in ("MANAGER", "ORG_ADMIN"):
                raise PermissionError("Approver no longer authorized.")
            binding, _, account, _ = destination(conn, row)
            if (binding["connector_id"], binding["channel_id"], account) != (
                row["connector_id"], row["channel_id"], row["bot_id"],
            ):
                raise PermissionError("Approval destination changed.")
            linked = conn.execute("""SELECT 1 FROM external_identity_links
                WHERE organization_id=? AND connector_id=? AND user_id=?
                  AND provider='telegram' AND account=? AND id=?""",
                (row["organization_id"], row["connector_id"], row["resolved_by"], account,
                 row["identity_link_id"])).fetchone()
            if not linked:
                raise PermissionError("Approver identity link was revoked.")

    resolve(db, dict(row), bool(row["decision"]), authorize)
