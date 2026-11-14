"""Opt-in Telegram ingress for local SQLite deployments."""
import asyncio
import fcntl
import hashlib
import json
import logging

from integrations.identity_proofs import InvalidProof
from integrations.provider_http import request_json
from storage.external_identities import connector_settings

from .api.channel_ingress import MAX_BODY, _receive
from .dependencies import get_db_manager

logger = logging.getLogger(__name__)


def poll_connector(db, connector_id):
    with db._get_connection() as conn:
        _, provider, settings, version = connector_settings(conn, connector_id)
        row = conn.execute("SELECT configuration FROM mcp_connectors WHERE id=?", (connector_id,)).fetchone()
        config = json.loads(row["configuration"])
        duplicates = conn.execute("""SELECT count(*) FROM mcp_connectors WHERE lower(provider)='telegram'
            AND status='CONNECTED' AND CASE WHEN json_valid(configuration) THEN
                instr(json_extract(configuration,'$.bot_token'), ':') > 0
                AND substr(json_extract(configuration,'$.bot_token'),1,
                    instr(json_extract(configuration,'$.bot_token'), ':')-1)=? ELSE 0 END""",
            (settings[1],)).fetchone()[0]
    if provider != "telegram" or config.get("ingress_mode") != "polling":
        return
    if duplicates != 1:
        raise ValueError("Telegram polling requires a dedicated bot connector")
    token = config["bot_token"]
    credentials = (version, hashlib.sha256(token.encode()).hexdigest())
    key = f"telegram_poll_offset:{connector_id}:{settings[1]}"
    request = {"timeout": 3, "limit": 20, "allowed_updates": ["message", "callback_query"]}
    offset = int(db.get_setting(key) or 0)
    if offset:
        request["offset"] = offset
    response = request_json("api.telegram.org", f"/bot{token}/getUpdates", payload=request)
    updates = response.get("result") if isinstance(response, dict) and response.get("ok") is True else None
    if not isinstance(updates, list) or any(
            not isinstance(update, dict) or type(update.get("update_id")) is not int
            or not 0 < update["update_id"] < 2**63 - 1 for update in updates):
        raise ValueError("Invalid Telegram update response")
    for update in sorted(updates, key=lambda item: item["update_id"]):
        if update["update_id"] < offset:
            continue
        raw = json.dumps(update, ensure_ascii=False).encode()
        try:
            result = _receive(db, connector_id, raw, {}, polled_credentials=credentials) if len(raw) <= MAX_BODY else None
        except InvalidProof as exc:
            if str(exc) not in {"INVALID_EVENT", "INVALID_PROOF", "INVALID_APPROVAL_CALLBACK"}:
                raise
            result = None
        offset = update["update_id"] + 1
        db.set_setting(key, str(offset))
        if result is not None and result.media_type == "application/json":
            answer = json.loads(result.body)
            if answer.pop("method", None) == "answerCallbackQuery":
                try:
                    request_json("api.telegram.org", f"/bot{token}/answerCallbackQuery", payload=answer)
                except ValueError:
                    logger.warning("Telegram callback acknowledgment unavailable connector=%s", connector_id)


def poll(db):
    with db._get_connection() as conn:
        rows = conn.execute("""SELECT id FROM mcp_connectors
            WHERE lower(provider)='telegram' AND status='CONNECTED'
              AND CASE WHEN json_valid(configuration)
                  THEN json_extract(configuration,'$.ingress_mode')='polling' ELSE 0 END""").fetchall()
    if not rows:
        return
    with open(str(db.db_path.resolve()) + ".telegram-poll.lock", "a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        for row in rows:
            try:
                poll_connector(db, row["id"])
            except Exception as exc:
                logger.warning("Telegram polling unavailable connector=%s error=%s", row["id"], type(exc).__name__)


async def run(stop):
    while not stop.is_set():
        try:
            await asyncio.to_thread(poll, get_db_manager())
        except Exception:
            logger.warning("Telegram polling worker unavailable")
        try:
            await asyncio.wait_for(stop.wait(), timeout=2)
        except TimeoutError:
            continue
