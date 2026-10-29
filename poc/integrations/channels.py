"""Single channel delivery implementation shared by MCP and workflow notifications."""

import json
import urllib.request


class ChannelDeliveryError(RuntimeError):
    """A message was not acknowledged; error text deliberately omits credentials."""


def resolve_telegram_target(configuration, requested):
    allowed = configuration.get("allowed_channels", [])
    first = allowed[0] if isinstance(allowed, list) and allowed else None
    configured = configuration.get("chat_id") or first
    aliases = {"@agents_office_alerts", "@hermesganbot", "hermesganbot", "Hermes_test"}
    if configured and (requested in aliases or requested.lower().endswith("bot")):
        return configured
    return requested


def deliver_channel_message(connector, channel_id, message):
    """Send once with a bounded timeout; return only after provider acknowledgement."""
    if connector is None:
        raise ChannelDeliveryError("Channel connector is unavailable")
    config = connector.configuration or {}
    provider = connector.provider.lower()
    headers = {"Content-Type": "application/json"}
    if provider == "telegram":
        token = config.get("bot_token")
        target = resolve_telegram_target(config, channel_id)
        if not token or not target:
            raise ChannelDeliveryError("Telegram token and chat must be configured")
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": target, "text": message}
    elif provider == "slack":
        token = config.get("bot_token")
        if not token or not channel_id:
            raise ChannelDeliveryError("Slack bot token and channel must be configured")
        url = "https://slack.com/api/chat.postMessage"
        headers["Authorization"] = f"Bearer {token}"
        payload = {"channel": channel_id, "text": message}
    else:
        raise ChannelDeliveryError("Channel provider does not support message delivery")

    request = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            result = json.loads(response.read().decode("utf-8"))
            if response.status != 200 or not result.get("ok"):
                raise ChannelDeliveryError("Channel provider rejected delivery")
    except ChannelDeliveryError:
        raise
    except Exception as error:
        raise ChannelDeliveryError("Channel delivery failed") from error
    return {"delivery": "delivered", "channel_id": channel_id}


def find_channel_connector(database, provider, organization_id=None):
    """Resolve configured channels within the caller's tenant."""
    connectors = database.list_mcp_connectors(organization_id=organization_id)
    return next((item for item in connectors if item.provider.lower() == provider.lower()), None)
