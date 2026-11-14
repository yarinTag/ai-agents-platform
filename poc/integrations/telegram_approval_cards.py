"""Telegram rendering and verified callback projection for approval cards."""
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import hmac
import json
import re
from urllib.parse import quote

from .identity_proofs import InvalidProof
from .provider_http import request_json


@dataclass(frozen=True)
class ApprovalCallback:
    callback_id: str
    token: str
    approve: bool
    sender_id: str
    channel_id: str
    message_id: str
    bot_id: str


def parse_callback(update, bot_id, secret):
    callback = update["callback_query"]
    data = callback.get("data", "")
    if not isinstance(data, str) or not data.startswith("dga:"):
        return None
    match = re.fullmatch(r"dga:([ar]):([a-f0-9]{40}):([a-f0-9]{12})", data)
    message, sender = callback["message"], callback["from"]
    if (not match or not hmac.compare_digest(match[3], signed_action(secret, match[2], match[1])) or sender.get("is_bot") is not False or type(sender["id"]) is not int
            or sender["id"] <= 0 or type(message["message_id"]) is not int
            or message["message_id"] <= 0 or type(message["chat"]["id"]) is not int
            or str(message["from"]["id"]) != bot_id
            or not re.fullmatch(r"[0-9]{1,40}", callback["id"])):
        raise InvalidProof("INVALID_APPROVAL_CALLBACK")
    return ApprovalCallback(callback["id"], match[2], match[1] == "a", str(sender["id"]),
                            str(message["chat"]["id"]), str(message["message_id"]), bot_id)


def action_token(bot_token, approval_id):
    return hmac.new(bot_token.encode(), f"conduitcross:dag-card:{approval_id}".encode(), hashlib.sha256).hexdigest()[:40]


def signed_action(secret, token, action):
    return hmac.new(secret.encode(), f"{token}:{action}".encode(), hashlib.sha256).hexdigest()[:12]


def write_card(bot_token, channel, row, state, dashboard_origin, *, message_id=None, token=None, proof_secret=None):
    if not re.fullmatch(r"[0-9]+:[A-Za-z0-9_-]+", bot_token):
        raise InvalidProof("APPROVAL_DESTINATION_UNAVAILABLE")
    buttons = []
    if dashboard_origin:
        url = f"{dashboard_origin}/workflows/{quote(row['workflow_id'], safe='')}/logs?execution={quote(row['execution_id'], safe='')}"
        buttons.append([{"text": "Details", "url": url}])
    if state.startswith("PENDING:") and token:
        buttons.insert(0, [{"text": "Approve", "callback_data": f"dga:a:{token}:{signed_action(proof_secret, token, 'a')}"},
                           {"text": "Reject", "callback_data": f"dga:r:{token}:{signed_action(proof_secret, token, 'r')}"}])
    expiry = row["expires_at"]
    deadline = datetime.fromisoformat(expiry).astimezone(timezone.utc) if isinstance(expiry, str) else datetime.fromtimestamp(expiry, timezone.utc)
    expires = deadline.strftime("%Y-%m-%d %H:%M UTC")
    status = {"APPROVED": "Approved", "REJECTED": "Rejected", "TIMED_OUT": "Expired",
              "DECIDED": "Decision received · checking outcome", "FAILED": "Approval processing failed"}
    label = status.get(state, f"Waiting for approval · {state.removeprefix('PENDING:')}")
    text = f"ConduitCross · {label}\nStep: {row['step_key']}\nExpires: {expires}"
    source = json.loads(row["policy_json"]).get("summary_step") if "policy_json" in row else None
    if "report" in row:
        subjects = json.loads(row["subjects_json"])
        pins = "\n".join(f"{pr['repository']} #{pr['pull_number']} · {pr['head_sha']}\n{pr['url']}"
                         for pr in subjects)
        if pins:
            text += f"\n\nReviewed PRs:\n{pins}"
        text += f"\n\nFindings:\n{row['report'][:1000]}"
    if source:
        summary = json.loads(row["checkpoint_json"])["outputs"].get(source, "").strip()
        if summary:
            excerpt = summary[:1000] + ("…" if len(summary) > 1000 else "")
            text += f"\n\nFindings:\n{excerpt}"
    if len(text.encode("utf-16-le")) // 2 > 4096:
        raise InvalidProof("APPROVAL_REPORT_TOO_LARGE")
    payload = {"chat_id": channel, "text": text,
               "reply_markup": {"inline_keyboard": buttons}, "link_preview_options": {"is_disabled": True}}
    method = "sendMessage"
    if message_id is not None:
        payload["message_id"] = int(message_id)
        method = "editMessageText"
    # Telegram's explicit no-change response means the desired edit is already applied.
    result = request_json("api.telegram.org", f"/bot{bot_token}/{method}", payload=payload,
                          accepted=(200, 400) if message_id is not None else (200,))
    if (message_id is not None and isinstance(result, dict) and result.get("error_code") == 400
            and str(result.get("description", "")).startswith("Bad Request: message is not modified")):
        return message_id
    message = result.get("result") if isinstance(result, dict) and result.get("ok") is True else None
    if (not isinstance(message, dict) or str((message.get("chat") or {}).get("id")) != channel
            or type(message.get("message_id")) is not int or message["message_id"] <= 0
            or (message_id is not None and str(message["message_id"]) != message_id)):
        raise InvalidProof("APPROVAL_DELIVERY_UNCONFIRMED")
    return str(message["message_id"])
