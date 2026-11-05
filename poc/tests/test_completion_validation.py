"""Pure completion-contract tests, no model calls or mocked transports. Not executed."""
import json
import pytest
from runtime.direct_outcomes import final_outcome, parse_outcome, OutcomeFormatError
from runtime.completion_validation import ConnectorFinalizer, FINISH_NAME, rejection_event, tool_input


def completed():
    return {'status': 'completed', 'output': 'Repository summary.', 'blocker': None}


def response(text='', calls=None):
    return {'text': text, 'calls': calls or []}


def finish(value):
    return {'id': 'finish-1', 'name': FINISH_NAME, 'input': value}


def test_exact_envelope_and_whole_json_fence_are_valid():
    value = completed()
    assert final_outcome(value) == ('Repository summary.', None)
    assert final_outcome('```json\n' + json.dumps(value) + '\n```') == ('Repository summary.', None)
    assert final_outcome('Here is my answer: ' + json.dumps(value))[0] is None
    assert final_outcome(json.dumps(value) + '\nPlease send another message.')[0] is None


@pytest.mark.parametrize('value', [
    {'status': 'completed', 'output': 'Done'},
    {'status': 'completed', 'output': 'Done', 'blocker': False},
    {'status': 'completed', 'output': 'Done', 'blocker': 0},
    {'status': 'completed', 'output': {'text': 'Done'}, 'blocker': None},
    {'status': 'completed', 'output': '   ', 'blocker': None},
    {'status': 'completed', 'output': 'Done', 'blocker': None, 'extra': 'ignored?'},
    {'status': 'success', 'output': 'Done', 'blocker': None},
])
def test_missing_fields_coercion_and_extras_never_mean_success(value):
    assert final_outcome(value)[0] is None


def test_duplicate_status_cannot_replace_a_blocker():
    text = '{"status":"blocked","status":"completed","output":"Done","blocker":null}'
    with pytest.raises(OutcomeFormatError):
        parse_outcome(text)
    finalizer = ConnectorFinalizer()
    raw = tool_input(FINISH_NAME, text)
    assert raw == text
    assert finalizer.inspect(response(calls=[finish(raw)]))[0] != 'completed'
    assert tool_input('external_read', '{"days":7}') == {'days': 7}


def test_valid_blocker_is_terminal_without_a_formatting_pass():
    finalizer = ConnectorFinalizer()
    action, reason = finalizer.inspect(response(calls=[finish({
        'status': 'blocked', 'output': 'Cannot write a PR.', 'blocker': 'Read tools only.'})]))
    assert action == 'blocked' and reason == 'Read tools only.'
    assert not finalizer.formatting_only
    assert final_outcome({'status': 'completed', 'output': 'Done', 'blocker': ''})[0] is None


def test_one_repair_removes_all_connectors_and_can_accept_a_typed_final():
    external = {'name': 'post_chat_message_scoped', 'input_schema': {}}
    finalizer = ConnectorFinalizer()
    assert {tool['name'] for tool in finalizer.inventory([external])} == {external['name'], FINISH_NAME}
    assert finalizer.inspect(response(calls=[{'id': 'read-1', 'name': external['name'], 'input': {}}]))[0] == 'tools'
    assert finalizer.inspect(response('A markdown summary instead of the completion envelope.'))[0] == 'repair'
    assert finalizer.diagnostic['recovery_action'] == 'formatting_only'
    assert [tool['name'] for tool in finalizer.inventory([external])] == [FINISH_NAME]
    assert finalizer.inspect(response(calls=[finish(completed())])) == ('completed', 'Repository summary.')


def test_second_invalid_result_and_connector_requests_during_repair_fail():
    for value in (response('Still invalid.'), response(calls=[{'name': 'send_message', 'input': {}}])):
        finalizer = ConnectorFinalizer()
        assert finalizer.inspect(response('invalid'))[0] == 'repair'
        assert finalizer.inspect(value)[0] == 'failed'
        assert finalizer.diagnostic['attempt'] == 2
        assert finalizer.diagnostic['recovery_action'] == 'fail_closed'


def test_mixed_completion_and_external_call_is_not_dispatched_or_repaired():
    finalizer = ConnectorFinalizer()
    action, _ = finalizer.inspect(response(calls=[finish(completed()), {'name': 'send_message', 'input': {}}]))
    assert action == 'failed'
    assert finalizer.diagnostic['error_code'] == 'MIXED_FINALIZATION'
    assert finalizer.diagnostic['recovery_action'] == 'fail_closed'


def test_diagnostic_is_bounded_redacted_and_never_contains_provider_metadata(monkeypatch):
    secret = 'private-provider-value'
    monkeypatch.setenv('OPENAI_API_KEY', secret)
    raw = 'token="sensitive-value" Bearer sensitive-bearer ' + secret + ' nvapi-123456789abcdef ' + 'x' * 6000
    event = rejection_event(raw, OutcomeFormatError('INVALID_JSON', 'Malformed completion.'), 1)
    preview = event['candidate_preview']
    assert all(value not in preview for value in (secret, 'sensitive-value', 'sensitive-bearer', 'nvapi-123456789abcdef'))
    assert len(preview) <= 4000 and event['candidate_truncated']
    assert len(event['candidate_sha256']) == 64
    assert set(event) == {'type', 'status', 'error_code', 'message', 'attempt', 'candidate_preview',
                          'candidate_truncated', 'candidate_characters', 'candidate_sha256'}
