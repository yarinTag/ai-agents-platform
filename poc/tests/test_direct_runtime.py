"""Direct runtime boundaries using real SQLite, files and local tool inventories.

These cases make no paid model calls and must be run with --noconftest.
"""
import asyncio
import os
from argparse import Namespace
from contextlib import contextmanager

import pytest
from config import AgentConfig
from persistence import DatabaseManager
from runtime.command_builder import RuntimeCommandBuilder
from runtime.direct_sessions import DirectSession
from runtime.direct_tools import DirectTools
from runtime.services import RuntimeServices


@contextmanager
def environment(**values):
    previous = {key: os.environ.get(key) for key in values}
    try:
        for key, value in values.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = str(value)
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def test_api_session_survives_reload_and_refuses_other_tenant(tmp_path):
    with environment(PLATFORM_API_SESSION_DIR=tmp_path, PLATFORM_API_SESSION_SCOPE='org-a:agent'):
        session = DirectSession('direct_openai', 'configured-model')
        session.messages.append({'role': 'user', 'content': 'Remember this task.'})
        session.save()
        assert session.path(session.id).stat().st_mode & 0o077 == 0
        loaded = DirectSession('direct_openai', 'configured-model', session.id)
        assert loaded.messages == session.messages
        fork = DirectSession('direct_openai', 'configured-model', session.id, fork=True)
        assert fork.id != session.id and fork.messages == session.messages
        with pytest.raises(ValueError):
            DirectSession('direct_nvidia', 'configured-model', session.id)
        with pytest.raises(ValueError):
            DirectSession('direct_openai', 'different-model', session.id)
        with environment(PLATFORM_API_SESSION_SCOPE='org-b:agent'):
            with pytest.raises(FileNotFoundError):
                DirectSession('direct_openai', 'configured-model', session.id)


def test_worker_command_uses_python_and_preserves_explicit_model(tmp_path):
    db = DatabaseManager(str(tmp_path / 'runtime.db'))
    db.set_setting('runtime_provider', 'direct_nvidia')
    db.set_setting('runtime_model_direct_nvidia', 'configured/model')
    services = RuntimeServices(database=lambda: db, configuration=lambda: None,
        resolve_model=lambda value: value, skills_prompt=lambda _: '', capture_session=lambda *_: None)
    builder = RuntimeCommandBuilder(services)
    agent = AgentConfig(id='worker', name='Worker', description='Worker', system_prompt='Work.', model='default')
    with environment(PLATFORM_RUNTIME_PROVIDER=None):
        command = builder._build_claude_command(agent, None, 'Do work.', playground=True)
        assert command[1:3] == ['-m', 'runtime.direct_worker']
        assert command[command.index('--model') + 1] == 'configured/model'
        assert command[command.index('--tools') + 1] == ''
        with pytest.raises(ValueError, match='different execution method'):
            builder._build_claude_command(agent, None, 'Resume.', session_id='cli-session-id')
        agent.model = 'nvidia_nim/explicit/model'
        command = builder._build_claude_command(agent, None, 'Do work.', playground=True)
        assert command[command.index('--model') + 1] == 'explicit/model'


def test_local_tools_enforce_inventory_and_workspace(tmp_path):
    outside = tmp_path / 'outside.txt'
    outside.write_text('private')
    workspace = tmp_path / 'workspace'
    workspace.mkdir()
    (workspace / 'escape').symlink_to(outside)
    args = Namespace(add_dir=str(workspace), mcp_config=None, restricted=False,
        tools=None, allowedTools='Read,Write', dangerously_skip_permissions=False)

    async def check():
        async with DirectTools(args) as tools:
            await tools.call('Write', {'file_path': 'result.txt', 'content': 'real output'})
            assert await tools.call('Read', {'file_path': 'result.txt'}) == 'real output'
            for path in ('../outside.txt', 'escape', str(outside)):
                with pytest.raises(ValueError, match='workspace'):
                    await tools.call('Read', {'file_path': path})
            with pytest.raises(ValueError, match='inventory'):
                await tools.call('Bash', {'command': 'echo unauthorized'})
        args.tools = ''
        async with DirectTools(args) as tools:
            assert tools.inventory == []

    asyncio.run(check())
