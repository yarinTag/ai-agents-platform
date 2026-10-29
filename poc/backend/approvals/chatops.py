"""
Dual-Channel Interactive ChatOps HITL Gating Service (Slack & Telegram).

Provides:
- Telegram Inline Keyboard generators & callback query handlers with in-place message updates.
- Slack Block Kit interactive message generators & interactivity action handlers.
- Unified resolution dispatching directly into Approvals / resume_task.
"""

import json
import logging
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime
import httpx

logger = logging.getLogger(__name__)


# ============================================================================
# Telegram Interactive Implementation
# ============================================================================

def format_telegram_approval(interaction: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    """
    Formats an approval or question into a Telegram HTML/Markdown message
    with interactive inline buttons.
    """
    interaction_id = interaction.get("id", "")
    task_id = interaction.get("task_id", "")
    agent_id = interaction.get("requester_agent_id", "")
    title = interaction.get("title", "Action Requires Human Approval")
    content = interaction.get("content", "")
    interaction_type = interaction.get("interaction_type", "PERMISSION_APPROVAL")

    type_badge = "🔐 <b>PERMISSION REQUIRED</b>" if interaction_type == "PERMISSION_APPROVAL" else "❓ <b>AGENT QUESTION</b>"

    text = (
        f"{type_badge}\n"
        f"<b>Title:</b> {title}\n"
        f"<b>Agent:</b> <code>{agent_id}</code> | <b>Task:</b> <code>{task_id}</code>\n\n"
        f"<b>Details:</b>\n<i>{content}</i>\n\n"
        f"<i>Please review and approve or reject this operation:</i>"
    )

    reply_markup = {
        "inline_keyboard": [
            [
                {
                    "text": "Approve & Resume ✅",
                    "callback_data": f"appr:approve:{interaction_id}"
                },
                {
                    "text": "Reject & Abort ❌",
                    "callback_data": f"appr:reject:{interaction_id}"
                }
            ]
        ]
    }

    return text, reply_markup


async def send_telegram_interactive_approval(
    bot_token: str,
    chat_id: str,
    interaction: Dict[str, Any]
) -> Optional[int]:
    """Sends Telegram message with inline keyboard via Telegram Bot API."""
    text, reply_markup = format_telegram_approval(interaction)
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "reply_markup": reply_markup
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                message_id = data.get("result", {}).get("message_id")
                logger.info(f"Dispatched interactive Telegram approval for interaction {interaction.get('id')}, msg_id={message_id}")
                return message_id
            else:
                logger.error(f"Failed to send Telegram approval: {resp.text}")
    except Exception as e:
        logger.error(f"Exception dispatching Telegram approval: {e}")
    return None


async def update_telegram_message_in_place(
    bot_token: str,
    chat_id: str,
    message_id: int,
    original_text: str,
    decision: str,
    responder: str
):
    """
    Edits the original Telegram message to reflect decision and removes action buttons.
    """
    status_emoji = "✅" if decision == "approve" else "❌"
    decision_text = "APPROVED" if decision == "approve" else "REJECTED"
    updated_at = datetime.utcnow().strftime("%H:%M:%S UTC")

    updated_text = (
        f"{original_text}\n\n"
        f"<b>━━━━━━━━━━━━━━━━━━━━</b>\n"
        f"{status_emoji} <b>Decision: {decision_text}</b>\n"
        f"👤 By: <code>{responder}</code> at <i>{updated_at}</i>\n"
        f"🚀 <i>Status updated in Control Plane</i>"
    )

    url = f"https://api.telegram.org/bot{bot_token}/editMessageText"
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": updated_text,
        "parse_mode": "HTML",
        "reply_markup": {"inline_keyboard": []}  # Remove buttons to prevent duplicate responses
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(url, json=payload)
    except Exception as e:
        logger.debug(f"Failed to edit Telegram message in-place: {e}")


# ============================================================================
# Slack Block Kit Interactive Implementation
# ============================================================================

def format_slack_approval_blocks(interaction: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Formats approval into Slack Block Kit payload with action buttons.
    """
    interaction_id = interaction.get("id", "")
    task_id = interaction.get("task_id", "")
    agent_id = interaction.get("requester_agent_id", "")
    title = interaction.get("title", "Action Requires Human Approval")
    content = interaction.get("content", "")
    interaction_type = interaction.get("interaction_type", "PERMISSION_APPROVAL")

    badge = "🔐 *Permission Approval Required*" if interaction_type == "PERMISSION_APPROVAL" else "❓ *Agent Clarification Request*"

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"AI Agents Platform: {title}"[:150],
                "emoji": True
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"{badge}\n"
                    f"*Agent:* `{agent_id}` | *Task:* `{task_id}`\n\n"
                    f"*Details:*\n>{content}\n"
                )
            }
        },
        {
            "type": "actions",
            "block_id": f"approval_block_{interaction_id}",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Approve & Resume ✅",
                        "emoji": True
                    },
                    "style": "primary",
                    "value": f"approve:{interaction_id}",
                    "action_id": "approve_action"
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Reject & Abort ❌",
                        "emoji": True
                    },
                    "style": "danger",
                    "value": f"reject:{interaction_id}",
                    "action_id": "reject_action"
                }
            ]
        }
    ]
    return blocks


async def send_slack_interactive_approval(
    webhook_url: str,
    interaction: Dict[str, Any]
) -> bool:
    """Dispatches Slack Block Kit interactive message."""
    blocks = format_slack_approval_blocks(interaction)
    payload = {
        "text": f"Approval required for task {interaction.get('task_id')}",
        "blocks": blocks
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(webhook_url, json=payload)
            if resp.status_code in (200, 204):
                logger.info(f"Dispatched Slack interactive approval for {interaction.get('id')}")
                return True
            else:
                logger.error(f"Slack webhook dispatch error: {resp.text}")
    except Exception as e:
        logger.error(f"Exception dispatching Slack approval: {e}")
    return False
