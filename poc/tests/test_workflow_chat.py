"""New workflow chat policy/creation with real SQLite, JWTs and FastAPI; no model calls.

Run with --noconftest only when runtime verification is authorized.
"""
import json
from datetime import datetime, timedelta
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from config import AgentConfig
from persistence import DatabaseManager
from backend.api.workflow_chat import router
from backend.api.workflow_chat_models import ChatWorkflow
from backend.api.workflow_chat_policy import catalog, validate_candidate
from backend.dependencies import get_db_manager
from backend.security import authenticate_request, create_access_token


@pytest.fixture
def setup(tmp_path):
    db = DatabaseManager(str(tmp_path / 'chat.db'))
    db.create_organization(id='org-chat', name='Chat', slug='chat')
    db.create_department(id='dept-chat', name='Engineering', organization_id='org-chat')
    db.create_user(id='chat-user', organization_id='org-chat', email='chat@example.test', full_name='Chat User', role='ORG_ADMIN')
    db.save_agent(AgentConfig(id='chat-agent', name='Worker', description='Works', system_prompt='Work.',
        organization_id='org-chat', department_id='dept-chat'))
    for provider, config in [('github', {'allowed_repos': ['team/allowed'], 'token': 'never-return-this-secret'}),
                             ('slack', {'allowed_channels': ['C01234567'], 'bot_token': 'never-return-this-secret'})]:
        db.save_mcp_connector({'id': provider, 'name': provider, 'provider': provider, 'status': 'CONNECTED',
            'organization_id': 'org-chat', 'configuration': config})
        operation = 'get_repository_activity' if provider == 'github' else 'post_chat_message'
        db.save_mcp_tool({'id': provider + '-read', 'connector_id': provider, 'name': operation, 'description': 'Implemented tool'})
        db.save_mcp_tool({'id': provider + '-write', 'connector_id': provider, 'name': 'write', 'description': 'Write'})
        db.grant_department_mcp_access('dept-chat', provider, allowed_tools=[operation], organization_id='org-chat')
    identity = {'sub': 'chat-user', 'org_id': 'org-chat', 'role': 'ORG_ADMIN'}
    app = FastAPI()
    app.include_router(router, prefix='/api/v1/workflows', dependencies=[Depends(authenticate_request)])
    app.dependency_overrides[get_db_manager] = lambda: db
    client = TestClient(app, headers={'Authorization': 'Bearer ' + create_access_token(identity)})
    return db, identity, client


def candidate():
    return ChatWorkflow.model_validate({'name': 'Summarize issues', 'steps': [{
        'key': 'summarize', 'name': 'Summarize', 'agent_id': 'chat-agent', 'prompt_template': 'Summarize the approved repository.',
        'resources': [{'connector_id': 'github', 'repository': 'team/allowed', 'tool_name': 'get_repository_activity'}]}],
        'destination': {'connector_id': 'slack', 'channel_id': 'C01234567'}})


def seed_job(db, value, job_id='chat-ready-request'):
    now = datetime.now()
    result = {'message': 'Ready to review.', 'workflow': value.model_dump(), 'errors': [], 'ready': True}
    with db._get_connection() as conn:
        conn.execute('''INSERT INTO workflow_builder_jobs
            (id, organization_id, user_id, department_id, request_hash, request_json, status,
             result_json, provider_id, model_id, cost_source, created_at, deadline_at)
            VALUES (?, 'org-chat', 'chat-user', 'dept-chat', 'hash', '{}', 'READY', ?,
                    'direct_nvidia', 'configured-model', 'API_KEY', ?, ?)''',
            (job_id, json.dumps(result), now.isoformat(), (now + timedelta(minutes=3)).isoformat()))
        conn.commit()


def test_catalog_is_scoped_and_never_contains_tokens(setup):
    db, identity, _ = setup
    resources = catalog(db, identity, 'dept-chat')
    assert 'never-return-this-secret' not in json.dumps(resources)
    github = next(c for c in resources['connectors'] if c['id'] == 'github')
    slack = next(c for c in resources['connectors'] if c['id'] == 'slack')
    assert github['repositories'] == ['team/allowed']
    assert github['tools'] == ['get_repository_activity']
    assert slack['channels'] == ['C01234567']
    assert validate_candidate(candidate(), resources) == []


def test_unknown_repository_channel_tool_and_cycles_are_rejected(setup):
    db, identity, _ = setup
    resources = catalog(db, identity, 'dept-chat')
    value = candidate()
    value.steps[0].resources[0].repository = 'team/forbidden'
    value.steps[0].resources[0].tool_name = 'write'
    value.destination.channel_id = 'C_FORBIDDEN'
    value.steps[0].depends_on = ['summarize']
    errors = validate_candidate(value, resources)
    assert any('team/forbidden' in error for error in errors)
    assert any('C_FORBIDDEN' in error for error in errors)
    assert any('write' in error for error in errors)
    assert any('cycle' in error for error in errors)


def test_creation_is_inactive_and_idempotent_with_dedicated_runner(setup):
    db, _, client = setup
    seed_job(db, candidate())
    first = client.post('/api/v1/workflows/ai/chat/chat-ready-request/create')
    assert first.status_code == 200, first.text
    second = client.post('/api/v1/workflows/ai/chat/chat-ready-request/create')
    assert second.status_code == 200, second.text
    assert first.json()['id'] == second.json()['id']
    workflow = db.get_workflow(first.json()['id'])
    assert not workflow.is_active and not workflow.webhook_enabled
    assert db.get_agent(first.json()['runner_agent_id']).is_workflow_agent
    assert len(db.list_workflows(organization_id='org-chat')) == 1
    assert db.list_workflow_revisions(workflow.id)[0]['snapshot']['is_active'] == 0


def test_revoked_connector_blocks_previously_ready_draft(setup):
    db, _, client = setup
    seed_job(db, candidate())
    db.revoke_department_mcp_access('dept-chat', 'github')
    response = client.post('/api/v1/workflows/ai/chat/chat-ready-request/create')
    assert response.status_code == 422
    assert db.list_workflows(organization_id='org-chat') == []


def test_draft_only_instructions_cannot_become_execution_prompts(setup):
    db, identity, client = setup
    value = candidate()
    value.steps[0].prompt_template += ' This is an inactive preview; do not claim execution.'
    assert any('draft-only' in error for error in validate_candidate(value, catalog(db, identity, 'dept-chat')))
    seed_job(db, value)
    assert client.post('/api/v1/workflows/ai/chat/chat-ready-request/create').status_code == 422
    assert db.list_workflows(organization_id='org-chat') == []


def test_other_user_cannot_read_or_create_private_draft(setup):
    db, _, client = setup
    seed_job(db, candidate())
    db.create_user(id='other-user', organization_id='org-chat', email='other@example.test', full_name='Other', role='ORG_ADMIN')
    headers = {'Authorization': 'Bearer ' + create_access_token({'sub': 'other-user', 'org_id': 'org-chat', 'role': 'ORG_ADMIN'})}
    for suffix in ('', '/create'):
        response = (client.get if not suffix else client.post)(
            '/api/v1/workflows/ai/chat/chat-ready-request' + suffix, headers=headers)
        assert response.status_code == 404


def test_usage_contributes_to_department_spend(setup):
    db, _, _ = setup
    seed_job(db, candidate())
    with db._get_connection() as conn:
        conn.execute("UPDATE workflow_builder_jobs SET cost_usd=0.25 WHERE id='chat-ready-request'")
        conn.commit()
    assert db.get_department_monthly_spend('dept-chat') == pytest.approx(0.25)
