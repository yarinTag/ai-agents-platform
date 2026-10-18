"""
Shared Channel Notification Dispatcher.
Centralizes outgoing notifications (Telegram, Slack, Webhook), configurable workflow
notification policies (FINAL_ONLY, START_AND_END, EVERY_STEP, ON_FAILURE_ONLY),
and MCP tool-call audit logging.
"""

import json
import logging
import urllib.error
import urllib.request
import uuid
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

BOT_PLACEHOLDER_TARGETS = ("@agents_office_alerts", "@hermesganbot", "hermesganbot", "Hermes_test")
VALID_NOTIFY_POLICIES = ("FINAL_ONLY", "START_AND_END", "EVERY_STEP", "ON_FAILURE_ONLY")


def resolve_telegram_target_chat(requested_channel: str, configured_chat_id: Optional[str]) -> str:
    """Resolve placeholder bot names to the configured Telegram chat_id when available."""
    if not requested_channel:
        return configured_chat_id or ""
    if configured_chat_id and (
        requested_channel in BOT_PLACEHOLDER_TARGETS or requested_channel.lower().endswith("bot")
    ):
        return configured_chat_id
    return requested_channel


def should_send_notification(
    channel_binding: Dict[str, Any],
    event_type: str,
    final_status: str = "COMPLETED",
    step_notify_override: bool = False,
) -> bool:
    """Evaluate whether a workflow lifecycle event should trigger a channel notification."""
    if not channel_binding or not isinstance(channel_binding, dict):
        return False

    policy = str(channel_binding.get("notify_policy") or "FINAL_ONLY").upper()
    event_upper = str(event_type or "").upper()
    status_upper = str(final_status or "COMPLETED").upper()

    if policy == "ON_FAILURE_ONLY":
        return status_upper == "FAILED"
    if policy == "EVERY_STEP":
        return event_upper in ("WORKFLOW_START", "STEP_COMPLETE", "WORKFLOW_END")
    if policy == "START_AND_END":
        return event_upper in ("WORKFLOW_START", "WORKFLOW_END") or (
            event_upper == "STEP_COMPLETE" and bool(step_notify_override)
        )

    # Default policy: FINAL_ONLY (with backward-compatible notify_mode support)
    if event_upper == "STEP_COMPLETE":
        return bool(step_notify_override)
    if event_upper == "WORKFLOW_END":
        notify_mode = str(channel_binding.get("notify_mode") or "ON_COMPLETE").upper()
        return (
            notify_mode == "ALWAYS"
            or (notify_mode == "ON_COMPLETE" and status_upper == "COMPLETED")
            or (notify_mode == "ON_FAILURE" and status_upper == "FAILED")
        )
    return False


def dispatch_channel_message(
    db: Any, provider: str, channel_id: str, message: str,
    connector_id: Optional[str] = None, agent_id: Optional[str] = None,
    raise_on_http_error: bool = False,
) -> Dict[str, Any]:
    """Dispatch a notification message (Telegram / Slack) and record the MCP tool call."""
    call_id = f"call_notify_{uuid.uuid4().hex[:8]}"
    now = datetime.now().isoformat()
    delivery_status = "simulated"
    provider_clean = (provider or "slack").lower()

    try:
        conn = db.get_mcp_connector(provider_clean)
    except Exception:
        conn = None

    resolved_agent_id = agent_id or "ceo-orchestrator"
    if not agent_id:
        try:
            agents = db.list_agents()
            resolved_agent_id = agents[0].id if agents else "ceo-orchestrator"
        except Exception:
            pass

    if conn and provider_clean == "telegram" and conn.configuration:
        bot_token = conn.configuration.get("bot_token")
        configured_chat_id = conn.configuration.get("chat_id")
        target_chat = resolve_telegram_target_chat(channel_id, configured_chat_id)
        if bot_token and target_chat:
            try:
                payload = json.dumps({"chat_id": target_chat, "text": message}).encode("utf-8")
                req = urllib.request.Request(
                    f"https://api.telegram.org/bot{bot_token}/sendMessage",
                    data=payload,
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=5) as response:
                    if response.status == 200:
                        delivery_status = "delivered"
            except urllib.error.HTTPError as h_ex:
                err_body = h_ex.read().decode("utf-8", errors="ignore")
                if raise_on_http_error:
                    raise RuntimeError(f"Telegram API Error ({h_ex.code}): {err_body}") from h_ex
                logger.warning(f"Telegram API HTTP warning ({h_ex.code}): {err_body}")
            except Exception as ex:
                if raise_on_http_error:
                    raise RuntimeError(f"Telegram dispatch failed: {ex}") from ex
                logger.warning(f"Failed to post live notification to Telegram API: {ex}")

    try:
        effective_connector_id = connector_id or (conn.id if conn else provider_clean)
        if not conn and connector_id:
            with db._get_connection() as raw_conn:
                raw_conn.execute(
                    "INSERT OR IGNORE INTO mcp_connectors (id, name, provider, status) VALUES (?, ?, ?, 'CONNECTED')",
                    (effective_connector_id, effective_connector_id.title(), provider_clean),
                )
                raw_conn.commit()
        if conn or connector_id:
            db.save_mcp_tool_call({
                "id": call_id, "connector_id": effective_connector_id,
                "tool_id": f"tool_{provider_clean}_send_message", "agent_id": resolved_agent_id,
                "task_id": None, "arguments": {"channel": channel_id, "text": message},
                "status": "COMPLETED", "result": f"Status: {delivery_status} to {channel_id}",
                "started_at": now, "completed_at": now,
            })
    except Exception as log_err:
        logger.debug(f"Could not persist notification MCP tool call log: {log_err}")

    return {
        "status": "success", "delivery": delivery_status, "provider": provider,
        "channel_id": channel_id, "message": message, "call_id": call_id, "timestamp": now,
    }


def _load_workflow_channel_binding(db: Any, workflow_id: str) -> Tuple[Optional[Any], Optional[Dict[str, Any]]]:
    """Load workflow record and its metadata.channel_binding dictionary if present."""
    wf_record = db.get_workflow(workflow_id)
    if not wf_record or not wf_record.definition_json:
        return None, None
    dj = json.loads(wf_record.definition_json)
    binding = dj.get("metadata", {}).get("channel_binding")
    return wf_record, (binding if isinstance(binding, dict) else None)


def _send_bound_message(db: Any, channel_binding: Dict[str, Any], message: str) -> Dict[str, Any]:
    """Send a formatted message using the workflow's channel_binding configuration."""
    provider = channel_binding.get("provider", "slack")
    return dispatch_channel_message(
        db=db, provider=provider, channel_id=channel_binding.get("channel_id", ""),
        message=message, connector_id=channel_binding.get("connector_id", provider),
        agent_id="ceo-orchestrator", raise_on_http_error=False,
    )


def dispatch_workflow_start_notification(
    db: Any, workflow_id: str, execution_id: str, trigger_type: str, total_steps: int
) -> Optional[Dict[str, Any]]:
    """Dispatch a notification when a workflow execution starts if permitted by notify_policy."""
    try:
        wf_record, binding = _load_workflow_channel_binding(db, workflow_id)
        if not wf_record or not binding or not should_send_notification(binding, "WORKFLOW_START", "RUNNING"):
            return None
        msg = (
            f"🚀 *Workflow Started*\n• Workflow: *{wf_record.name}* (`{wf_record.id}`)\n"
            f"• Execution: `{execution_id}` | Trigger: `{trigger_type}` | Steps: {total_steps}"
        )
        return _send_bound_message(db, binding, msg)
    except Exception as notify_err:
        logger.warning(f"Failed to dispatch workflow start notification: {notify_err}")
        return None


def dispatch_workflow_step_notification(
    db: Any, workflow_id: str, execution_id: str, step_key: str, step_name: str,
    status: str, step_output: str, tokens: int = 0, cost_usd: float = 0.0,
    step_notify_override: bool = False,
) -> Optional[Dict[str, Any]]:
    """Dispatch a step-level notification if permitted by notify_policy or step_notify_override."""
    try:
        wf_record, binding = _load_workflow_channel_binding(db, workflow_id)
        if not wf_record or not binding:
            return None
        step_map = binding.get("step_notifications") or {}
        override = bool(step_notify_override or step_map.get(step_key, False))
        if not should_send_notification(binding, "STEP_COMPLETE", final_status=status, step_notify_override=override):
            return None
        summary = (step_output or "")[:1200]
        msg = (
            f"🔹 *Workflow Step Completed*\n• Workflow: *{wf_record.name}* (`{execution_id}`)\n"
            f"• Step: *{step_name or step_key}* (`{step_key}`) | Status: *{status}* | Tokens: {tokens} (${cost_usd:.4f})"
        )
        if summary:
            msg += f"\n\n📄 *Step Output:*\n{summary}"
        return _send_bound_message(db, binding, msg)
    except Exception as notify_err:
        logger.warning(f"Failed to dispatch workflow step notification: {notify_err}")
        return None


def dispatch_workflow_completion_notification(
    db: Any, workflow_id: str, final_status: str, trigger_type: str,
    step_outputs: Dict[str, str], total_tokens: int, total_cost_usd: float,
    failure_error: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Format and dispatch a workflow completion notification if channel_binding is configured."""
    try:
        wf_record, binding = _load_workflow_channel_binding(db, workflow_id)
        if not wf_record or not binding or not should_send_notification(binding, "WORKFLOW_END", final_status):
            return None

        custom_tmpl = binding.get("message_template")
        final_output = list(step_outputs.values())[-1] if step_outputs else ""
        if len(final_output) > 2500:
            final_output = final_output[:2450] + "...\n(truncated)"

        if custom_tmpl:
            msg = custom_tmpl.replace("{{workflow_name}}", wf_record.name).replace("{{status}}", final_status)
            if "{{output}}" in custom_tmpl:
                msg = msg.replace("{{output}}", final_output)
            elif final_output and final_output not in msg:
                msg += f"\n\n📋 *Workflow Summary / Report:*\n{final_output}"
        else:
            msg = (
                f"🤖 *Workflow Run Notification*\n• Workflow: *{wf_record.name}* (`{wf_record.id}`)\n"
                f"• Status: *{final_status}* | Trigger: `{trigger_type}` | Tokens: {total_tokens} (Cost: ${total_cost_usd:.4f})"
            )
            if final_output:
                msg += f"\n\n📋 *Result:*\n{final_output}"
            if failure_error:
                msg += f"\n• Error: {failure_error}"

        return _send_bound_message(db, binding, msg)
    except Exception as notify_err:
        logger.warning(f"Failed to dispatch channel binding notification: {notify_err}")
        return None
