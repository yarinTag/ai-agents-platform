"""Container-only SDK entrypoint. Real provider credentials never enter this process."""
import asyncio
import json
import os
import sys
import urllib.request
from importlib.metadata import version
from pathlib import Path

SDK_VERSION = '0.2.177'
ROOT = Path('/workspace/repo')


def emit(event):
    print(json.dumps(event, ensure_ascii=False), flush=True)


def authorize(tool, inputs):
    if tool not in ('Read', 'Glob', 'Grep'):
        raise ValueError('Tool is not permitted.')
    path = inputs.get('file_path') if tool == 'Read' else inputs.get('path', '.')
    if not isinstance(path, str) or not (ROOT / path).resolve().is_relative_to(ROOT):
        raise ValueError('Tool path must stay inside the repository.')
    request = urllib.request.Request(os.environ['ANTHROPIC_BASE_URL'] + '/authorize',
        data=json.dumps({'tool': tool}).encode(), headers={'Content-Type': 'application/json',
        'x-api-key': os.environ['ANTHROPIC_API_KEY']}, method='POST')
    with urllib.request.urlopen(request, timeout=10) as response:
        if not json.load(response).get('allowed'):
            raise ValueError('Tool authorization denied.')


async def run(config):
    if version('claude-agent-sdk') != SDK_VERSION:
        raise ValueError('Hosted SDK version does not match the audited worker contract.')
    from claude_agent_sdk import ClaudeAgentOptions, HookMatcher, query

    async def before(data, tool_id, context):
        name, inputs = data.get('tool_name'), data.get('tool_input') or {}
        try:
            await asyncio.to_thread(authorize, name, inputs)
            decision = 'allow'
        except Exception:
            decision = 'deny'
        emit({'type': 'tool_use', 'id': tool_id, 'name': name,
              'input': json.loads(json.dumps(inputs)) if len(json.dumps(inputs)) < 30000 else '[Input exceeded log limit]', 'phase': 'started' if decision == 'allow' else 'denied'})
        return {'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': decision,
                'permissionDecisionReason': 'Server-owned read-only repository policy.'}}

    async def after(data, tool_id, context):
        emit({'type': 'tool_result', 'tool_use_id': tool_id, 'content': str(data.get('tool_response', ''))[:30000]})
        return {}

    async def failed(data, tool_id, context):
        emit({'type': 'tool_result', 'tool_use_id': tool_id, 'is_error': True,
              'content': str(data.get('error', 'Tool failed.'))[:30000]})
        return {}

    options = ClaudeAgentOptions(model=config['model'], cwd=str(ROOT),
        system_prompt=config['system'], tools=config['tools'], allowed_tools=[],
        setting_sources=[], strict_mcp_config=True, mcp_servers={}, agents={}, plugins=[],
        permission_mode='default', max_turns=20, max_buffer_size=2_000_000,
        hooks={'PreToolUse': [HookMatcher(hooks=[before])],
               'PostToolUse': [HookMatcher(hooks=[after])],
               'PostToolUseFailure': [HookMatcher(hooks=[failed])]},
        env={'CLAUDE_CODE_MAX_OUTPUT_TOKENS': str(config['max_tokens']),
             'CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC': '1', 'DISABLE_AUTOUPDATER': '1',
             'CLAUDE_CODE_MAX_RETRIES': '0'},
        extra_args={'disable-slash-commands': None})
    terminal = None
    async for message in query(prompt=config['prompt'], options=options):
        kind = type(message).__name__
        if kind == 'SystemMessage' and getattr(message, 'subtype', None) == 'init':
            # Session handle is informational; resumption is deliberately unsupported.
            session = (getattr(message, 'data', None) or {}).get('session_id')
            emit({'type': 'system', 'subtype': 'hosted_session_started',
                  'session_id': 'sdk_' + str(session) if session else None})
        elif kind == 'AssistantMessage':
            for block in message.content:
                if type(block).__name__ == 'TextBlock':
                    emit({'type': 'assistant', 'message': {'content': [{'type': 'text', 'text': block.text}]}})
                # Thinking blocks and signatures are deliberately not exported.
        elif kind == 'ResultMessage':
            terminal = message
    if terminal is None:
        raise ValueError('SDK returned no terminal result.')
    failed = (terminal.subtype != 'success' or terminal.is_error or
              getattr(terminal, 'terminal_reason', None) not in (None, 'completed') or
              getattr(terminal, 'stop_reason', None) == 'refusal' or
              bool(getattr(terminal, 'permission_denials', None)))
    emit({'type': 'result', 'is_error': failed,
          'result': 'Hosted SDK task failed, was denied, or reached a limit.' if failed else str(terminal.result or '')})


def main():
    try:
        raw = sys.stdin.buffer.read(200_001)
        if len(raw) > 200_000:
            raise ValueError('Hosted input is too large.')
        asyncio.run(run(json.loads(raw)))
    except Exception:
        emit({'type': 'result', 'is_error': True,
              'result': 'Claude Agent SDK failed. Check the pinned image, broker policy and model configuration.'})
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
