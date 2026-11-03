"""Optional Anthropic transport state; the local transcript remains authoritative."""
import copy
import hashlib
import json
import os
import time

BETA = 'message-threads-2026-08-12'
SETTING = 'runtime_message_threads_enabled'
RECOVERABLE = {'thread_not_found', 'thread_already_continued', 'thread_continue_in_flight'}


def enabled():
    from persistence import DatabaseManager
    from storage.runtime_settings import OrganizationRuntimeSettings
    database = os.environ.get('PLATFORM_PROVIDER_DB')
    organization = os.environ.get('PLATFORM_PROVIDER_ORGANIZATION')
    if not database or not organization:
        return False
    return OrganizationRuntimeSettings(DatabaseManager(database), organization).get_setting(SETTING) == 'true'


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=False).encode()).hexdigest()


def prepare(body, session):
    """Returns a private wire copy and safe event. Never mutate durable messages."""
    state = session.thread_state
    fingerprint = digest({key: value for key, value in body.items()
                          if key not in ('messages', 'max_tokens', 'stream')})
    binding = digest([os.getenv('PLATFORM_PROVIDER_ORGANIZATION'),
                      os.getenv('PLATFORM_PROVIDER_VERSION')])
    count = state.get('message_count', 0)
    same_config = state.get('fingerprint') == fingerprint and state.get('binding') == binding
    valid = (same_config and not state.get('pending') and state.get('previous_message_id')
             and 0 < count <= len(body['messages'])
             and state.get('prefix') == digest(body['messages'][:count])
             and time.time() - state.get('updated_at', 0) < 300)
    wire = copy.deepcopy(body)
    mode = 'continue' if valid else 'create'
    if valid:
        wire['messages'] = wire['messages'][count:]
        wire.pop('system', None)
        wire.pop('tools', None)
        wire['thread'] = {'type': mode, 'previous_message_id': state['previous_message_id']}
    else:
        # Changed instructions/tools invalidate earlier signed reasoning on newer models.
        if state and not same_config:
            for message in wire['messages']:
                if isinstance(message.get('content'), list):
                    message['content'] = [block for block in message['content']
                                          if block.get('type') not in ('thinking', 'redacted_thinking')]
        wire['thread'] = {'type': mode}
    session.thread_state = {'pending': True, 'fingerprint': fingerprint, 'binding': binding}
    session.save()  # An interrupted request must never reuse its predecessor cursor.
    return wire, {'type': 'conversation_transport', 'mode': mode,
                  'messages_sent': len(wire['messages']),
                  'request_bytes': len(json.dumps(wire, ensure_ascii=False).encode())}


def accept(session, data, messages):
    if not data.get('id') or data.get('stop_reason') in ('refusal', 'max_tokens', 'pause_turn'):
        session.thread_state = {}
        return
    session.thread_state.update(previous_message_id=data['id'], message_count=len(messages) + 1,
        prefix=digest(messages + [{'role': 'assistant', 'content': data.get('content') or []}]),
        updated_at=time.time(), pending=False)


def recovery(status, mode, payload):
    """Only explicit pre-inference thread errors authorize another HTTP attempt."""
    if status not in (400, 404) or not isinstance(payload, dict):
        return None, None
    error = payload.get('error')
    details = error.get('details') if isinstance(error, dict) else None
    code = details.get('error_code') if isinstance(details, dict) else None
    if not isinstance(code, str):
        return None, None
    if mode == 'continue' and code in RECOVERABLE:
        return 'replay', code
    if code == 'thread_unsupported_request':
        return 'unthreaded', code
    return None, None
