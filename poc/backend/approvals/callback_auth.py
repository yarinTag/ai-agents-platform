"""Authenticity checks for public ChatOps approval callbacks. Both fail closed.

Telegram: register the webhook with setWebhook(secret_token=TELEGRAM_WEBHOOK_SECRET);
Telegram then sends it in X-Telegram-Bot-Api-Secret-Token on every update.
Slack: requests are signed with the app's signing secret (SLACK_SIGNING_SECRET).
https://core.telegram.org/bots/api#setwebhook
https://api.slack.com/authentication/verifying-requests-from-slack
"""
import hashlib
import hmac
import logging
import os
import time
from fastapi import HTTPException, Request, status

logger = logging.getLogger(__name__)
SLACK_MAX_SKEW_SECONDS = 300


def _secret(name: str) -> bytes:
    value = os.getenv(name, "").strip()
    if not value:
        logger.warning("Approval callback rejected: %s is not configured", name)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="This approval callback is not configured.")
    return value.encode()


def _reject():
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid callback signature.")


def verify_telegram_callback(request: Request) -> None:
    secret = _secret("TELEGRAM_WEBHOOK_SECRET")
    provided = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "").encode()
    if not hmac.compare_digest(provided, secret):
        _reject()


async def verify_slack_callback(request: Request) -> None:
    secret = _secret("SLACK_SIGNING_SECRET")
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")
    if not timestamp.isdigit() or abs(time.time() - int(timestamp)) > SLACK_MAX_SKEW_SECONDS:
        _reject()  # Missing or stale timestamp: blocks replay of captured requests.
    body = await request.body()  # Starlette caches it, so form parsing still works afterwards.
    expected = "v0=" + hmac.new(secret, b"v0:" + timestamp.encode() + b":" + body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature.encode(), expected.encode()):
        _reject()
