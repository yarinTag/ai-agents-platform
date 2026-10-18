"""
Shared Channel Notification Dispatcher.
Centralizes outgoing notifications (Telegram, Slack, Webhook) and MCP tool-call audit logging
so that neither WorkflowEngine nor MCP API routers duplicate channel dispatch logic.
"""

import json
import logging
import urllib.error
import urllib.request
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

BOT_PLACEHOLDER_TARGETS = ("@agents_office_alerts", "@hermesganbot", "hermesganbot", "Hermes_test")


def resolve_telegram_target_chat(requested_channel: str, configured_chat_id: Optional[str]) -> str:
    """Resolve placeholder bot names to the configured Telegram chat_id when available."""
    if not requested_channel:
        return configured_chat_id or ""
    if configured_chat_id:
        if requested_channel in BOT_PLACEHOLDER_TARGETS or requested_channel.lower().endswith("bot"):
            return configured_chat_id
    return requested_channel


def dispatch_channel_message(
    db: Any,
    provider: str,
    channel_id: str,
    message: str,
    connector_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    raise_on_http_error: bool = False
) -> Dict[str, Any]:
    """
    Dispatch a notification message to a configured communication provider (Telegram / Slack)
    and record the corresponding MCP tool call in the database.
    """
    call_id = f"call_notify_{uuid.uuid4().hex[:8]}"
    now = datetime.now().isoformat()
    delivery_status = "simulated"
    provider_clean = (provider or "slack").lower()

    conn = None
    try:
        conn = db.get_mcp_connector(provider_clean)
    except Exception:
        conn = None

    resolved_agent_id = agent_id
    if not resolved_agent_id:
        try:
            agents = db.list_agents()
            resolved_agent_id = agents[0].id if agents else "ceo-orchestrator"
        except Exception:
            resolved_agent_id = "ceo-orchestrator"

    if conn and provider_clean == "telegram" and conn.configuration:
        bot_token = conn.configuration.get("bot_token")
        configured_chat_id = conn.configuration.get("chat_id")
        target_chat = resolve_telegram_target_chat(channel_id, configured_chat_id)

        if bot_token and target_chat:
            try:
                payload = json.dumps({"chat_id": target_chat, "text": message}).encode("utf-8")
                telegram_req = urllib.request.Request(
                    f"https://api.telegram.org/bot{bot_token}/sendMessage",
                    data=payload,
                    headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(telegram_req, timeout=5) as response:
                    if response.status == 200:
                        delivery_status = "delivered"
                        logger.info(f"Delivered live Telegram notification to {target_chat}")
            except urllib.error.HTTPError as h_ex:
                err_body = h_ex.read().decode("utf-8", errors="ignore")
                if raise_on_http_error:
                    raise RuntimeError(
                        f"Telegram API Error ({h_ex.code}): {err_body}. "
                        f"Tip: Telegram bots cannot message themselves. Use your personal Chat ID "
                        f"(e.g. {configured_chat_id or '1176967752'}) or an authorized channel."
                    ) from h_ex
                logger.warning(f"Telegram API HTTP warning ({h_ex.code}): {err_body}")
            except Exception as ex:
                if raise_on_http_error:
                    raise RuntimeError(f"Telegram dispatch failed: {ex}") from ex
                logger.warning(f"Failed to post live notification to Telegram API: {ex}")

    try:
        effective_connector_id = connector_id or (conn.id if conn else provider_clean)
        # Ensure connector stub exists if we record a workflow notification tool call
        if not conn and connector_id:
            with db._get_connection() as raw_conn:
                raw_conn.execute(
                    "INSERT OR IGNORE INTO mcp_connectors (id, name, provider, status) VALUES (?, ?, ?, 'CONNECTED')",
                    (effective_connector_id, effective_connector_id.title(), provider_clean)
                )
                raw_conn.commit()

        if conn or connector_id:
            db.save_mcp_tool_call({
                "id": call_id,
                "connector_id": effective_connector_id,
                "tool_id": f"tool_{provider_clean}_send_message",
                "agent_id": resolved_agent_id,
                "task_id": None,
                "arguments": {"channel": channel_id, "text": message},
                "status": "COMPLETED",
                "result": f"Status: {delivery_status} to {channel_id}",
                "started_at": now,
                "completed_at": now
            })
    except Exception as log_err:
        logger.debug(f"Could not persist notification MCP tool call log: {log_err}")

    return {
        "status": "success",
        "delivery": delivery_status,
        "provider": provider,
        "channel_id": channel_id,
        "message": message,
        "call_id": call_id,
        "timestamp": now
    }


def dispatch_workflow_completion_notification(
    db: Any,
    workflow_id: str,
    final_status: str,
    trigger_type: str,
    step_outputs: Dict[str, str],
    total_tokens: int,
    total_cost_usd: float,
    failure_error: Optional[str] = None
) -> None:
    """Format and dispatch a workflow completion notification if channel_binding is configured."""
    try:
        wf_record = db.get_workflow(workflow_id)
        if not wf_record or not wf_record.definition_json:
            return
        dj = json.loads(wf_record.definition_json)
        channel_binding = dj.get("metadata", {}).get("channel_binding")
        if not channel_binding:
            return

        notify_mode = channel_binding.get("notify_mode", "ON_COMPLETE")
        should_notify = (
            notify_mode == "ALWAYS"
            or (notify_mode == "ON_COMPLETE" and final_status == "COMPLETED")
            or (notify_mode == "ON_FAILURE" and final_status == "FAILED")
        )
        if not should_notify:
            return

        provider = channel_binding.get("provider", "slack")
        channel_id = channel_binding.get("channel_id", "")
        custom_tmpl = channel_binding.get("message_template")

        final_output = list(step_outputs.values())[-1] if step_outputs else ""
        if len(final_output) > 2500:
            final_output = final_output[:2450] + "...\n(truncated)"

        if custom_tmpl:
            msg_body = custom_tmpl.replace("{{workflow_name}}", wf_record.name).replace("{{status}}", final_status)
            if "{{output}}" in custom_tmpl:
                msg_body = msg_body.replace("{{output}}", final_output)
            elif final_output and final_output not in msg_body:
                msg_body += f"\n\n📋 *Workflow Summary / Report:*\n{final_output}"
        else:
            msg_body = (
                f"🤖 *Workflow Run Notification*\n"
                f"• Workflow: *{wf_record.name}* (`{wf_record.id}`)\n"
                f"• Status: *{final_status}*\n"
                f"• Trigger: `{trigger_type}`\n"
                f"• Tokens: {total_tokens} (Cost: ${total_cost_usd:.4f})"
            )
            if final_output:
                msg_body += f"\n\n📋 *Result:*\n{final_output}"
            if failure_error:
                msg_body += f"\n• Error: {failure_error}"

        dispatch_channel_message(
            db=db,
            provider=provider,
            channel_id=channel_id,
            message=msg_body,
            connector_id=channel_binding.get("connector_id", provider),
            agent_id="ceo-orchestrator",
            raise_on_http_error=False
        )
    except Exception as notify_err:
        logger.warning(f"Failed to dispatch channel binding notification: {notify_err}")
