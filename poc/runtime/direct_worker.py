"""Direct HTTP agent worker emitting the shared runtime's JSON event contract.

This is launched by Python, not by Claude Code. Process isolation reuses existing
cancellation, lifecycle, persistence and subscriber handling in the parent.
"""
import argparse
import asyncio
import json
import os
from .direct_config import rates, validate_model
from .direct_http import DirectAPIError, add_tool_results, request
from .direct_sessions import DirectSession
from .direct_tools import DirectTools


def arguments():
    parser = argparse.ArgumentParser()
    for flag in ('model', 'system-prompt', 'add-dir', 'resume', 'mcp-config', 'allowedTools',
                 'tools', 'output-format', 'setting-sources', 'settings', 'permission-mode', 'json-schema'):
        parser.add_argument('--' + flag)
    parser.add_argument('-p', required=True)
    parser.add_argument('--max-tokens', type=int, default=8000)
    parser.add_argument('--max-budget-usd', type=float)
    for flag in ('fork-session', 'verbose', 'safe-mode', 'strict-mcp-config', 'no-session-persistence',
                 'disable-slash-commands', 'no-chrome', 'restricted', 'dangerously-skip-permissions', 'connector-only'):
        parser.add_argument('--' + flag, action='store_true')
    return parser.parse_args()


def emit(event):
    print(json.dumps(event, ensure_ascii=False), flush=True)


async def run(args):
    provider = os.environ['PLATFORM_RUNTIME_PROVIDER']
    model = validate_model(args.model)
    session = DirectSession(provider, model, args.resume, args.fork_session, args.no_session_persistence)
    messages = session.messages
    messages.append({'role': 'user', 'content': args.p})
    session.save()
    if not args.no_session_persistence:
        emit({'type': 'system', 'session_id': session.id})
    system = args.system_prompt or ''
    if args.json_schema:
        system += '\nReturn your final answer as JSON matching this schema: ' + args.json_schema
    pricing = rates(provider)
    if pricing is None:
        raise DirectAPIError('Configure ' + provider.upper() +
            '_INPUT_USD_PER_MILLION and _OUTPUT_USD_PER_MILLION on the server to enforce this API budget.')
    input_tokens = output_tokens = 0
    total_cost = 0.0 if pricing else None

    def result(text, **extra):
        event = {'type': 'result', 'is_error': False, 'result': text, 'model': model,
            'usage': {'input_tokens': input_tokens, 'output_tokens': output_tokens}}
        if not args.no_session_persistence:
            event['session_id'] = session.id
        if total_cost is not None:
            event['total_cost_usd'] = total_cost
        emit({**event, **extra})

    async with DirectTools(args) as tools:
        for _ in range(40):
            if tools.connector is not None:
                try:
                    tools.connector.inventory()  # Recheck authority before another model request.
                except ValueError as exc:
                    result(str(exc), is_error=True)
                    return
            if args.max_budget_usd is not None:
                # Conservative UTF-8 byte upper bound for text tokens, plus framing.
                upper = len(json.dumps([system, messages, tools.inventory], ensure_ascii=False).encode()) + 4096
                reservation = (upper * pricing[0] + args.max_tokens * pricing[1]) / 1_000_000
                if total_cost + reservation > args.max_budget_usd:
                    result('The remaining API budget is too small for another model request.', is_error=True)
                    return
            try:
                response = await asyncio.to_thread(request, provider, model, system, messages, tools.inventory, args.max_tokens)
            except DirectAPIError as exc:
                result(str(exc), is_error=True)
                return
            input_tokens += response['input_tokens']
            output_tokens += response['output_tokens']
            if pricing:
                total_cost = (input_tokens * pricing[0] + output_tokens * pricing[1]) / 1_000_000
            messages.append(response['message'])
            if response['truncated']:
                session.save()
                result('The API response was truncated or filtered. Increase the output token limit or refine the request.', is_error=True)
                return
            if not response['calls']:
                if not response['text']:
                    raise DirectAPIError('The API returned an empty response.')
                if tools.connector is not None:
                    try:
                        tools.connector.verify_completion()
                    except ValueError as exc:
                        result(str(exc), is_error=True)
                        return
                session.save()
                result(response['text'])
                return
            results = []
            question = None
            for call in response['calls']:
                # Verify authorization before interpreting a question or executing a tool.
                if call['name'] not in {t['name'] for t in tools.inventory}:
                    raise DirectAPIError('The model requested a tool outside the authorized inventory.')
                if call['name'] == 'AskUserQuestion':
                    question = call['input'].get('question') or 'Please provide the missing task information.'
                    results.append((call, 'Awaiting supervisor response in the next user message.', False))
                    continue
                if question:
                    results.append((call, 'Not executed while awaiting supervisor response.', True))
                    continue
                try:
                    output = await tools.call(call['name'], call['input'])
                    results.append((call, output, False))
                except PermissionError:
                    question = 'Permission required to execute tool: ' + call['name']
                    results.append((call, question, True))
                except (ValueError, OSError, KeyError) as exc:
                    if tools.connector is not None:
                        result(str(exc), is_error=True)
                        return
                    results.append((call, str(exc), True))
                emit({'type': 'tool_use', **call})
                if tools.connector is not None:
                    emit({'type': 'tool_result', 'tool_use_id': call['id'], 'content': output})
            add_tool_results(provider, messages, results)
            session.save()
            if question:
                result('[SUPERVISOR_REQUEST] ' + question)
                return
        result('The direct API tool-call limit was reached. Resume this session to continue.', is_error=True)


def main():
    try:
        asyncio.run(run(arguments()))
    except DirectAPIError as exc:
        emit({'type': 'result', 'is_error': True, 'result': str(exc)})
    except Exception as exc:
        # Do not expose arbitrary HTTP bodies, headers, tool arguments or keys.
        emit({'type': 'result', 'is_error': True,
            'result': f'Direct API execution failed ({type(exc).__name__}). Check provider/model configuration.'})


if __name__ == '__main__':
    main()
