"""Pure provider wire-contract cases; no model calls or simulated HTTP transports."""
import json

from poc.runtime.direct_reasoning import (
    anthropic_thinking, compatible_reasoning, openai_reasoning_model, reasoning_event,
    responses_body, responses_result,
)


def test_reasoning_summary_does_not_leak_opaque_continuation_or_become_answer():
    response = responses_result({'status': 'completed', 'output': [
        {'type': 'reasoning', 'encrypted_content': 'private-continuation',
         'summary': [{'type': 'summary_text', 'text': 'Checking repository evidence.'}]},
        {'type': 'message', 'role': 'assistant', 'phase': 'final_answer',
         'content': [{'type': 'output_text', 'text': 'Finished.'}]},
    ], 'usage': {'input_tokens': 10, 'output_tokens': 20}}, 'gpt-5')
    event = reasoning_event(response, 'direct_openai', 2)
    assert response['text'] == 'Finished.'
    assert event['content'] == 'Checking repository evidence.'
    assert event['turn'] == 2
    assert 'private-continuation' not in json.dumps(event)
    assert response['input_tokens'] == 10
    assert response['output_tokens'] == 20
    resumed = responses_body('gpt-5', 'system', [response['message'],
        {'role': 'user', 'content': 'Continue.'}], [], 8000)
    assert resumed['input'][0]['encrypted_content'] == 'private-continuation'
    assert resumed['input'][1]['phase'] == 'final_answer'
    assert resumed['store'] is False


def test_responses_tool_round_trip_and_legacy_transcript_conversion():
    arguments = '{"file_path":"README.md"}'
    response = responses_result({'status': 'completed', 'output': [
        {'type': 'function_call', 'call_id': 'call_1', 'name': 'Read', 'arguments': arguments},
    ]}, 'gpt-5')
    assert response['calls'][0]['input'] == {'file_path': 'README.md'}
    history = [
        {'role': 'user', 'content': 'Read this.'},
        {'role': 'assistant', 'content': None, 'tool_calls': [
            {'id': 'call_0', 'function': {'name': 'Read', 'arguments': arguments}}]},
        {'role': 'tool', 'tool_call_id': 'call_0', 'content': 'Old content'},
        response['message'],
        {'role': 'tool', 'tool_call_id': 'call_1', 'content': 'Current content'},
    ]
    body = responses_body('gpt-5', 'system', history, [], 8000)
    assert body['input'][1]['type'] == 'function_call'
    assert body['input'][2]['call_id'] == 'call_0'
    assert body['input'][3]['call_id'] == 'call_1'
    assert body['input'][4]['type'] == 'function_call_output'


def test_no_visible_summary_is_explicit_and_incomplete_is_not_success():
    response = responses_result({'status': 'incomplete', 'output': []}, 'gpt-5')
    assert response['truncated']
    assert not response['text']
    event = reasoning_event(response, 'direct_openai', 1)
    assert event['status'] == 'not_returned'
    assert event['content'] == ''


def test_thinking_configuration_is_model_specific_and_within_token_limit():
    assert anthropic_thinking('claude-sonnet-4-6', 8000)['type'] == 'adaptive'
    assert anthropic_thinking('claude-sonnet-4-5', 1500)['budget_tokens'] == 1499
    assert anthropic_thinking('unknown-model', 8000) is None
    assert anthropic_thinking('claude-haiku-4-5', 1024) is None
    assert openai_reasoning_model('gpt-5.1')
    assert openai_reasoning_model('o3')
    assert not openai_reasoning_model('o3-mini')
    assert not openai_reasoning_model('o1')
    assert not openai_reasoning_model('gpt-4o')


def test_compatible_visible_reasoning_excludes_encrypted_details_and_duplicates():
    details = [{'type': 'reasoning.summary', 'summary': 'Visible summary'},
               {'type': 'reasoning.encrypted', 'data': 'opaque-secret'}]
    assert compatible_reasoning({'reasoning_details': details}) == ['Visible summary']
    assert compatible_reasoning({'reasoning': 'Visible summary', 'reasoning_details': details}) == ['Visible summary']
    assert compatible_reasoning({'reasoning_details': [details[1]]}) == []
