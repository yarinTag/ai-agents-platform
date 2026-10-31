"""Read-only Telegram chat-ID discovery from the current tenant's bot updates."""
import re
from fastapi import HTTPException
from integrations.provider_http import request_json
from integrations.tool_definitions import ToolAccessError, resource_values, valid_channel


def discover_telegram(payload, request, db):
    claims = getattr(request.state, 'user', None) or {}
    user = db.get_user(claims.get('sub')) if claims else None
    if not user or user.status != 'ACTIVE' or user.role != 'ORG_ADMIN' or user.organization_id != claims.get('org_id'):
        raise HTTPException(403, 'An active organization administrator must discover bot chat IDs.')
    configuration = dict(payload.configuration or {})
    if payload.connector_id:
        connector = db.get_mcp_connector(payload.connector_id)
        if not connector or connector.organization_id != user.organization_id or connector.provider != 'telegram':
            raise HTTPException(404, 'Telegram connector not found in this organization.')
    else:
        candidates = [c for c in db.list_mcp_connectors(organization_id=user.organization_id)
                      if c.organization_id == user.organization_id and c.provider == 'telegram']
        connector = candidates[0] if len(candidates) == 1 else None
    token = configuration.get('bot_token') or payload.token
    if not isinstance(token, str) or not re.fullmatch(r'[0-9]+:[A-Za-z0-9_-]+', token):
        token = (connector.configuration or {}).get('bot_token') if connector else None
    if not isinstance(token, str) or not re.fullmatch(r'[0-9]+:[A-Za-z0-9_-]+', token):
        raise HTTPException(400, 'Select a Telegram connector or configure its valid bot token before discovering chats.')
    try:
        result = request_json('api.telegram.org', '/bot' + token + '/getUpdates',
            params={'timeout': 0, 'limit': 100})  # No offset: do not acknowledge/consume updates.
    except ToolAccessError as exc:
        raise HTTPException(502, 'Telegram chat discovery is unavailable. If the bot uses a webhook, getUpdates cannot be used; enter the exact ID or @channel username instead.') from exc
    if not isinstance(result, dict) or result.get('ok') is not True or not isinstance(result.get('result'), list):
        raise HTTPException(502, 'Telegram did not return acknowledged chat updates.')
    chats = {}
    for update in result['result']:
        if not isinstance(update, dict):
            continue
        for kind in ('message', 'channel_post', 'edited_message', 'edited_channel_post', 'my_chat_member'):
            item = update.get(kind) or {}
            chat = item.get('chat') if isinstance(item, dict) else None
            if not isinstance(chat, dict) or not isinstance(chat.get('id'), int):
                continue
            identifier = str(chat['id'])
            if valid_channel('telegram', identifier):
                chats[identifier] = {'id': identifier, 'name': str(chat.get('title') or chat.get('username') or ' '.join(str(chat.get(k) or '') for k in ('first_name', 'last_name')).strip() or identifier)[:200],
                    'description': 'Observed bot chat ID; discovery does not grant workflow access.'}
    config = connector.configuration if connector else configuration
    for identifier in resource_values(config or {}, 'channels'):
        if valid_channel('telegram', identifier) and identifier not in chats:
            chats[identifier] = {'id': identifier, 'name': str((config or {}).get('channel_labels', {}).get(identifier) or identifier)[:200], 'description': 'Configured target; not verified by recent updates.'}
    return {'provider': 'telegram', 'chats': list(chats.values()),
        'message': 'Choose the numeric ID matching your chat, then save it to the connector allowlist. '
                   'Only recent bot updates are discoverable; no message was sent and no permission was granted.'}
