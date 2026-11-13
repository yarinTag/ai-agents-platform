"""Verify provider bytes and project only stable event metadata."""
from dataclasses import dataclass
import json
import re

from .identity_proofs import InvalidProof, require_slack_signature, require_telegram_secret


@dataclass(frozen=True)
class Event:
    event_id: str
    event_type: str
    channel_id: str
    message_id: str
    sender_id: str | None


@dataclass(frozen=True)
class Handshake:
    challenge: str


@dataclass(frozen=True)
class IdentityProof:
    """Marker for the existing verifier. Never send these messages to the outbox."""


def _integer(value, *, signed=False):
    return type(value) is int and (-(2**63) if signed else 0) <= value < 2**63


def _personal_telegram_sender(message):
    sender = message.get("from")
    if (isinstance(sender, dict) and sender.get("is_bot") is False and _integer(sender.get("id"))
            and sender["id"] > 0 and not any(key in message for key in (
                "sender_chat", "forward_origin", "forward_date", "via_bot", "is_automatic_forward",
            ))):
        return str(sender["id"])
    return None


def _telegram(raw, headers, settings, now):
    require_telegram_secret(headers, settings)
    update = json.loads(raw)
    message = update.get("message")
    if message is None:
        return None
    chat = message["chat"]
    if (not _integer(update["update_id"]) or not _integer(message["message_id"])
            or not _integer(chat["id"], signed=True) or not chat["id"] or not message["message_id"]
            or not _integer(message["date"]) or not now - 86400 <= message["date"] <= now + 300):
        raise InvalidProof("INVALID_EVENT")
    body = message.get("text")
    if isinstance(body, str) and (body == "/start" or body.startswith(("/start ", "/start@"))):
        return IdentityProof()
    return Event(str(update["update_id"]), "MESSAGE", str(chat["id"]), str(message["message_id"]),
                 _personal_telegram_sender(message))


def _slack(raw, headers, settings, now):
    require_slack_signature(raw, headers, settings, now)
    if headers.get("content-type", "").split(";", 1)[0].strip().lower() == "application/x-www-form-urlencoded":
        return IdentityProof()
    envelope = json.loads(raw)
    if envelope["type"] == "url_verification":
        challenge = envelope["challenge"]
        if not isinstance(challenge, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", challenge):
            raise InvalidProof("INVALID_EVENT")
        return Handshake(challenge)
    _, team, app = settings
    if envelope.get("team_id") != team or envelope.get("api_app_id") != app:
        raise InvalidProof("INVALID_PROOF")
    if envelope["type"] != "event_callback":
        return None
    event = envelope["event"]
    if event["type"] != "message" or event.get("subtype"):
        return None
    event_id, channel, message = envelope["event_id"], event["channel"], event["ts"]
    if (not re.fullmatch(r"Ev[A-Za-z0-9]{2,80}", event_id)
            or not re.fullmatch(r"[CGD][A-Z0-9]{7,30}", channel)
            or not re.fullmatch(r"[0-9]{1,16}\.[0-9]{1,9}", message)):
        raise InvalidProof("INVALID_EVENT")
    user = event.get("user")
    sender = user if (not event.get("bot_id") and isinstance(user, str) and re.fullmatch(r"[UW][A-Z0-9]{2,31}", user)) else None
    return Event(event_id, "MESSAGE", channel, message, sender)


def verify_event(provider, raw, headers, settings, now):
    try:
        adapter = {"telegram": _telegram, "slack": _slack}[provider]
        return adapter(raw, headers, settings, now)
    except InvalidProof:
        raise
    except (TypeError, ValueError, KeyError, AttributeError, RecursionError):
        raise InvalidProof("INVALID_EVENT") from None
