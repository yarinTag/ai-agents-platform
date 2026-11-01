"""HTTP wire formats for Anthropic Messages and OpenAI-compatible chat APIs."""
import json
import httpx
from .direct_config import configuration


class DirectAPIError(ValueError):
    pass


def request(provider, model, system, messages, tools, max_tokens):
    _, key, base = configuration(provider)
    anthropic = provider == 'direct_anthropic'
    headers = {'x-api-key': key, 'anthropic-version': '2023-06-01'} if anthropic else {'Authorization': 'Bearer ' + key}
    body = {'model': model, 'messages': messages, 'stream': False}
    if anthropic:
        body.update(system=system, max_tokens=max_tokens)
        if tools:
            body['tools'] = tools
    else:
        body['messages'] = [{'role': 'system', 'content': system}] + messages
        body['max_completion_tokens' if provider == 'direct_openai' else 'max_tokens'] = max_tokens
        if tools:
            body['tools'] = [{'type': 'function', 'function': {'name': t['name'],
                'description': t['description'], 'parameters': t['input_schema']}} for t in tools]
    try:
        # No implicit retries: retries can duplicate paid work or external actions.
        with httpx.Client(timeout=httpx.Timeout(120, connect=15), follow_redirects=False) as client:
            response = client.post(base + ('/messages' if anthropic else '/chat/completions'), headers=headers, json=body)
    except httpx.TimeoutException as exc:
        raise DirectAPIError('The API request timed out. Check the provider status or try again.') from exc
    except httpx.HTTPError as exc:
        raise DirectAPIError('Could not connect to the selected API provider.') from exc
    if response.status_code >= 300:
        reasons = {400: 'Request parameters or model capabilities are unsupported.',
            401: 'API credentials are invalid or expired.', 403: 'Access to this model is denied.',
            404: 'The model or API endpoint was not found.', 429: 'Rate limit or API quota exceeded.'}
        # Never persist a provider body which may echo credentials or request content.
        raise DirectAPIError(f'API HTTP {response.status_code}: ' + reasons.get(response.status_code, 'Provider request failed.'))
    data = response.json()
    usage = data.get('usage') or {}
    if anthropic:
        blocks = data.get('content') or []
        calls = [b for b in blocks if b.get('type') == 'tool_use']
        text = '\n'.join(b.get('text', '') for b in blocks if b.get('type') == 'text')
        message = {'role': 'assistant', 'content': blocks}
        truncated = data.get('stop_reason') == 'max_tokens'
    else:
        choice = data['choices'][0]
        raw = choice['message']
        message = {k: raw[k] for k in ('role', 'content', 'tool_calls') if k in raw}
        text = raw.get('content') or raw.get('reasoning_content') or ''
        if not message.get('content') and text:
            message['content'] = text
        calls = [{'id': c['id'], 'name': c['function']['name'],
            'input': json.loads(c['function']['arguments']), 'type': 'tool_use'} for c in raw.get('tool_calls') or []]
        truncated = choice.get('finish_reason') in ('length', 'content_filter')
    return {'text': text, 'calls': calls, 'message': message, 'truncated': truncated,
        'model': data.get('model', model),
        'input_tokens': int(usage.get('input_tokens', usage.get('prompt_tokens', 0))),
        'output_tokens': int(usage.get('output_tokens', usage.get('completion_tokens', 0)))}


def add_tool_results(provider, messages, results):
    if provider == 'direct_anthropic':
        messages.append({'role': 'user', 'content': [{'type': 'tool_result',
            'tool_use_id': call['id'], 'content': output, 'is_error': failed} for call, output, failed in results]})
    else:
        messages.extend({'role': 'tool', 'tool_call_id': call['id'], 'content': output} for call, output, _ in results)
