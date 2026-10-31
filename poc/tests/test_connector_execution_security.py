"""Real SQLite scope/audit/authorization boundaries. No live provider/model calls.

Use --noconftest only when execution verification is authorized.
"""
import asyncio
import json
import os
from argparse import Namespace
from contextlib import contextmanager
from datetime import datetime
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from config import AgentConfig
from persistence import DatabaseManager
from runtime.models import AgentRun, TaskStatus
from runtime.direct_tools import DirectTools
from runtime.connector_context import attach_connectors
from runtime.services import RuntimeServices
from runtime_adapter import ClaudeCodeRuntimeAdapter
from integrations.notification_guard import notification_target
from integrations.tool_definitions import ToolAccessError
from integrations.tool_executor import WorkflowToolExecutor
from integrations.tool_scopes import execution_context, prepare_execution_context, prepare_scope
from workflows.parser import WorkflowParser
from backend.api.mcp_discovery import router as discovery_router
from backend.dependencies import get_db_manager
from backend.security import authenticate_request, create_access_token


@contextmanager
def environment(**values):
    saved = {key: os.environ.get(key) for key in values}
    try:
        os.environ.update({key: str(value) for key, value in values.items()})
        yield
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


@pytest.fixture
def database(tmp_path):
    db = DatabaseManager(str(tmp_path / 'connector-security.db'))
    db.max_agents = 100
    db.create_organization(id='secure-org', name='Secure', slug='secure')
    db.create_organization(id='other-org', name='Other', slug='other')
    db.create_department(id='secure-dept', name='Engineering', organization_id='secure-org')
    db.create_user(id='operator', organization_id='secure-org', email='secure@example.test', full_name='Operator', role='ORG_ADMIN')
    db.save_agent(AgentConfig(id='secure-agent', name='Worker', description='Worker', system_prompt='Work.',
        organization_id='secure-org', department_id='secure-dept'))
    for identifier, provider, organization, configuration in [
        ('github-secure', 'github', 'secure-org', {'token': 'never-expose-this-token', 'allowed_repos': ['team/approved']}),
        ('telegram-secure', 'telegram', 'secure-org', {'bot_token': '12345:never-expose-this-token', 'allowed_channels': ['-1001234567890']}),
        ('github-foreign', 'github', 'other-org', {'token': 'foreign-secret', 'allowed_repos': ['other/private']})]:
        db.save_mcp_connector({'id': identifier, 'provider': provider, 'name': provider, 'organization_id': organization,
            'status': 'CONNECTED', 'configuration': configuration})
        if organization == 'secure-org':
            db.grant_department_mcp_access('secure-dept', identifier, '*', organization_id='secure-org')
    return db


def scoped_run(db, channel=False, binding=None, extra_connector=False):
    resource = {'connector_id': 'telegram-secure', 'channel_id': '-1001234567890', 'tool_name': 'send_message'} if channel else {
        'connector_id': 'github-secure', 'repository': 'team/approved', 'tool_name': 'get_repository_activity'}
    data = {'name': 'Governed workflow', 'steps': [{'key': 'work', 'name': 'Work', 'agent_id': 'secure-agent',
        'prompt_template': 'Perform the approved operation.', 'mcp_servers': [resource['connector_id']],
        'params': {'authorized_resources': [resource]}}], 'metadata': {'channel_binding': binding} if binding else {}}
    if extra_connector:
        data['steps'][0]['mcp_servers'].append('telegram-secure')
    workflow = db.create_workflow(id='secure-wf', name='Governed', definition_json=json.dumps(data),
        department_id='secure-dept', organization_id='secure-org')
    execution = db.create_workflow_execution('secure-exec', workflow.id, 'MANUAL', department_id='secure-dept')
    definition = WorkflowParser.from_dict(data)
    prepare_execution_context(db, execution, workflow, definition, {'sub': 'operator'})
    task = AgentRun(run_id='wf_task_secure', agent_id='secure-agent', project_id=None, prompt='Work.',
        status=TaskStatus.RUNNING, created_at=datetime.now(), organization_id='secure-org')
    db.save_task_run(task)
    prepare_scope(db, task.run_id, execution.id, definition.steps[0])
    return WorkflowToolExecutor(db, task.run_id), task


def test_inventory_contains_only_implemented_narrow_schemas_without_credentials(database):
    tools, _ = scoped_run(database)
    inventory = tools.inventory()
    assert len(inventory) == 1
    assert inventory[0]['input_schema']['properties']['repository']['enum'] == ['team/approved']
    assert not inventory[0]['input_schema']['additionalProperties']
    encoded = json.dumps(inventory)
    assert 'never-expose' not in encoded and 'foreign-secret' not in encoded
    with pytest.raises(ToolAccessError, match='receipt'):
        tools.verify_completion()


@pytest.mark.parametrize('arguments', [
    {'repository': 'other/private'}, {'repository': 'team/approved/../../private'},
    {'repository': 'https://attacker.test/x'}, {'repository': 'team/approved', 'days': 999},
    {'repository': 'team/approved', 'days': True}, {'repository': 'team/approved', 'token': 'injected'},
    {'repository': 'team/approved', 'connector_id': 'github-foreign'},
    {'repository': 'team/approved', 'url': 'http://127.0.0.1/internal'},
])
def test_forged_arguments_fail_before_a_network_attempt(database, arguments):
    tools, task = scoped_run(database)
    with pytest.raises(ToolAccessError):
        tools.call(next(iter(tools.entries)), arguments)
    calls = database.list_mcp_tool_calls(task_id=task.run_id)
    assert len(calls) == 1 and calls[0].id.startswith('call_denied_')
    assert calls[0].status == 'FAILED' and calls[0].arguments == {'denied': True}


def test_live_revocation_blocks_cached_inventory(database):
    tools, _ = scoped_run(database)
    database.revoke_department_mcp_access('secure-dept', 'github-secure')
    with pytest.raises(ToolAccessError, match='grant'):
        tools.call(next(iter(tools.entries)), {'repository': 'team/approved'})


def test_permission_growth_does_not_expand_a_running_scope(database):
    tools, _ = scoped_run(database)
    connector = database.get_mcp_connector('github-secure')
    connector.configuration['allowed_repos'].append('team/newly-added')
    database.save_mcp_connector(connector)
    with pytest.raises(ToolAccessError, match='outside'):
        tools.call(next(iter(tools.entries)), {'repository': 'team/newly-added'})


def test_tool_whitelist_is_checked_again_before_each_call(database):
    tools, _ = scoped_run(database)
    database.grant_department_mcp_access('secure-dept', 'github-secure', ['list_issues'], organization_id='secure-org')
    with pytest.raises(ToolAccessError, match='revoked'):
        tools.call(next(iter(tools.entries)), {'repository': 'team/approved'})


def test_agent_skip_permissions_flag_cannot_bypass_explicit_tool_restrictions(database):
    tools, _ = scoped_run(database)
    agent = database.get_agent('secure-agent')
    agent.mcp_permissions = ['github-secure.list_issues']
    agent.dangerously_skip_permissions = True
    database.save_agent(agent)
    with pytest.raises(ToolAccessError, match='agent is not allowed'):
        tools.call(next(iter(tools.entries)), {'repository': 'team/approved'})


@pytest.mark.parametrize('change', ['cancel', 'suspend', 'expire', 'move_connector'])
def test_run_and_identity_changes_invalidate_scope(database, change):
    tools, task = scoped_run(database)
    if change == 'cancel':
        task.status = TaskStatus.CANCELLED
        database.save_task_run(task)
    elif change == 'suspend':
        with database._get_connection() as conn:
            conn.execute("UPDATE users SET status='SUSPENDED' WHERE id='operator'")
    elif change == 'expire':
        with database._get_connection() as conn:
            scope = json.loads(conn.execute('SELECT scope_json FROM workflow_tool_scopes WHERE task_id=?', (task.run_id,)).fetchone()[0])
            scope['deadline_at'] = '2000-01-01T00:00:00'
            conn.execute('UPDATE workflow_tool_scopes SET scope_json=? WHERE task_id=?', (json.dumps(scope), task.run_id))
        tools = WorkflowToolExecutor(database, task.run_id)
    else:
        connector = database.get_mcp_connector('github-secure')
        connector.organization_id = 'other-org'
        database.save_mcp_connector(connector)
    with pytest.raises(ToolAccessError):
        tools.call(next(iter(tools.entries)), {'repository': 'team/approved'})


def test_ambiguous_delivery_is_not_repeated_and_message_body_is_not_audited(database):
    tools, task = scoped_run(database, channel=True)
    entry = next(iter(tools.entries.values()))
    arguments = {'channel_id': '-1001234567890', 'text': 'private message body'}
    call_id, previous = tools._claim(entry, arguments)
    assert previous is None
    assert 'private message body' not in json.dumps(database.get_mcp_tool_call(call_id).arguments)
    with pytest.raises(ToolAccessError, match='already started'):
        tools.call(entry['name'], arguments)
    with pytest.raises(ToolAccessError, match='already attempted'):
        tools.call(entry['name'], {**arguments, 'text': 'a different message'})
    assert len(database.list_mcp_tool_calls(task_id=task.run_id)) == 1


def test_direct_connector_mode_has_no_local_escape_tools(database):
    _, task = scoped_run(database)
    args = Namespace(add_dir=None, connector_only=True, restricted=False, tools=None, allowedTools=None)
    async def check():
        with environment(PLATFORM_CONNECTOR_DB=database.db_path, PLATFORM_CONNECTOR_TASK=task.run_id):
            async with DirectTools(args) as tools:
                assert tools.connector is not None
                assert not {'Bash', 'Read', 'Write', 'Edit', 'Glob', 'Grep'}.intersection(t['name'] for t in tools.inventory)
                with pytest.raises(ValueError, match='inventory'):
                    await tools.call('Bash', {'command': 'cat /etc/passwd'})
    asyncio.run(check())


def test_playground_does_not_receive_connector_context(database):
    _, task = scoped_run(database)
    services = RuntimeServices(database=lambda: database, configuration=lambda: None,
        resolve_model=lambda value: value, skills_prompt=lambda _: '', capture_session=lambda *_: None)
    runtime = ClaudeCodeRuntimeAdapter(services=services)
    environment = {'PLATFORM_CONNECTOR_DB': 'inherited', 'PLATFORM_CONNECTOR_TASK': 'inherited'}
    command = ['python', '-m', 'runtime.direct_worker']
    assert attach_connectors(runtime, task, 'direct_nvidia', command, environment, playground=True) is None
    assert environment == {} and '--connector-only' not in command


def test_production_attachment_binds_transcript_to_the_task(database):
    _, task = scoped_run(database)
    services = RuntimeServices(database=lambda: database, configuration=lambda: None,
        resolve_model=lambda value: value, skills_prompt=lambda _: '', capture_session=lambda *_: None)
    runtime = ClaudeCodeRuntimeAdapter(services=services)
    command = ['python', '-m', 'runtime.direct_worker', '--system-prompt', 'Work.']
    env = {'PLATFORM_API_SESSION_SCOPE': 'secure-org:secure-agent'}
    guard = attach_connectors(runtime, task, 'direct_nvidia', command, env)
    assert guard is not None and '--connector-only' in command
    assert command[command.index('--tools') + 1] == ''
    assert env['PLATFORM_CONNECTOR_TASK'] == task.run_id
    assert env['PLATFORM_API_SESSION_SCOPE'].endswith(':task:' + task.run_id)
    assert 'never-expose' not in json.dumps(env)


def test_notification_uses_exact_connector_and_real_channel_id(database):
    binding = {'provider': 'telegram', 'connector_id': 'telegram-secure', 'channel_id': '-1001234567890', 'notify_mode': 'ON_COMPLETE'}
    scoped_run(database, binding=binding)
    workflow = database.get_workflow('secure-wf')
    assert notification_target(database, workflow, 'secure-exec')[2] == '-1001234567890'
    connector = database.get_mcp_connector('telegram-secure')
    connector.configuration['allowed_channels'] = ['Hermes_test']
    connector.configuration['chat_id'] = 'Hermes_test'
    database.save_mcp_connector(connector)
    with pytest.raises(ToolAccessError, match='channel ID'):
        notification_target(database, workflow, 'secure-exec')


def test_telegram_discovery_cannot_use_foreign_connector_or_stale_admin_claim(database):
    app = FastAPI()
    app.include_router(discovery_router, prefix='/api/v1/mcp', dependencies=[Depends(authenticate_request)])
    app.dependency_overrides[get_db_manager] = lambda: database
    identity = {'sub': 'operator', 'org_id': 'secure-org', 'role': 'ORG_ADMIN'}
    client = TestClient(app, headers={'Authorization': 'Bearer ' + create_access_token(identity)})
    response = client.post('/api/v1/mcp/discover-resources', json={'provider': 'telegram', 'connector_id': 'github-foreign'})
    assert response.status_code == 404
    with database._get_connection() as conn:
        conn.execute("UPDATE users SET role='MEMBER' WHERE id='operator'")
    response = client.post('/api/v1/mcp/discover-resources', json={'provider': 'telegram', 'connector_id': 'telegram-secure'})
    assert response.status_code == 403


def test_optional_delivery_failure_does_not_block_the_declared_github_read(database):
    binding = {'provider': 'telegram', 'connector_id': 'telegram-secure', 'channel_id': 'Hermes_test', 'notify_mode': 'ON_COMPLETE'}
    tools, _ = scoped_run(database, binding=binding, extra_connector=True)
    assert len(tools.inventory()) == 1
    assert next(iter(tools.entries.values()))['provider'] == 'github'
    context = execution_context(database, 'secure-exec')
    assert 'channel ID' in context['notification_error']
    with pytest.raises(ToolAccessError, match='receipt'):
        tools.verify_completion()  # No actual data receipt is fabricated by skipping delivery.


def test_manual_channel_test_rejects_aliases_foreign_connectors_and_stale_admin(database):
    from backend.api.mcp_channels import router as channels_router
    app = FastAPI()
    app.include_router(channels_router, prefix='/api/v1/mcp', dependencies=[Depends(authenticate_request)])
    app.dependency_overrides[get_db_manager] = lambda: database
    identity = {'sub': 'operator', 'org_id': 'secure-org', 'role': 'ORG_ADMIN'}
    client = TestClient(app, headers={'Authorization': 'Bearer ' + create_access_token(identity)})
    payload = {'provider': 'telegram', 'connector_id': 'telegram-secure', 'channel_id': 'Hermes_test'}
    assert client.post('/api/v1/mcp/test-channel-message', json=payload).status_code == 400
    payload['connector_id'] = 'github-foreign'
    assert client.post('/api/v1/mcp/test-channel-message', json=payload).status_code == 404
    with database._get_connection() as conn:
        conn.execute("UPDATE users SET role='MEMBER' WHERE id='operator'")
    payload['connector_id'] = 'telegram-secure'
    assert client.post('/api/v1/mcp/test-channel-message', json=payload).status_code == 403
