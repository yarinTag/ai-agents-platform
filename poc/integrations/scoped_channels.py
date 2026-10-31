"""Strict plain-text sends for governed runtime tools; no alias guessing or redirects."""
import re
from .provider_http import request_json
from .tool_definitions import ToolAccessError, valid_channel


def send_message(connector, channel_id, text, authorize):
    provider = connector.provider.lower()
    if not valid_channel(provider, channel_id):
        raise ToolAccessError('Configure an exact Telegram chat ID/@channel username or Slack channel ID. Display names are not delivery IDs.')
    config = connector.configuration or {}
    token = config.get('bot_token')
    if not isinstance(token, str) or not token:
        raise ToolAccessError('The channel connector has no configured bot token.')
    authorize()
    if provider == 'telegram':
        if not re.fullmatch(r'[0-9]+:[A-Za-z0-9_-]+', token):
            raise ToolAccessError('Telegram bot token format is invalid.')
        result = request_json('api.telegram.org', '/bot' + token + '/sendMessage',
            payload={'chat_id': channel_id, 'text': text, 'link_preview_options': {'is_disabled': True}})
    elif provider == 'slack':
        plain_text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        result = request_json('slack.com', '/api/chat.postMessage', {'Authorization': 'Bearer ' + token},
            payload={'channel': channel_id, 'text': plain_text, 'mrkdwn': False, 'parse': 'none',
                     'unfurl_links': False, 'unfurl_media': False})
    else:
        raise ToolAccessError('Unsupported channel provider.')
    if not isinstance(result, dict) or result.get('ok') is not True:
        raise ToolAccessError('Channel provider did not acknowledge delivery. Do not retry automatically.')
    if provider == 'telegram':
        receipt = result.get('result') or {}
        message_id = receipt.get('message_id') if isinstance(receipt, dict) else None
        actual = (receipt.get('chat') or {}).get('id') if isinstance(receipt, dict) else None
        if not isinstance(message_id, int) or isinstance(message_id, bool) or actual is None:
            raise ToolAccessError('Telegram delivery receipt is incomplete; outcome is unknown. Do not resend automatically.')
        if not channel_id.startswith('@') and str(actual) != channel_id:
            raise ToolAccessError('Telegram acknowledged a different target; do not resend automatically.')
    else:
        message_id, actual = result.get('ts'), result.get('channel')
        if not isinstance(message_id, str) or not message_id or actual != channel_id:
            raise ToolAccessError('Slack delivery receipt is incomplete or has a different target; do not resend automatically.')
    return {'delivery': 'delivered', 'channel_id': channel_id, 'delivered_channel_id': str(actual),
            'provider_message_id': str(message_id)}
