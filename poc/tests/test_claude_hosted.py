"""Hosted SDK policy/budget cases using real SQLite, no SDK/Docker/provider execution."""
import base64
import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from threading import Barrier

import pytest
from test_workflow_chat import setup
from runtime.models import AgentRun, TaskStatus
from runtime.claude_hosted.policy import context_for_task, require_read_workspace, read_tools
from runtime.claude_hosted.broker import CredentialBroker, response_usage, validate_request
from storage.runtime_settings import OrganizationRuntimeSettings
from storage.hosted_budget import reserve, settle, task_usage
from workflows.parser import WorkflowParser
from workflows.settings import validate_settings


@pytest.fixture
def hosted(setup, monkeypatch, tmp_path):
    db, identity, _ = setup
    monkeypatch.setenv('PLATFORM_SECRETS_KEY', base64.b64encode(b'a' * 32).decode())
    credentials = OrganizationRuntimeSettings(db, 'org-chat')
    credentials.save({}, {'direct_anthropic': 'never-in-container'}, 'chat-user')
    agent = db.get_agent('chat-agent')
    agent.allowed_tools = ['Read', 'Glob', 'Grep']
    db.save_agent(agent)
    db.grant_department_mcp_access('dept-chat', 'github', allowed_tools=['clone_repository'], organization_id='org-chat')
    definition = {'name': 'Read only', 'settings': {'execution_backend': 'claude_code'}, 'steps': [{
        'key': 'inspect', 'agent_id': 'chat-agent', 'prompt_template': 'Analyze files.', 'params': {
        'workspace': {'connector_id': 'github', 'repository': 'team/allowed', 'mode': 'read'}}}]}
    db.create_workflow(id='sdk-wf', name='Read only', definition_json=json.dumps(definition),
                       organization_id='org-chat', department_id='dept-chat')
    db.create_workflow_execution(execution_id='sdk-exec', workflow_id='sdk-wf',
                                trigger_type='MANUAL', department_id='dept-chat')
    run = AgentRun(run_id='wf_task_sdk', agent_id=agent.id, prompt='Analyze files.',
                   status=TaskStatus.RUNNING, organization_id='org-chat', created_at=datetime.now())
    db.save_task_run(run)
    db.save_workflow_step_run(dict(id='sdk-step', execution_id='sdk-exec', step_key='inspect',
        agent_id=agent.id, status='RUNNING', task_run_id=run.run_id, input_data='', output_data=None,
        input_tokens=0, output_tokens=0, cost_usd=0, started_at=None, completed_at=None))
    with db._get_connection() as conn:
        conn.execute('INSERT INTO workflow_execution_tool_contexts(execution_id,context_json) VALUES(?,?)',
            ('sdk-exec', json.dumps({'initiator_id': 'chat-user', 'organization_id': 'org-chat', 'department_id': 'dept-chat'})))
        conn.execute('INSERT INTO workflow_repo_workspaces(task_id,execution_id,workspace_json) VALUES(?,?,?)',
            (run.run_id, 'sdk-exec', json.dumps({'state': 'ACTIVE', 'repository': 'team/allowed',
                'connector_id': 'github', 'execution_id': 'sdk-exec', 'mode': 'read', 'worktree': str(tmp_path)})))
    context = context_for_task(db, run, agent, 'claude-sonnet-4-20250514')
    return db, run, agent, context, credentials, tmp_path


def test_broker_authorizes_only_bound_capability_routes_and_grants(hosted):
    db, _, _, context, _, path = hosted
    broker = CredentialBroker(db, context, path)
    with pytest.raises(ValueError):
        broker.dispatch('/authorize', 'wrong-token', {'tool': 'Read'})
    assert broker.dispatch('/authorize', broker.token, {'tool': 'Read'})[0] == b'{"allowed":true}'
    for route in ('https://example.test/v1/messages', '/v1/models', '/v1/messages?url=evil'):
        with pytest.raises(ValueError):
            broker.dispatch(route, broker.token, {})
    with pytest.raises(ValueError):
        broker.dispatch('/authorize', broker.token, {'tool': 'Bash'})


def test_revocation_cancellation_and_user_demotion_fail_live_policy(hosted):
    db, run, agent, context, credentials, _ = hosted
    context.authorize(db)
    credentials.revoke('direct_anthropic', 'chat-user')
    with pytest.raises(ValueError, match='revoked'):
        context.authorize(db)
    credentials.save({}, {'direct_anthropic': 'replacement'}, 'chat-user')
    with pytest.raises(ValueError, match='replaced'):
        context.authorize(db)


def test_current_user_and_tool_grants_are_rechecked(hosted):
    db, run, agent, context, _, _ = hosted
    agent.allowed_tools = ['Read']
    db.save_agent(agent)
    with pytest.raises(ValueError, match='grants'):
        context.authorize(db)
    agent.allowed_tools = ['Read', 'Glob', 'Grep']
    db.save_agent(agent)
    db.update_user('chat-user', status='INACTIVE')
    with pytest.raises(ValueError):
        context.authorize(db)


def test_task_cancellation_denies_the_broker(hosted):
    db, run, _, context, _, path = hosted
    run.status = TaskStatus.CANCELLED
    db.save_task_run(run)
    broker = CredentialBroker(db, context, path)
    with pytest.raises(ValueError):
        broker.dispatch('/authorize', broker.token, {'tool': 'Read'})


def test_model_and_multimodal_or_external_tools_are_rejected_before_dispatch(hosted):
    _, _, _, context, _, _ = hosted
    body = {'model': context.model, 'max_tokens': 100, 'messages': [{'role': 'user', 'content': 'Inspect.'}]}
    assert validate_request(body, context) == body
    for patch in ({'model': 'other'}, {'max_tokens': 999999}, {'mcp_servers': []},
                  {'tools': [{'name': 'Bash'}]}, {'messages': [{'content': [{'type': 'image'}]}]}):
        with pytest.raises(ValueError):
            validate_request({**body, **patch}, context)


def test_atomic_budget_reservation_unknown_outcomes_and_no_double_booking(hosted):
    db, run, _, context, _, _ = hosted
    db.update_department('dept-chat', monthly_budget_usd=1)
    barrier = Barrier(2)
    def attempt():
        barrier.wait()
        try:
            return reserve(db, context, 0.6, {'source': 'CONFIGURED_ESTIMATE'})
        except ValueError:
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: attempt(), range(2)))
    identities = [identity for identity in results if identity]
    assert len(identities) == 1
    assert db.get_department_monthly_spend('dept-chat') == 0
    assert db.check_department_budget('dept-chat')['reserved_usd'] == pytest.approx(0.6)
    settle(db, identities[0], 0.2, {'input_tokens': 10, 'output_tokens': 10})
    assert db.get_department_monthly_spend('dept-chat') == pytest.approx(0.2)
    db.update_workflow_execution('sdk-exec', total_cost_usd=0.2)
    assert db.get_department_monthly_spend('dept-chat') == pytest.approx(0.2)
    unknown = reserve(db, context, 0.3, {})
    settle(db, unknown)
    assert db.get_department_monthly_spend('dept-chat') == pytest.approx(0.2)
    assert db.check_department_budget('dept-chat')['reserved_usd'] == pytest.approx(0.3)
    assert not db.check_department_budget('dept-chat', requested_cost=0.6)['allowed']
    usage = task_usage(db, run.run_id)
    assert usage['uncertain'] and usage['reserved_usd'] == pytest.approx(0.3)
    assert usage['cost_usd'] == pytest.approx(0.2)


def test_stream_usage_requires_terminal_event_and_complete_counts():
    def wire(events):
        return ''.join('data: ' + json.dumps(event) + '\n\n' for event in events).encode()
    events = [{'type': 'message_start', 'message': {'usage': {'input_tokens': 100, 'output_tokens': 0}}},
              {'type': 'message_delta', 'usage': {'output_tokens': 25}}, {'type': 'message_stop'}]
    assert response_usage(wire(events), True)['output_tokens'] == 25
    assert response_usage(wire(events[:-1]), True) is None
    assert response_usage(wire([*events, {'type': 'error'}]), True) is None
    assert response_usage(b'{"usage":{"input_tokens":1}}', False) is None


def test_private_unix_http_transport_checks_real_authorization(hosted):
    from runtime.claude_hosted.relay import UnixConnection
    db, _, _, context, _, path = hosted
    import tempfile
    with tempfile.TemporaryDirectory(prefix='sdk_test_', dir='/tmp') as directory, CredentialBroker(db, context, Path(directory)) as broker:
        class LocalUnixConnection(UnixConnection):
            def connect(self):
                import socket
                self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                self.sock.settimeout(5)
                self.sock.connect(broker.path)
        connection = LocalUnixConnection('broker')
        try:
            connection.request('POST', '/authorize', json.dumps({'tool': 'Read'}),
                headers={'x-api-key': broker.token, 'Content-Type': 'application/json'})
            response = connection.getresponse()
            assert response.status == 200 and json.loads(response.read())['allowed']
        finally:
            connection.close()
