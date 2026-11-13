"""Plan a channel-triggered run from a verified ingress claim and current policy."""
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import time
from uuid import uuid4

from integrations.channel_providers import CHANNEL_PROVIDERS
from integrations.identity_proofs import InvalidProof
from storage.external_identities import connector_settings, resolve_user
from .channel_trigger_rules import ChannelTriggerInput, TriggerRule, match_trigger


@dataclass(frozen=True)
class TriggerPlan:
    workflow_id: str
    revision: int
    principal_id: str
    sender_user_id: str
    binding_id: str
    event_id: str
    parameters: dict[str, str | None]


def _rank(conn, organization_id, department_id, user_id):
    row = conn.execute("""
        SELECT u.role, m.role AS department_role
        FROM users u LEFT JOIN department_members m ON m.user_id=u.id AND m.department_id=?
        WHERE u.id=? AND u.organization_id=? AND u.status='ACTIVE'
    """, (department_id, user_id, organization_id)).fetchone()
    levels = {"MEMBER": 1, "OPERATOR": 2, "MANAGER": 3, "ORG_ADMIN": 4}
    if not row:
        return 0
    if row["role"] == "ORG_ADMIN":
        return 4
    return min(levels.get(row["role"], 0), levels.get(row["department_role"], 0))


def plan_triggers(db, claim, *, connection=None):
    if connection is None:
        with db._get_connection() as conn:
            conn.execute("BEGIN")
            return plan_triggers(db, claim, connection=conn)
    conn = connection
    event = claim["event"]
    org, connector_id = event["organization_id"], event["connector_id"]
    if not event["sender_id"]:
        return []
    try:
        _, provider, (_, account, _), _ = connector_settings(conn, connector_id, org)
        sender = resolve_user(db, org, connector_id, event["sender_id"], connection=conn)
        if not sender or (provider, account) != (event["provider"], event["account"]):
            return []
        connector = conn.execute("SELECT configuration FROM mcp_connectors WHERE id=?",
                                 (connector_id,)).fetchone()
        adapter = CHANNEL_PROVIDERS.get(provider)
        if not adapter or event["channel_id"] not in adapter.configured_ids(json.loads(connector[0] or "{}")):
            return []
        return _eligible_plans(conn, event, sender, claim.get("trigger_text"))
    except InvalidProof:
        return []


def _eligible_plans(conn, event, sender, text):
    rows = conn.execute("""
        SELECT w.id, w.revision, w.department_id, w.definition_json, b.id AS binding_id
        FROM channel_bindings b JOIN workflows w
          ON w.organization_id=b.organization_id AND w.department_id=b.department_id
        JOIN department_mcp_access g ON g.department_id=b.department_id AND g.connector_id=b.connector_id
        WHERE b.organization_id=? AND b.connector_id=? AND b.channel_id=? AND b.provider=?
          AND b.trigger_workflows=1 AND w.is_active=1 AND g.is_active=1
          AND (g.organization_id IS NULL OR g.organization_id=b.organization_id)
        ORDER BY w.id
    """, (event["organization_id"], event["connector_id"], event["channel_id"], event["provider"]))
    plans = []
    for row in rows:
        try:
            metadata = json.loads(row["definition_json"]).get("metadata", {})
            rule = TriggerRule.model_validate(metadata.get("channel_trigger"))
        except (ValueError, AttributeError, TypeError):
            continue
        principal = metadata.get("channel_trigger_principal")
        if not rule.enabled or rule.binding_id != row["binding_id"] or not isinstance(principal, str):
            continue
        org, dept = event["organization_id"], row["department_id"]
        if _rank(conn, org, dept, sender) < 2 or _rank(conn, org, dept, principal) < 3:
            continue
        if text is None and rule.matcher != "event_type":
            continue
        inputs = ChannelTriggerInput(
            event_type=event["event_type"], channel_id=event["channel_id"],
            message_id=event["message_id"], sender_id=event["sender_id"], text=text or "",
        )
        parameters = match_trigger(rule, inputs)
        if parameters is not None:
            plans.append(TriggerPlan(row["id"], row["revision"], principal, sender,
                                     rule.binding_id, event["id"], parameters))
    return plans


def reserve_dispatches(db, claim):
    """Commit one execution and its provenance per event/workflow under the live lease."""
    event_id = claim["event"]["id"]
    created_at = datetime.now(timezone.utc).isoformat()
    with db._get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        lease = conn.execute("""SELECT 1 FROM channel_ingress_outbox
            WHERE event_id=? AND status='PROCESSING' AND lease_token=? AND lease_until>?""",
            (event_id, claim["lease_token"], int(time.time()))).fetchone()
        if lease is None:
            return []
        plans = plan_triggers(db, claim, connection=conn)
        # Recover reservations even when current policy no longer matches. Admission
        # will reject those runs and the worker can close their queued records.
        reserved = [row["execution_id"] for row in conn.execute(
            "SELECT execution_id FROM channel_trigger_dispatches WHERE event_id=? ORDER BY workflow_id",
            (event_id,),
        )]
        for plan in plans:
            existing = conn.execute("""SELECT execution_id FROM channel_trigger_dispatches
                WHERE event_id=? AND workflow_id=?""", (event_id, plan.workflow_id)).fetchone()
            if existing:
                continue
            execution_id = f"wf_exec_{uuid4().hex}"
            inserted = conn.execute("""INSERT INTO workflow_executions
                (id, workflow_id, trigger_type, trigger_payload, status, department_id, created_at)
                SELECT ?, id, 'CHANNEL', ?, 'QUEUED', department_id, ?
                FROM workflows WHERE id=? AND revision=? AND is_active=1""",
                (execution_id, json.dumps(plan.parameters, ensure_ascii=False), created_at,
                 plan.workflow_id, plan.revision))
            if not inserted.rowcount:
                continue
            conn.execute("""INSERT INTO channel_trigger_dispatches
                (event_id,workflow_id,execution_id,workflow_revision,binding_id,principal_id,sender_user_id)
                VALUES (?,?,?,?,?,?,?)""",
                (event_id, plan.workflow_id, execution_id, plan.revision,
                 plan.binding_id, plan.principal_id, plan.sender_user_id))
            reserved.append(execution_id)
        return reserved


def admit_dispatch(db, execution_id, workflow, lease_token):
    """Load server-owned parameters and claim the execution before any sandbox side effects."""
    with db._get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("""SELECT d.*, x.trigger_payload, e.connector_id, e.sender_id,
                   e.organization_id, e.provider, e.account, e.channel_id, e.message_id,
                   e.event_type, e.id, i.text AS trigger_text
            FROM channel_trigger_dispatches d
            JOIN workflow_executions x ON x.id=d.execution_id
            JOIN channel_ingress_events e ON e.id=d.event_id
            LEFT JOIN channel_ingress_trigger_inputs i ON i.event_id=e.id AND i.expires_at>?
            WHERE d.execution_id=? AND d.workflow_id=? AND d.workflow_revision=?
              AND x.trigger_type='CHANNEL' AND x.status='QUEUED'""",
            (int(time.time()), execution_id, workflow.id, workflow.revision)).fetchone()
        if row is None:
            return None
        parameters = json.loads(row["trigger_payload"])
        plans = plan_triggers(db, {"event": dict(row), "trigger_text": row["trigger_text"]}, connection=conn)
        if not any(plan.workflow_id == workflow.id and plan.revision == workflow.revision
                   and plan.binding_id == row["binding_id"] and plan.principal_id == row["principal_id"]
                   and plan.sender_user_id == row["sender_user_id"] and plan.parameters == parameters
                   for plan in plans):
            return None
        result = conn.execute("""UPDATE workflow_executions SET status='RUNNING', started_at=?
            WHERE id=? AND status='QUEUED' AND EXISTS (
                SELECT 1 FROM workflows WHERE id=? AND revision=? AND is_active=1
            ) AND EXISTS (
                SELECT 1 FROM channel_ingress_outbox WHERE event_id=?
                AND status='PROCESSING' AND lease_token=? AND lease_until>?
            )""", (datetime.now(timezone.utc).isoformat(), execution_id, workflow.id, workflow.revision,
                   row["event_id"], lease_token, int(time.time())))
        if not result.rowcount:
            return None
    return parameters, {"sub": row["principal_id"], "org_id": row["organization_id"]}
