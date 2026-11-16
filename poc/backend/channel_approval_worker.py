"""Deliver and reconcile Telegram approval cards outside callback handling."""
import asyncio
import logging

from governance.policy import decide
from integrations.telegram_approval_cards import action_token, write_card as write_telegram_card
from integrations.slack_approval_cards import write_card as write_slack_card
from integrations.tool_scopes import execution_context
from storage import channel_approval_delivery as delivery
from workflows.approval_config import optional_public_url
from .dependencies import get_db_manager

logger = logging.getLogger(__name__)


def _destination(db, row):
    with db._get_connection() as conn:
        binding, config, bot, _ = delivery.destination(conn, row)
    context = execution_context(db, row["execution_id"]) or {}
    if context.get("workflow_revision") != row["workflow_revision"] or context.get("governance") is None:
        raise ValueError("Approval delivery has no captured policy.")
    operation = {'telegram': 'telegram.send_message', 'slack': 'slack.post_chat_message'}[binding['provider']]
    decision = decide(db, row["organization_id"], row["department_id"], binding["connector_id"],
                      operation, binding["channel_id"],
                      user_id=context.get("initiator_id") if "config_json" in row else row["initiator_id"],
                      workflow_id=row["workflow_id"], frozen=context["governance"])
    if decision["decision"] != "allowed":
        raise ValueError("Approval delivery is not authorized.")
    return binding, config["bot_token"], bot, config["identity_webhook_secret" if binding["provider"] == "telegram" else "identity_signing_secret"]


def _write(binding, bot_token, row, state, secret, **kwargs):
    origin = optional_public_url()
    if binding["provider"] == "slack":
        return write_slack_card(bot_token, binding["channel_id"], row, state, origin, proof_secret=secret, **kwargs)
    return write_telegram_card(bot_token, binding["channel_id"], row, state, origin, proof_secret=secret, **kwargs)


def _send(db, row):
    try:
        binding, bot_token, bot, secret = _destination(db, row)
        token = action_token(bot_token, row["id"])
        with db._get_connection() as conn:
            table = "workflow_approvals" if "config_json" in row else "workflow_dag_approvals"
            current = conn.execute(f"SELECT * FROM {table} WHERE id=?", (row["id"],)).fetchone()
            state = delivery.message_state(conn, current)
        message = _write(binding, bot_token, row, state, secret, token=token)
        delivery.record_delivery(db, row["id"], "DELIVERED", connector=binding["connector_id"],
                                 channel=binding["channel_id"], message=message, bot=bot, rendered=state, token=token)
    except Exception:
        delivery.record_delivery(db, row["id"], "UNCONFIRMED")
        logger.warning("Approval card delivery unconfirmed approval_id=%s", row["id"])


def _edit(db, row, state):
    try:
        binding, bot_token, bot, secret = _destination(db, row)
        if (binding["connector_id"], binding["channel_id"], bot) != (
            row["connector_id"], row["channel_id"], row["bot_id"],
        ):
            return
        token = action_token(bot_token, row["id"])
        if delivery.digest(token) != row["token_digest"]:
            token = None
        _write(binding, bot_token, row, state, secret, message_id=row["message_id"], token=token)
        delivery.record_edit(db, row["id"], state)
    except Exception:
        logger.warning("Approval card edit unconfirmed approval_id=%s", row["id"])


def consume(db):
    from storage.terminal_channel_approval import consume as consume_terminal
    edit = delivery.next_edit(db)
    if edit:
        _edit(db, *edit)
    consume_terminal(db)
    from workflows.pr_approval_sequence import advance_confirmed
    advance_confirmed(db)
    row = delivery.next_delivery(db)
    if row:
        _send(db, row)
    edit = delivery.next_edit(db)
    if edit:
        _edit(db, *edit)


async def run(stop):
    while not stop.is_set():
        try:
            await asyncio.to_thread(lambda: consume(get_db_manager()))
        except Exception:
            logger.warning("Approval card worker unavailable")
        try:
            await asyncio.wait_for(stop.wait(), timeout=2)
        except TimeoutError:
            continue
