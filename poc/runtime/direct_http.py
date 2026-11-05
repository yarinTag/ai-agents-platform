"""HTTP wire formats for Anthropic Messages and OpenAI-compatible chat APIs."""
import json
import httpx
from .direct_config import configuration
from .completion_validation import tool_input
from .direct_reasoning import (anthropic_thinking, compatible_reasoning,
                               openai_reasoning_model, responses_body, responses_result)


class DirectAPIError(ValueError):
    pass


def request(provider, model, system, messages, tools, max_tokens, session=None, guard=None):
    _, key, base = configuration(provider)
    anthropic = provider == 'direct_anthropic'
    responses = provider == 'direct_openai' and openai_reasoning_model(model)
    headers = {'x-api-key': key, 'anthropic-version': '2023-06-01'} if anthropic else {'Authorization': 'Bearer ' + key}
    body = {'model': model, 'messages': messages, 'stream': False}
    if anthropic:
        body.update(system=system, max_tokens=max_tokens)
        thinking = anthropic_thinking(model, max_tokens)
        if thinking:
            body['thinking'] = thinking
        if tools:
            body['tools'] = tools
    else:
        body['messages'] = [{'role': 'system', 'content': system}] + messages
        body['max_completion_tokens' if provider == 'direct_openai' else 'max_tokens'] = max_tokens
        if tools:
            body['tools'] = [{'type': 'function', 'function': {'name': t['name'],
                'description': t['description'], 'parameters': t['input_schema']}} for t in tools]
    if responses:
        body = responses_body(model, system, messages, tools, max_tokens)
    elif provider == 'direct_openrouter':
        body['reasoning'] = {'enabled': True, 'exclude': False}
    endpoint = '/responses' if responses else '/messages' if anthropic else '/chat/completions'
    original_body = body
    transport = None
    threaded = False
    if anthropic and session is not None:
        from .anthropic_threads import enabled, prepare
        threaded = enabled() and not getattr(session, 'threads_unsupported', False)
        if threaded:
            headers['anthropic-beta'] = 'message-threads-2026-08-12'
            body, transport = prepare(body, session)
        else:
            session.thread_state = {}
            if getattr(session, 'threads_unsupported', False):
                transport = {'type': 'conversation_transport', 'mode': 'unthreaded',
                             'reason': 'thread_unsupported_request', 'messages_sent': len(messages),
                             'request_bytes': len(json.dumps(body, ensure_ascii=False).encode())}
    try:
        # No implicit retries: retries can duplicate paid work or external actions.
        with httpx.Client(timeout=httpx.Timeout(120, connect=15), follow_redirects=False) as client:
            if guard:
                guard()
            configuration(provider)  # Recheck revocation/rotation before every HTTP attempt.
            response = client.post(base + endpoint, headers=headers, json=body)
            if threaded and response.status_code in (400, 404):
                from .anthropic_threads import recovery, prepare, enabled
                try:
                    action, error = recovery(response.status_code, body['thread']['type'], response.json())
                except ValueError:
                    action, error = None, None
                if action == 'replay':
                    if guard:
                        guard()
                    configuration(provider)
                    if not enabled():
                        raise DirectAPIError('Message threads configuration changed. Start a new run.')
                    session.thread_state = {}
                    full = {'model': model, 'messages': messages, 'system': system,
                            'max_tokens': max_tokens, 'stream': False}
                    if tools:
                        full['tools'] = tools
                    thinking = anthropic_thinking(model, max_tokens)
                    if thinking:
                        full['thinking'] = thinking
                    body, transport = prepare(full, session)
                    transport.update(mode='replay', reason=error)
                    response = client.post(base + endpoint, headers=headers, json=body)
                elif action == 'unthreaded':
                    if guard:
                        guard()
                    configuration(provider)
                    session.thread_state = {}
                    session.threads_unsupported = True
                    session.save()
                    headers.pop('anthropic-beta', None)
                    body = original_body
                    transport = {'type': 'conversation_transport', 'mode': 'unthreaded',
                                 'reason': error, 'messages_sent': len(messages),
                                 'request_bytes': len(json.dumps(body, ensure_ascii=False).encode())}
                    threaded = False
                    response = client.post(base + endpoint, headers=headers, json=body)
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
    if responses:
        return responses_result(data, model)
    if threaded:
        from .anthropic_threads import accept
        accept(session, data, messages)
    usage = data.get('usage') or {}
    reasoning = []
    if anthropic:
        blocks = data.get('content') or []
        calls = [b for b in blocks if b.get('type') == 'tool_use']
        text = '\n'.join(b.get('text', '') for b in blocks if b.get('type') == 'text')
        reasoning = [b['thinking'] for b in blocks if b.get('type') == 'thinking' and b.get('thinking')]
        message = {'role': 'assistant', 'content': blocks}
        truncated = data.get('stop_reason') == 'max_tokens'
    else:
        choice = data['choices'][0]
        raw = choice['message']
        message = {k: raw[k] for k in ('role', 'content', 'tool_calls', 'reasoning_content', 'reasoning_details') if k in raw}
        text = raw.get('content') or ''
        reasoning = compatible_reasoning(raw)
        calls = [{'id': c['id'], 'name': c['function']['name'],
            'input': tool_input(c['function']['name'], c['function']['arguments']), 'type': 'tool_use'} for c in raw.get('tool_calls') or []]
        truncated = choice.get('finish_reason') in ('length', 'content_filter')
    return {'stop_reason': data.get('stop_reason'), 'transport': transport, 'response_id': data.get('id'), 'text': text, 'calls': calls, 'message': message, 'truncated': truncated, 'reasoning': reasoning,
        'provider_cost_usd': usage.get('cost') if provider == 'direct_openrouter' else None,
        'model': data.get('model', model),
        'input_tokens': int(usage.get('input_tokens', usage.get('prompt_tokens', 0))),
        'output_tokens': int(usage.get('output_tokens', usage.get('completion_tokens', 0)))}


def add_tool_results(provider, messages, results):
    if provider == 'direct_anthropic':
        messages.append({'role': 'user', 'content': [{'type': 'tool_result',
            'tool_use_id': call['id'], 'content': output, 'is_error': failed} for call, output, failed in results]})
    else:
        messages.extend({'role': 'tool', 'tool_call_id': call['id'], 'content': output} for call, output, _ in results)
