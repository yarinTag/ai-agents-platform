"""Bind workflow policy and optional ChatOps delivery at the composition root."""
import asyncio
import logging
from .capabilities import capabilities

logger = logging.getLogger(__name__)


def prompt_guard(database):
    def check(text, step_key, execution_id):
        from .security.firewall import get_prompt_firewall
        get_prompt_firewall().assert_clean_prompt(
            text=text, source=f"workflow_step:{step_key}", db_manager=database,
            actor=f"workflow_execution:{execution_id}",
        )
    return check


def sanitize_output(step_key, output):
    from .security.firewall import get_prompt_firewall
    return get_prompt_firewall().sanitize_mcp_output(tool_name=step_key, raw_output=output)


def approval_dispatch(database):
    def dispatch(task_id, execution_id):
        if not capabilities.enabled("approvals") or not capabilities.enabled("notifications"):
            return
        task = database.get_task_run(task_id)
        interactions = database.list_interactions(task_id=task_id, status="PENDING")
        if not task or not interactions:
            return
        from integrations.channels import find_channel_connector
        from .approvals.chatops import send_telegram_interactive_approval, send_slack_interactive_approval
        async def deliver():
            for provider in ("telegram", "slack"):
                connector = find_channel_connector(database, provider, task.organization_id)
                if not connector:
                    continue
                cfg = connector.configuration or {}
                try:
                    if provider == "telegram" and cfg.get("bot_token") and cfg.get("chat_id"):
                        await send_telegram_interactive_approval(cfg["bot_token"], str(cfg["chat_id"]), interactions[0])
                    elif provider == "slack" and cfg.get("webhook_url"):
                        await send_slack_interactive_approval(cfg["webhook_url"], interactions[0])
                except Exception:
                    logger.warning("Optional %s approval delivery failed for %s", provider, execution_id)
        asyncio.run(deliver())
    return dispatch
