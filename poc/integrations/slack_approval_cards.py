"""Slack approval actions bound to a verified installation and message receipt."""
import hashlib
import hmac
import json
import re

from .identity_proofs import InvalidProof
from .provider_http import request_json
from .telegram_approval_cards import ApprovalCallback, signed_action

APPROVE = 'platform_approval_approve'
REJECT = 'platform_approval_reject'


def parse_callback(raw_payload, team, app, secret):
    payload = json.loads(raw_payload)
    if payload.get('type') != 'block_actions':
        return None
    if (payload.get('team', {}).get('id'), payload.get('api_app_id')) != (team, app):
        raise InvalidProof('INVALID_PROOF')
    action, = payload['actions']
    choice = action.get('action_id')
    if choice not in (APPROVE, REJECT):
        return None
    container = payload['container']
    channel, message = container['channel_id'], container['message_ts']
    user = payload['user']
    sender, timestamp = user['id'], action['action_ts']
    token, _, signature = action['value'].partition(':')
    if (container.get('type') != 'message' or container.get('is_ephemeral')
            or user.get('team_id', team) != team or payload.get('channel', {}).get('id') != channel
            or not re.fullmatch(r'[CGD][A-Z0-9]{7,30}', channel)
            or not re.fullmatch(r'[UW][A-Z0-9]{2,31}', sender)
            or not all(re.fullmatch(r'[0-9]{1,16}\.[0-9]{1,9}', item) for item in (message, timestamp))
            or not re.fullmatch(r'[a-f0-9]{40}', token)
            or not re.fullmatch(r'[a-f0-9]{12}', signature)
            or not hmac.compare_digest(signature, signed_action(secret, token, choice))):
        raise InvalidProof('INVALID_APPROVAL_CALLBACK')
    callback_id = hashlib.sha256(f'{team}:{app}:{channel}:{message}:{sender}:{timestamp}:{choice}'.encode()).hexdigest()
    return ApprovalCallback(callback_id, token, choice == APPROVE, sender, channel, message, team)


def write_card(bot_token, channel, row, state, dashboard_origin, *, message_id=None, token=None, proof_secret=None):
    from .telegram_approval_cards import card_content

    text, url = card_content(row, state, dashboard_origin)
    controls = []
    if state.startswith('PENDING:') and token:
        controls.extend({'type': 'button', 'text': {'type': 'plain_text', 'text': label},
                         'action_id': identifier, 'value': f'{token}:{signed_action(proof_secret, token, identifier)}', 'style': style}
                        for label, identifier, style in (
                            ('Approve', APPROVE, 'primary'), ('Reject', REJECT, 'danger')))
    if url:
        controls.append({'type': 'button', 'text': {'type': 'plain_text', 'text': 'Details'},
                         'action_id': 'platform_approval_details', 'url': url})
    blocks = [{'type': 'section', 'text': {'type': 'plain_text', 'text': text[:3000]}}]
    if controls:
        blocks.append({'type': 'actions', 'elements': controls})
    payload = {'channel': channel, 'text': text[:3000], 'blocks': blocks}
    if message_id:
        payload['ts'] = message_id
    else:
        payload.update(unfurl_links=False, unfurl_media=False)
    method = 'chat.update' if message_id else 'chat.postMessage'
    result = request_json('slack.com', f'/api/{method}', {'Authorization': f'Bearer {bot_token}'}, payload=payload)
    ts = result.get('ts') if isinstance(result, dict) else None
    if (not ts or not re.fullmatch(r'[0-9]{1,16}\.[0-9]{1,9}', ts) or result.get('ok') is not True
            or result.get('channel') != channel or (message_id and ts != message_id)):
        raise InvalidProof('APPROVAL_DELIVERY_UNCONFIRMED')
    return ts
