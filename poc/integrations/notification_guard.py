"""Frozen, governed workflow completion delivery with atomic no-retry audit claims."""
import hashlib
import json
import sqlite3
from datetime import datetime
from .scoped_channels import send_message
from .tool_definitions import ToolAccessError, ensure_tools, require_credentials, resource_values, valid_channel
from .tool_scopes import execution_context, require_initiator


def notification_target(db, workflow, execution_id):
    context = execution_context(db, execution_id)
    execution = db.get_workflow_execution(execution_id)
    if (not context or not execution or execution.workflow_id != workflow.id or execution.trigger_type == 'PLAYGROUND'
            or workflow.organization_id != context['organization_id'] or workflow.department_id != context['department_id']
            or execution.department_id != workflow.department_id):
        raise ToolAccessError('Notification execution scope is unavailable or changed.')
    require_initiator(db, context.get('initiator_id'), workflow.organization_id, workflow.department_id)
    binding = context.get('binding') or {}
    connector = db.get_mcp_connector(binding.get('connector_id'))
    if (not connector or connector.organization_id != workflow.organization_id or connector.status != 'CONNECTED'
            or connector.provider not in ('telegram', 'slack') or connector.provider != binding.get('provider')):
        raise ToolAccessError('The exact notification connector is unavailable in this organization.')
    grant = db.get_department_mcp_access(workflow.department_id, connector.id)
    if not grant or not grant.is_active or grant.organization_id not in (None, workflow.organization_id):
        raise ToolAccessError('Notification connector grant is unavailable.')
    require_credentials(connector)
    operation = 'send_message' if connector.provider == 'telegram' else 'post_chat_message'
    tool = ensure_tools(db, connector)[operation]
    if not db.check_department_mcp_permission(workflow.department_id, connector.id, operation)['allowed']:
        raise ToolAccessError('Notification message delivery is not granted to this department.')
    channel = binding.get('channel_id', '')
    if channel not in resource_values(connector.configuration or {}, 'channels') or not valid_channel(connector.provider, channel):
        raise ToolAccessError('Configure an allowed exact notification channel ID; display-name aliases are not accepted.')
    return connector, tool, channel, binding


def deliver_notification(db, workflow, execution_id, text):
    connector, tool, channel, _ = notification_target(db, workflow, execution_id)
    # An explicit send step already delivered this destination; do not send it again.
    with db._get_connection() as conn:
        calls = conn.execute('''SELECT c.arguments FROM mcp_tool_calls c
            JOIN workflow_tool_scopes s ON s.task_id=c.task_id
            WHERE s.execution_id=? AND c.connector_id=? AND c.status='COMPLETED' ''',
            (execution_id, connector.id)).fetchall()
    if any(json.loads(call['arguments'] or '{}').get('channel_id') == channel for call in calls):
        return {'delivery': 'already_delivered', 'channel_id': channel}
    # A real execution agent owns the audit record, never an arbitrary tenant agent.
    with db._get_connection() as conn:
        row = conn.execute('SELECT agent_id FROM workflow_step_runs WHERE execution_id=? ORDER BY started_at DESC LIMIT 1',
                           (execution_id,)).fetchone()
    actor = db.get_agent(row['agent_id']) if row else None
    if not actor or actor.organization_id != workflow.organization_id or actor.department_id not in (None, workflow.department_id):
        raise ToolAccessError('Notification has no authorized execution audit actor.')
    identifier = 'call_notify_' + execution_id
    arguments = {'channel_id': channel, 'message_sha256': hashlib.sha256(text.encode()).hexdigest()}
    with db._get_connection() as conn:
        try:
            conn.execute('''INSERT INTO mcp_tool_calls
                (id,connector_id,tool_id,agent_id,run_id,status,arguments,started_at)
                VALUES (?,?,?,?,?,'STARTED',?,?)''', (identifier, connector.id, tool.id, actor.id, execution_id,
                json.dumps(arguments), datetime.now().isoformat()))
        except sqlite3.IntegrityError as exc:
            raise ToolAccessError('Notification was already attempted; it will not be resent automatically.') from exc
    try:
        def authorize():
            notification_target(db, workflow, execution_id)
        output = send_message(connector, channel, text, authorize)
        db.update_mcp_tool_call(identifier, 'COMPLETED', result=json.dumps(output), completed_at=datetime.now().isoformat())
        return output
    except Exception as exc:
        # ToolAccessError contains fixed, credential-safe policy/provider diagnostics.
        detail = str(exc) if isinstance(exc, ToolAccessError) else 'Notification delivery failed or is unknown. No automatic resend was made.'
        db.update_mcp_tool_call(identifier, 'FAILED', error=detail,
                               completed_at=datetime.now().isoformat())
        raise ToolAccessError(detail) from exc
