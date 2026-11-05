"""Provider-visible reasoning summaries; opaque continuation data stays private."""
import re
from .completion_validation import tool_input


def anthropic_thinking(model, max_tokens):
    """Only request thinking on known Claude families, never arbitrary models."""
    if re.search(r'claude-(?:opus|sonnet)-(?:4-[6789]|[5-9])', model) or model.startswith('claude-fable-'):
        return {'type': 'adaptive', 'display': 'summarized'}
    if re.search(r'claude-(?:opus|sonnet|haiku)-4', model) and max_tokens > 1024:
        return {'type': 'enabled', 'budget_tokens': min(2048, max_tokens - 1)}
    return None


def openai_reasoning_model(model):
    # Older o1/o3-mini reasoning models do not expose the summary API.
    return not model.startswith('o3-mini') and bool(
        re.match(r'(?:o[34](?:-|$)|gpt-[5-9](?:[.-]|$))', model))


def compatible_reasoning(message):
    visible = message.get('reasoning_content') or message.get('reasoning')
    if isinstance(visible, str) and visible.strip():
        return [visible]
    summaries = []
    for item in message.get('reasoning_details') or []:
        if not isinstance(item, dict):
            continue
        value = item.get('summary') if item.get('type') == 'reasoning.summary' else (
            item.get('text') if item.get('type') == 'reasoning.text' else None)
        if isinstance(value, str) and value.strip():
            summaries.append(value)
    return summaries


def responses_body(model, system, messages, tools, max_tokens):
    """Translate existing chat transcripts, retaining new Responses output verbatim."""
    history = []
    for message in messages:
        if 'response_items' in message:
            history.extend(message['response_items'])
        elif message['role'] == 'tool':
            history.append({'type': 'function_call_output', 'call_id': message['tool_call_id'],
                            'output': message['content']})
        else:
            if message.get('content'):
                history.append({'role': message['role'], 'content': message['content']})
            for call in message.get('tool_calls') or []:
                history.append({'type': 'function_call', 'call_id': call['id'],
                                'name': call['function']['name'],
                                'arguments': call['function']['arguments']})
    body = {'model': model, 'instructions': system, 'input': history,
            'store': False, 'max_output_tokens': max_tokens,
            'reasoning': {'summary': 'auto'}, 'include': ['reasoning.encrypted_content']}
    if tools:
        body['tools'] = [{'type': 'function', 'name': t['name'], 'description': t['description'],
                          'parameters': t['input_schema'], 'strict': False} for t in tools]
    return body


def responses_result(data, model):
    items = data.get('output') or []
    text = '\n'.join(block['text'] for item in items if item.get('type') == 'message'
                     for block in item.get('content', []) if block.get('type') == 'output_text')
    summaries = [block['text'] for item in items if item.get('type') == 'reasoning'
                 for block in item.get('summary', []) if block.get('type') == 'summary_text' and block.get('text')]
    calls = [{'id': item['call_id'], 'name': item['name'], 'type': 'tool_use',
              'input': tool_input(item['name'], item['arguments'])} for item in items if item.get('type') == 'function_call']
    usage = data.get('usage') or {}
    return {'text': text, 'calls': calls, 'message': {'role': 'assistant', 'response_items': items},
            'truncated': data.get('status') != 'completed', 'model': data.get('model', model),
            'input_tokens': int(usage.get('input_tokens', 0)),
            'output_tokens': int(usage.get('output_tokens', 0)), 'reasoning': summaries}


def reasoning_event(response, provider, turn):
    """Do not expose signatures, encrypted reasoning, or entire provider responses."""
    summaries = response.get('reasoning') or []
    return {'type': 'reasoning_summary', 'provider': provider, 'model': response['model'],
            'turn': turn, 'status': 'available' if summaries else 'not_returned',
            'content': '\n\n'.join(summaries)}
