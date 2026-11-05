"""Pure wire/state contracts and real filesystem leases. Never call a provider."""
import json
import pytest
from runtime.anthropic_threads import prepare, accept, recovery
from runtime.direct_sessions import DirectSession, session_lease


@pytest.fixture
def session(tmp_path, monkeypatch):
    monkeypatch.setenv('PLATFORM_API_SESSION_DIR', str(tmp_path))
    monkeypatch.setenv('PLATFORM_API_SESSION_SCOPE', 'organization:agent')
    monkeypatch.setenv('PLATFORM_PROVIDER_ORGANIZATION', 'organization')
    monkeypatch.setenv('PLATFORM_PROVIDER_VERSION', '1')
    return DirectSession('direct_anthropic', 'model')


def body(messages):
    return {'model': 'model', 'system': 'instructions', 'tools': [{'name': 'read'}],
            'messages': messages, 'max_tokens': 100, 'stream': False}


def answered(session):
    messages = [{'role': 'user', 'content': 'hello'}]
    prepare(body(messages), session)
    response = {'id': 'msg_one', 'stop_reason': 'end_turn',
                'content': [{'type': 'text', 'text': 'hello back'}]}
    accept(session, response, messages)
    messages.append({'role': 'assistant', 'content': response['content']})
    session.messages = messages
    session.save()
    return messages


def test_create_then_continue_sends_only_new_messages(session):
    messages = answered(session)
    messages.append({'role': 'user', 'content': 'next'})
    wire, event = prepare(body(messages), session)
    assert wire['thread'] == {'type': 'continue', 'previous_message_id': 'msg_one'}
    assert wire['messages'] == [messages[-1]]
    assert 'system' not in wire and 'tools' not in wire
    assert event['messages_sent'] == 1
    assert session.thread_state['pending']


def test_pending_attempt_cannot_reuse_cursor_after_restart(session):
    answered(session)
    session.messages.append({'role': 'user', 'content': 'next'})
    prepare(body(session.messages), session)
    resumed = DirectSession(session.provider, session.model, session.id)
    wire, _ = prepare(body(resumed.messages), resumed)
    assert wire['thread'] == {'type': 'create'}


def test_resume_continues_but_fork_starts_independent_thread(session):
    answered(session)
    resumed = DirectSession(session.provider, session.model, session.id)
    fork = DirectSession(session.provider, session.model, session.id, fork=True)
    assert resumed.thread_state['previous_message_id'] == 'msg_one'
    assert fork.thread_state == {} and fork.id != session.id


def test_format_repair_removes_old_tools_and_reasoning_from_wire_only(session):
    messages = answered(session)
    messages[1]['content'].append({'type': 'thinking', 'thinking': 'private', 'signature': 'opaque'})
    changed = body(messages)
    changed['tools'] = [{'name': 'platform_workflow_finish'}]
    wire, _ = prepare(changed, session)
    assert wire['thread']['type'] == 'create'
    assert all(b['type'] != 'thinking' for b in wire['messages'][1]['content'])
    assert messages[1]['content'][-1]['type'] == 'thinking'


def test_rotation_and_expiration_restart(session, monkeypatch):
    messages = answered(session)
    monkeypatch.setenv('PLATFORM_PROVIDER_VERSION', '2')
    assert prepare(body(messages), session)[0]['thread']['type'] == 'create'
    answered(session)
    session.thread_state['updated_at'] = 0
    assert prepare(body(session.messages), session)[0]['thread']['type'] == 'create'


def test_refusal_or_truncation_discards_cursor(session):
    messages = answered(session)
    for reason in ('refusal', 'max_tokens', 'pause_turn'):
        accept(session, {'id': 'msg_bad', 'stop_reason': reason}, messages)
        assert session.thread_state == {}


def test_real_session_lease_rejects_concurrent_resume(session):
    with session_lease(session.id):
        with pytest.raises(ValueError, match='already running'):
            with session_lease(session.id):
                pass


def test_legacy_record_and_private_state_have_no_api_key(session):
    answered(session)
    record = json.loads(session.path(session.id).read_text())
    assert 'api_key' not in json.dumps(record['thread_state'])
    record.pop('thread_state')
    session.path(session.id).write_text(json.dumps(record))
    assert DirectSession(session.provider, session.model, session.id).thread_state == {}


def test_only_known_pre_inference_errors_allow_recovery():
    def payload(code):
        return {'error': {'details': {'error_code': code}}}
    for code in ('thread_not_found', 'thread_already_continued', 'thread_continue_in_flight'):
        assert recovery(404 if code == 'thread_not_found' else 400, 'continue', payload(code)) == ('replay', code)
        assert recovery(400, 'create', payload(code)) == (None, None)
    assert recovery(400, 'create', payload('thread_unsupported_request'))[0] == 'unthreaded'
    for status in (401, 403, 429, 500):
        assert recovery(status, 'continue', payload('thread_not_found')) == (None, None)
    for bad in ({'error': 'bad'}, [], {'error': {'details': {'error_code': []}}}, payload('model_not_found')):
        assert recovery(404, 'continue', bad) == (None, None)
