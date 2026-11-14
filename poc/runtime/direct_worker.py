"""Direct HTTP agent worker emitting the shared runtime's JSON event contract.

This is launched by Python, not by Claude Code. Process isolation reuses existing
cancellation, lifecycle, persistence and subscriber handling in the parent.
"""
import argparse
import asyncio
import json
import os
from .direct_config import validate_model
from .direct_pricing import call_cost, pricing, totals
from .direct_http import DirectAPIError, add_tool_results, request
from .direct_sessions import DirectSession, session_lease
from .direct_reasoning import reasoning_event
from .direct_tools import DirectTools
from .direct_outcomes import OUTCOME_PROMPT
from .completion_validation import ConnectorFinalizer, FINISH_PROMPT, REPAIR_PROMPT


def arguments():
    parser = argparse.ArgumentParser()
    for flag in ('model', 'system-prompt', 'add-dir', 'resume', 'mcp-config', 'allowedTools',
                 'tools', 'output-format', 'setting-sources', 'settings', 'permission-mode', 'json-schema',
                 'sandbox-container', 'sandbox-redactions'):
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


async def run_session(args, session):
    provider = os.environ['PLATFORM_RUNTIME_PROVIDER']
    model = validate_model(args.model)
    messages = session.messages
    messages.append({'role': 'user', 'content': args.p})
    session.save()
    if not args.no_session_persistence:
        emit({'type': 'system', 'session_id': session.id})
    system = args.system_prompt or ''
    if args.json_schema:
        system += '\nReturn your final answer as JSON matching this schema: ' + args.json_schema
    price_policy = pricing(provider, model)
    token_rates = price_policy['rates']
    if token_rates is None and args.max_budget_usd is not None:
        raise DirectAPIError('Configure ' + provider.upper() +
            '_INPUT_USD_PER_MILLION and _OUTPUT_USD_PER_MILLION on the server to enforce this API budget.')
    input_tokens = output_tokens = 0
    run_calls = []

    def result(text, **extra):
        event = {'type': 'result', 'is_error': False, 'result': text, 'model': model,
            'usage': {'input_tokens': input_tokens, 'output_tokens': output_tokens},
            'cost_summary': totals(run_calls), 'session_cost_summary': totals(
                session.usage_calls, prior_unknown=session.prior_usage_unknown),
            'pricing_status': totals(run_calls)['status']}
        if not args.no_session_persistence:
            event['session_id'] = session.id
        if run_calls and totals(run_calls)['cost_usd'] is not None:
            event['total_cost_usd'] = totals(run_calls)['cost_usd']
        emit({**event, **extra})

    async with DirectTools(args) as tools:
        pull_numbers = tools.connector.scope.get('pull_numbers') if tools.connector is not None else None
        finalizer = ConnectorFinalizer(pull_numbers) if tools.connector is not None else None
        if finalizer:
            system += OUTCOME_PROMPT + FINISH_PROMPT
            if pull_numbers is not None:
                system += ' For PR review, include eligible_pull_numbers in the completion tool arguments and put plain-text findings in output.'
        for turn in range(1, 41):
            if tools.connector is not None:
                try:
                    tools.connector.inventory()  # Recheck authority before another model request.
                except ValueError as exc:
                    result(str(exc), is_error=True)
                    return
            inventory = finalizer.inventory(tools.inventory) if finalizer else tools.inventory
            if args.max_budget_usd is not None:
                # Conservative UTF-8 byte upper bound for text tokens, plus framing.
                upper = len(json.dumps([system, messages, inventory], ensure_ascii=False).encode()) + 4096
                reservation = (upper * token_rates[0] + args.max_tokens * token_rates[1]) / 1_000_000
                if totals(run_calls)['known_cost_usd'] + reservation > args.max_budget_usd:
                    result('The remaining API budget is too small for another model request.', is_error=True)
                    return
            def guard():
                if tools.connector is not None:
                    tools.connector.inventory()

            try:
                response = await asyncio.to_thread(request, provider, model, system, messages,
                                                  inventory, args.max_tokens, session, guard)
            except DirectAPIError as exc:
                result(str(exc), is_error=True)
                return
            if response.get('transport'):
                emit(response['transport'])
            input_tokens += response['input_tokens']
            output_tokens += response['output_tokens']
            usage_call = call_cost(response, price_policy)
            run_calls.append(usage_call)
            session.usage_calls.append(usage_call)
            emit({'type': 'usage', 'provider': provider, 'model': model, 'turn': turn,
                  **usage_call, 'cost_summary': totals(run_calls), 'session_cost_summary': totals(
                      session.usage_calls, prior_unknown=session.prior_usage_unknown)})
            messages.append(response['message'])
            event = reasoning_event(response, provider, turn)
            if tools.sandbox is not None:
                event['content'] = tools.sandbox.redact(event['content'])
            emit(event)
            session.save()
            if response.get('stop_reason') in ('pause_turn', 'refusal'):
                result('The provider paused or refused this turn; automatic continuation is not supported.', is_error=True)
                return
            if response['truncated']:
                reason = response.get('stop_reason')
                if reason in ('max_tokens', 'max_output_tokens', 'length'):
                    message = f'The model reached its output limit ({args.max_tokens:,} tokens). Request a smaller deliverable or use a model with more output capacity.'
                elif reason == 'content_filter':
                    message = 'The provider filtered the model response.'
                else:
                    message = 'The provider returned an incomplete model response.'
                result(message, is_error=True)
                return
            if finalizer:
                action, output = finalizer.inspect(response)
                if finalizer.diagnostic:
                    emit(finalizer.diagnostic)
                if action != 'tools':
                    if response['calls']:
                        # Close the internal tool turn for valid future session replay.
                        # No call in a finalization response is sent to a connector.
                        add_tool_results(provider, messages, [(call,
                            'Server completion validation only; no connector action executed.',
                            action != 'completed') for call in response['calls']])
                    if action in ('failed', 'blocked'):
                        session.save()
                        result(output, is_error=True)
                        return
                    try:
                        tools.connector.verify_completion()  # Rechecks live policy and required receipts.
                    except ValueError as exc:
                        session.save()
                        result(str(exc), is_error=True)
                        return
                    if action == 'repair':
                        # One bounded model-only formatting pass. Connector tools are
                        # removed from the next request and cannot be dispatched.
                        repair = REPAIR_PROMPT
                        if pull_numbers is not None:
                            repair += ' Include the eligible_pull_numbers array from the reviewed batch.'
                        messages.append({'role': 'user', 'content': repair})
                        session.save()
                        continue
                    session.save()
                    result(output)
                    return
            if not response['calls']:
                if not response['text']:
                    raise DirectAPIError('The API returned an empty response.')
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


async def run(args):
    provider = os.environ['PLATFORM_RUNTIME_PROVIDER']
    model = validate_model(args.model)
    with session_lease(args.resume):
        session = DirectSession(provider, model, args.resume, args.fork_session, args.no_session_persistence)
        if session.id == args.resume:
            await run_session(args, session)
        elif args.no_session_persistence:
            await run_session(args, session)
        else:
            with session_lease(session.id):
                await run_session(args, session)


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
