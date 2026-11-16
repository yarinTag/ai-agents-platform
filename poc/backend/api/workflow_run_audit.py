"""Allowlisted provenance for an already-authorized workflow execution."""
import json


def _receipt(value):
    try:
        result = json.loads(value or "{}")
    except (TypeError, ValueError):
        return {}
    if not isinstance(result, dict):
        return {}
    return {key: result[key] for key in ("message_id", "pull_number", "merge_commit_sha", "status")
            if type(result.get(key)) in (str, int)}


def execution_audit(db, execution, organization_id, context):
    identifier = execution.id
    with db._get_connection() as conn:
        trigger = conn.execute("""SELECT d.event_id,d.workflow_revision,d.binding_id,d.principal_id,d.sender_user_id,
            e.provider,e.connector_id,e.received_at,o.status AS outbox_status
            FROM channel_trigger_dispatches d JOIN channel_ingress_events e ON e.id=d.event_id
            LEFT JOIN channel_ingress_outbox o ON o.event_id=e.id
            WHERE d.execution_id=? AND e.organization_id=?""", (identifier, organization_id)).fetchone()
        dag = conn.execute("""SELECT a.id,a.step_key,a.status,a.decided_at,a.decided_by,s.started_at AS opened_at,
                d.status AS delivery_status,d.connector_id,d.message_id,d.binding_id,
                EXISTS(SELECT 1 FROM dag_channel_callbacks cb
                       WHERE cb.approval_id=a.id AND cb.user_id=a.decided_by) AS from_channel
            FROM workflow_dag_approvals a LEFT JOIN dag_channel_deliveries d ON d.approval_id=a.id
            LEFT JOIN workflow_step_runs s ON s.id=a.id AND s.execution_id=a.execution_id
            WHERE a.execution_id=? AND a.organization_id=? ORDER BY a.expires_at,a.id""",
                           (identifier, organization_id)).fetchall()
        terminal = conn.execute("""SELECT a.id,s.step_key,a.status,a.resolved_at AS decided_at,a.created_at AS opened_at,
                a.resolved_by AS decided_by,d.status AS delivery_status,d.connector_id,d.message_id,d.binding_id,
                d.callback_id IS NOT NULL AS from_channel
            FROM workflow_approvals a LEFT JOIN pr_channel_deliveries d ON d.approval_id=a.id
            LEFT JOIN workflow_step_runs s ON s.id=a.step_run_id AND s.execution_id=a.execution_id
            WHERE a.execution_id=? AND a.organization_id=? ORDER BY a.position""", (identifier, organization_id)).fetchall()
        calls = conn.execute("""SELECT c.id,c.connector_id,t.name AS operation,m.provider,c.status,
                c.started_at,c.completed_at,c.result,s.step_key
            FROM mcp_tool_calls c JOIN mcp_connectors m ON m.id=c.connector_id AND m.organization_id=?
            JOIN mcp_tools t ON t.id=c.tool_id AND t.connector_id=c.connector_id
            LEFT JOIN workflow_step_runs s ON s.execution_id=? AND s.task_run_id=c.task_id
            WHERE (c.run_id=? OR s.id IS NOT NULL)
                AND (lower(m.provider)='github' OR
                     (lower(m.provider) IN ('telegram','slack') AND t.name IN ('send_message','post_chat_message')))
            ORDER BY c.started_at DESC,c.id DESC LIMIT 101""", (organization_id, identifier, identifier)).fetchall()
    approvals = []
    for row in (*dag, *terminal):
        item = dict(row)
        from_channel = item.pop("from_channel")
        channel_provider = "slack" if "." in (item["message_id"] or "") else "telegram"
        item["decision_source"] = channel_provider if from_channel else "dashboard" if item["decided_by"] else None
        if item["status"] == "CLAIMED":
            item["status"] = "APPROVED"
        approvals.append(item)
    receipts = []
    for row in calls[:100]:
        item = dict(row)
        item["receipt"] = _receipt(item.pop("result"))
        receipts.append(item)
    return {"correlation_id": identifier, "workflow_revision": trigger["workflow_revision"] if trigger
            else context.get("workflow_revision"), "principal_id": trigger["principal_id"] if trigger
            else context.get("initiator_id"), "trigger": dict(trigger) if trigger else None, "approvals": approvals,
            "receipts": receipts, "receipts_truncated": len(calls) > 100}
