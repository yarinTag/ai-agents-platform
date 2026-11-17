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
from backend.api.workflow_chat_policy import catalog, native_definition, validate_candidate
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


def test_chat_requires_exact_tool_resource_pairs(setup):
    db, identity, _ = setup
    resources = catalog(db, identity, 'dept-chat')
    value = candidate()
    valid = value.steps[0].resources[0]
    value.steps[0].resources.append(valid.model_copy(update={'tool_name': None}))
    value.steps[0].resources.append(valid.model_copy(update={'repository': None}))
    clarifications = []
    errors = validate_candidate(value, resources, clarifications=clarifications)
    assert any('explicit tool for each resource' in error for error in errors)
    assert any('each GitHub tool with one exact repository' in error for error in errors)
    assert clarifications == [
        {'code': 'CAPABILITY_SELECTION_REQUIRED', 'step_key': value.steps[0].key,
         'resource_index': index, 'action': 'select_authorized_resource_or_request_setup'}
        for index in (1, 2)
    ]


def test_chat_compiles_checkpoint_and_keeps_tool_grants_separate(setup):
    db, identity, _ = setup
    resources = catalog(db, identity, 'dept-chat')
    value = candidate()
    write = value.steps[0]
    write.resources[0].tool_name = 'comment_pull_request'
    assert any('human approval checkpoint' in error for error in validate_candidate(value, resources))
    checkpoint = write.model_copy(update={'key': 'approval', 'resources': []})
    from backend.api.workflow_chat_models import ApprovalCheckpoint
    checkpoint.approval_checkpoint = ApprovalCheckpoint(expires_hours=2)
    value.steps.insert(0, checkpoint)
    write.depends_on = [checkpoint.key]
    assert any('exact PR write arguments' in error for error in validate_candidate(value, resources))
    from workflows.pr_write_approval import PRWriteApproval
    write.pr_write_approval = PRWriteApproval.model_validate({
        'connector_id': 'github', 'approval_step': checkpoint.key,
        'intent': {'operation': 'comment_pull_request', 'arguments': {
            'repository': 'team/allowed', 'pull_number': 7, 'head_sha': 'a' * 40, 'body': 'Reviewed.',
        }},
    })
    errors = validate_candidate(value, resources)
    assert not any('human approval checkpoint' in error for error in errors)
    assert any('comment_pull_request' in error for error in errors)
    compiled, protected = native_definition(value, resources)['steps']
    assert compiled['mcp_servers'] == []
    assert compiled['params'] == {'dag_approval': {'timeout_seconds': 7200}}
    assert protected['depends_on'] == ['approval']
    from workflows.parser import WorkflowParser
    from workflows.pr_write_approval import approval_manifest
    definition = WorkflowParser.from_dict(native_definition(value, resources))
    manifest = approval_manifest(definition, 'approval')
    assert manifest['fingerprint'] == write.pr_write_approval.fingerprint(write.key)
    assert manifest['description'].endswith('Reviewed.')
    amended = write.pr_write_approval.model_copy(deep=True)
    amended.intent.arguments.body = 'Changed content.'
    assert amended.fingerprint(write.key) != manifest['fingerprint']


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


def test_plugin_skill_is_catalogued_preserved_and_revalidated(setup, tmp_path, monkeypatch):
    from plugins.workflow_skills import skill_catalog, skill_context
    from backend.api.workflow_chat_policy import native_definition
    db, identity, _ = setup
    monkeypatch.setenv('PLATFORM_TENANT_STORAGE_ROOT', str(tmp_path / 'tenants'))
    root = tmp_path / 'tenants' / 'org-chat' / 'shared' / 'plugins'
    folder = root / 'tech-backend' / 'skills' / 'senior-architect'
    folder.mkdir(parents=True)
    source = folder / 'SKILL.md'
    source.write_text('# Senior Architect\nReview system architecture carefully.', encoding='utf-8')
    db.update_organization(id='org-chat', plugins_source_mode='local', plugins_local_path=str(root))
    resources = catalog(db, identity, 'dept-chat')
    identifier = str(source)
    assert identifier in {skill['id'] for skill in resources['skills']}
    candidate = ChatWorkflow.model_validate({'name': 'Review', 'steps': [{
        'key': 'review', 'name': 'Review', 'agent_id': 'chat-agent',
        'prompt_template': 'Review architecture.', 'skills': [identifier]}]})
    assert validate_candidate(candidate, resources) == []
    assert native_definition(candidate, resources)['skills'] == [identifier]
    assert 'skills' not in native_definition(candidate, resources)['steps'][0]
    assert 'Review system architecture carefully.' in skill_context(db, 'org-chat', [identifier])
    # Legacy relative references resolve only when unique inside the current source.
    assert 'Senior Architect' in skill_context(db, 'org-chat', ['tech-backend/skills/senior-architect/SKILL.md'])
    db.update_organization(id='org-chat', plugins_local_path='')
    assert skill_catalog(db, 'org-chat') == []
    with pytest.raises(ValueError, match='unavailable or ambiguous'):
        skill_context(db, 'org-chat', [identifier])
    assert any('skill outside' in error for error in validate_candidate(candidate, catalog(db, identity, 'dept-chat')))


def test_workflow_skill_selection_is_shared_and_legacy_assignments_are_promoted():
    from workflows.skill_inheritance import workflow_skill_ids
    from backend.api.workflow_chat_policy import native_definition
    candidate = ChatWorkflow.model_validate({'name': 'Shared skills', 'skills': ['architecture'], 'steps': [
        {'key': 'review', 'name': 'Review', 'agent_id': 'chat-agent', 'prompt_template': 'Review.',
         'skills': ['security', 'architecture']},
        {'key': 'summarize', 'name': 'Summarize', 'agent_id': 'chat-agent', 'prompt_template': 'Summarize.'}]})
    native = native_definition(candidate, {'connectors': []})
    assert native['skills'] == ['architecture', 'security']
    assert all('skills' not in step for step in native['steps'])
    assert workflow_skill_ids(native) == ['architecture', 'security']
    legacy = {'skills': [{'id': 'architecture', 'name': 'Architecture'}],
              'steps': [{'skills': ['security', 'architecture']}, {'skills': ['testing']}]}
    assert workflow_skill_ids(legacy) == ['architecture', 'security', 'testing']


def test_chat_can_plan_and_create_its_own_runner_without_office_agents(setup):
    from backend.api.workflow_chat_policy import PLANNED_RUNNER_ID
    db, identity, client = setup
    db.delete_agent('chat-agent')
    resources = catalog(db, identity, 'dept-chat')
    assert len(resources['agents']) == 1
    planned = resources['agents'][0]
    assert planned['id'] == PLANNED_RUNNER_ID and planned['provision_on_create']
    assert planned['connector_tools']['github'] == ['get_repository_activity']
    assert db.get_agent(PLANNED_RUNNER_ID) is None
    value = candidate()
    value.steps[0].agent_id = PLANNED_RUNNER_ID
    assert validate_candidate(value, resources) == []
    seed_job(db, value)
    response = client.post('/api/v1/workflows/ai/chat/chat-ready-request/create')
    assert response.status_code == 200, response.text
    saved = response.json()
    runner = db.get_agent(saved['runner_agent_id'])
    assert runner.is_workflow_agent and runner.organization_id == 'org-chat'
    assert runner.department_id == 'dept-chat'
    definition = json.loads(db.get_workflow(saved['id']).definition_json)
    assert definition['steps'][0]['agent_id'] == runner.id
    assert PLANNED_RUNNER_ID not in json.dumps(definition)
    assert not saved['is_active']


def test_planned_runner_does_not_allow_invented_ids_or_revoked_tools(setup):
    from backend.api.workflow_chat_policy import PLANNED_RUNNER_ID
    db, identity, client = setup
    value = candidate()
    value.steps[0].agent_id = 'invented-fetcher'
    assert any('not available' in error for error in validate_candidate(value, catalog(db, identity, 'dept-chat')))
    value.steps[0].agent_id = PLANNED_RUNNER_ID
    seed_job(db, value)
    db.revoke_department_mcp_access('dept-chat', 'github')
    assert client.post('/api/v1/workflows/ai/chat/chat-ready-request/create').status_code == 422
    assert db.list_workflows(organization_id='org-chat') == []


def test_manual_creation_binds_planned_runner_to_real_agent(setup):
    from backend.api.workflows_crud import router as crud_router
    db, _, client = setup
    client.app.include_router(crud_router, prefix='/api/v1/workflows', dependencies=[Depends(authenticate_request)])
    response = client.post('/api/v1/workflows', json={
        'name': 'Manual runner', 'department_id': 'dept-chat', 'webhook_enabled': False,
        'definition_json': json.dumps({'name': 'Manual runner', 'steps': [{
            'key': 'work', 'agent_id': '__workflow_runner__', 'prompt_template': 'Summarize.'}]})})
    assert response.status_code == 201, response.text
    saved = db.get_workflow(response.json()['id'])
    definition = json.loads(saved.definition_json)
    assert definition['steps'][0]['agent_id'] == definition['runner_agent_id']
    runner = db.get_agent(definition['runner_agent_id'])
    assert runner.is_workflow_agent and runner.department_id == 'dept-chat'


def test_chat_channel_trigger_binds_server_principal_without_activating(setup):
    from storage.channel_bindings import create
    from workflows.channel_trigger_rules import TriggerRule

    db, identity, client = setup
    binding = create(db, 'org-chat', 'dept-chat', 'chat-user', 'slack', 'slack',
                     'C01234567', {'trigger_workflows': True, 'send_notifications': False, 'approve_decisions': False})
    value = candidate()
    value.channel_trigger = TriggerRule(binding_id=binding['id'], enabled=True,
                                        matcher='command', pattern='/review')
    assert validate_candidate(value, catalog(db, identity, 'dept-chat')) == []
    seed_job(db, value)
    response = client.post('/api/v1/workflows/ai/chat/chat-ready-request/create')
    assert response.status_code == 200, response.text
    workflow = db.get_workflow(response.json()['id'])
    metadata = json.loads(workflow.definition_json)['metadata']
    assert metadata['channel_trigger'] == value.channel_trigger.model_dump()
    assert metadata['channel_trigger_principal'] == 'chat-user'
    assert not workflow.is_active


def test_exact_pr_write_refuses_mismatched_claim_before_preparing_tools(setup):
    from workflows.pr_write_approval import PRWriteApproval, execute_approved_write
    from integrations.tool_definitions import ToolAccessError

    db, _, _ = setup
    db.create_workflow(id='pinned-write', name='Pinned', organization_id='org-chat',
                       department_id='dept-chat', definition_json='{}')
    db.create_workflow_execution('pinned-run', 'pinned-write', 'MANUAL',
                                 department_id='dept-chat', status='RUNNING')
    config = PRWriteApproval.model_validate({
        'connector_id': 'github', 'approval_step': 'approval',
        'intent': {'operation': 'comment_pull_request', 'arguments': {
            'repository': 'team/allowed', 'pull_number': 7, 'head_sha': 'a' * 40, 'body': 'Changed.',
        }},
    })
    with db._get_connection() as conn:
        conn.execute("""INSERT INTO workflow_dag_approvals
            (id,execution_id,step_key,workflow_revision,organization_id,department_id,
             initiator_id,policy_json,checkpoint_json,status,expires_at)
            VALUES ('pinned-claim','pinned-run','approval',1,'org-chat','dept-chat','chat-user',
                    '{}',?,'CLAIMED',unixepoch()+300)""",
            (json.dumps({'approved_pr_write': {'step_key': 'summarize', 'fingerprint': '0' * 64}}),))
    with pytest.raises(ToolAccessError, match='differs from the approved action'):
        execute_approved_write(db, candidate().steps[0], config, None, 'pinned-run')
    with db._get_connection() as conn:
        assert conn.execute('SELECT count(*) FROM mcp_tool_calls').fetchone()[0] == 0
