"""Bounded HTTPS to fixed vendor hosts. No redirects, proxies or model-supplied URLs."""
import http.client
import json
import ssl
from urllib.parse import urlencode
from .tool_definitions import ToolAccessError

_HOSTS = {'api.github.com', 'api.telegram.org', 'slack.com'}


def telegram_rejection(raw, status):
    """Map known provider reasons to fixed text; never reflect response content."""
    try:
        result = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        return None
    if not isinstance(result, dict) or result.get('ok') is not False:
        return None
    description = result.get('description')
    reasons = {
        "Forbidden: bots can't send messages to bots": 'The saved destination is another bot. Choose your personal chat ID or the intended group/channel ID; the sending bot username is not a recipient.',
        "Forbidden: bot can't initiate conversation with a user": 'This recipient has not started the configured bot. Open the sending bot and press Start from the receiving account.',
        'Forbidden: user is deactivated': 'The receiving user account is deactivated. Explicitly select an active receiving chat.',
        'Bad Request: chat not found': 'Chat not found. Start the configured bot in your private chat, or add it to the intended group/channel. Select that chat from Find chats; a personal ID does not identify a channel.',
        'Bad Request: not enough rights to send text messages to the chat': 'The bot lacks permission to post in this chat. Give it permission to send messages.',
        'Bad Request: not enough rights to send text messages to the channel': 'The bot lacks permission to post in this channel. Add it as an administrator with permission to post messages.',
        'Bad Request: CHAT_WRITE_FORBIDDEN': 'The bot cannot write to this destination. Check its channel membership and posting permissions.',
        'Forbidden: bot was blocked by the user': 'The recipient blocked this bot. Unblock the configured bot and press Start.',
        'Forbidden: bot was kicked from the supergroup chat': 'The bot was removed from the group. Add the configured bot again.',
        'Forbidden: bot is not a member of the channel chat': 'The bot is not a member of this channel. Add the configured bot with posting permissions.',
        'Bad Request: group chat was upgraded to a supergroup chat': 'This group migrated to a supergroup. Discover and explicitly save its new chat ID.',
        'Unauthorized': 'The bot token was rejected. Update the configured bot token.',
        'Not Found': 'The bot endpoint was not found. Check the configured bot token.',
        'Bad Request: message text is empty': 'The message is empty. Enter text before sending.',
    }
    hint = reasons.get(description) if isinstance(description, str) else None
    if not hint and status == 429:
        hint = 'Telegram rate limited this bot. Wait before explicitly testing again.'
    if not hint:
        return None
    return f'Telegram rejected the request (HTTP {status}). {hint} No automatic retry was made.'


def request_json(host, path, headers=None, params=None, payload=None, accepted=(200,), method=None):
    if host not in _HOSTS or not path.startswith('/'):
        raise ToolAccessError('Unsupported integration endpoint.')
    if params:
        path += '?' + urlencode(params)
    connection = http.client.HTTPSConnection(host, timeout=10, context=ssl.create_default_context())
    try:
        body = json.dumps(payload, ensure_ascii=False).encode() if payload is not None else None
        verb = method or ('POST' if body is not None else 'GET')
        if verb not in ('GET', 'POST', 'PUT') or (verb == 'PUT' and host != 'api.github.com'):
            raise ToolAccessError('Unsupported integration method.')
        connection.request(verb, path, body=body,
            headers={'Accept': 'application/json', 'Content-Type': 'application/json; charset=utf-8',
                     'User-Agent': 'AI-Agents-Platform', **(headers or {})})
        response = connection.getresponse()
        raw = response.read(2_000_001)
        if len(raw) > 2_000_000:
            raise ToolAccessError('Integration response exceeded the size limit.')
        if response.status not in accepted:
            reason = telegram_rejection(raw, response.status) if host == 'api.telegram.org' else None
            raise ToolAccessError(reason or f'Integration returned HTTP {response.status}; check credentials, access and rate limits. No automatic retry was made.')
        return json.loads(raw)
    except ToolAccessError:
        raise
    except Exception as exc:
        # Do not expose token-bearing Telegram paths, headers or response bodies.
        raise ToolAccessError('Integration request failed or timed out. Delivery may be unknown; do not retry automatically.') from exc
    finally:
        connection.close()
