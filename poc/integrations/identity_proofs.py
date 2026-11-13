"""Verify provider requests before extracting a personal linking subject."""
import hashlib
import hmac
import json
import re
from urllib.parse import parse_qs


class InvalidProof(ValueError):
    pass


def configuration(provider, config):
    if provider == "telegram":
        secret = config.get("identity_webhook_secret")
        token = config.get("bot_token")
        account = token.partition(":")[0] if isinstance(token, str) else ""
        if isinstance(secret, str) and re.fullmatch(r"[A-Za-z0-9_-]{32,256}", secret) and account.isascii() and account.isdigit():
            return secret, account, ""
    if provider == "slack":
        secret, team, app = (config.get(key) for key in ("identity_signing_secret", "identity_team_id", "identity_app_id"))
        if (isinstance(secret, str) and 32 <= len(secret) <= 256
                and isinstance(team, str) and re.fullmatch(r"T[A-Z0-9]{2,31}", team)
                and isinstance(app, str) and re.fullmatch(r"A[A-Z0-9]{2,31}", app)):
            return secret, team, app
    raise InvalidProof("PROVIDER_UNCONFIGURED")


def require_telegram_secret(headers, settings):
    secret, _, _ = settings
    header = headers.get("x-telegram-bot-api-secret-token", "")
    if not hmac.compare_digest(header.encode(), secret.encode()):
        raise InvalidProof("INVALID_PROOF")


def telegram(raw, headers, settings, now):
    require_telegram_secret(headers, settings)
    update = json.loads(raw)
    message = update["message"]
    sender, chat = message["from"], message["chat"]
    identifier = sender["id"]
    if (type(identifier) is not int or not 0 < identifier < 10**20 or sender.get("is_bot") is not False
            or chat["type"] != "private" or chat["id"] != identifier
            or any(key in message for key in ("sender_chat", "forward_origin", "forward_date", "via_bot", "is_automatic_forward"))
            or type(message["date"]) is not int or abs(now - message["date"]) > 300):
        raise InvalidProof("INVALID_PROOF")
    command, _, challenge = message["text"].partition(" ")
    if command != "/start":
        raise InvalidProof("INVALID_PROOF")
    return str(identifier), challenge


def require_slack_signature(raw, headers, settings, now):
    secret, _, _ = settings
    timestamp = headers.get("x-slack-request-timestamp", "")
    if not re.fullmatch(r"[0-9]{1,12}", timestamp) or abs(now - int(timestamp)) > 300:
        raise InvalidProof("INVALID_PROOF")
    signed = b"v0:" + timestamp.encode() + b":" + raw
    signature = "v0=" + hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature.encode(), headers.get("x-slack-signature", "").encode()):
        raise InvalidProof("INVALID_PROOF")


def slack(raw, headers, settings, now):
    require_slack_signature(raw, headers, settings, now)
    _, team, app = settings
    fields = parse_qs(raw.decode("utf-8"), strict_parsing=True, max_num_fields=32)

    def field(name):
        value, = fields[name]
        return value

    if field("team_id") != team or field("api_app_id") != app or field("command") != "/platform-link":
        raise InvalidProof("INVALID_PROOF")
    subject = field("user_id")
    if not re.fullmatch(r"[UW][A-Z0-9]{2,31}", subject):
        raise InvalidProof("INVALID_PROOF")
    return subject, field("text")


VERIFIERS = {"telegram": telegram, "slack": slack}


def verify(provider, raw, headers, settings, now):
    try:
        subject, challenge = VERIFIERS[provider](raw, headers, settings, now)
        if not re.fullmatch(r"[A-Za-z0-9_-]{43}", challenge):
            raise InvalidProof("INVALID_PROOF")
        return subject, challenge
    except (TypeError, ValueError, KeyError, AttributeError, RecursionError) as exc:
        if isinstance(exc, InvalidProof):
            raise
        raise InvalidProof("INVALID_PROOF") from None
