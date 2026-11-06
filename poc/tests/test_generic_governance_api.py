"""AI-13 HTTP baseline: real guarded routers/SQLite, multiple providers, no agents run."""
import json
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from backend.dependencies import get_config_manager, get_db_manager
from backend.router_registry import register_routers
from backend.security.tokens import create_access_token
from config import AgentConfig, ConfigManager
from persistence import DatabaseManager

PROVIDERS = ('github', 'telegram', 'slack')
TOOLS = {'github': ['list_open_pull_requests', 'get_pull_request_review', 'get_pull_request', 'get_pull_request_diff', 'get_pull_request_checks'],
         'telegram': ['send_message'], 'slack': ['post_chat_message']}


@pytest.fixture
def baseline(tmp_path, monkeypatch):
    monkeypatch.setenv('JWT_SECRET_KEY', 'isolated-ai13-api-baseline-key-000000000000')
    monkeypatch.setenv('PLATFORM_DISABLED_CAPABILITIES', 'runtime,scheduler-worker,intelligence,notifications')
    monkeypatch.setenv('ALLOW_UNAUTHENTICATED_DEV', 'false')
    monkeypatch.setenv('PLATFORM_TENANT_STORAGE_ROOT', str(tmp_path / 'tenants'))
    monkeypatch.delenv('PLATFORM_PUBLIC_URL', raising=False)
    db = DatabaseManager(str(tmp_path / 'baseline.db'))
    for org in ('atlas', 'boreal'):
        db.create_organization(id=org, name=org, slug=org)
        for department in ('engineering', 'finance', 'operations'):
            db.create_department(id=f'{org}_{department}', name=department, organization_id=org)
            # Persisted identity subjects only. No runtime is registered or started.
            db.save_agent(AgentConfig(id=f'{org}_{department}', name=department, description='Policy subject',
                                     system_prompt='', organization_id=org, department_id=f'{org}_{department}'))
        for role in ('ORG_ADMIN', 'MANAGER', 'OPERATOR', 'MEMBER'):
            db.create_user(id=f'{org}_{role}', email=f'{role.lower()}@{org}.example.test', full_name=role,
                           organization_id=org, role=role)
            if role != 'ORG_ADMIN':
                db.add_user_to_department(f'{org}_engineering', f'{org}_{role}', role=role)
        for provider in (*PROVIDERS, 'postgres'):
            configuration = {'token': f'{org}-private-fixture-secret', 'allowed_repos': ['owner/repository']}
            if provider != 'github':
                configuration = {'bot_token': f'{org}-private-fixture-secret', 'allowed_channels': ['12345' if provider == 'telegram' else 'C12345678']}
            connector = f'{org}_{provider}'
            db.save_mcp_connector({'id': connector, 'name': provider, 'provider': provider, 'status': 'CONNECTED',
                                   'organization_id': org, 'configuration': configuration})
            db.grant_department_mcp_access(f'{org}_engineering', connector,
                                          allowed_tools=TOOLS.get(provider, ['query']), organization_id=org)
            if provider == 'postgres':
                db.save_mcp_tool({'id': org + '_query', 'connector_id': connector, 'name': 'query', 'description': 'Descriptive metadata only'})
    app = FastAPI()
    app.dependency_overrides[get_db_manager] = lambda: db
    app.dependency_overrides[get_config_manager] = lambda: ConfigManager(str(tmp_path / 'config'))
    register_routers(app)  # Real registry policy and response wrappers; no application lifespan.
    with TestClient(app) as client:
        yield db, client


def auth(role='ORG_ADMIN', org='atlas', department='engineering'):
    token = create_access_token({'sub': f'{org}_{role}', 'org_id': org, 'role': role})
    return {'Authorization': 'Bearer ' + token, 'X-Department-ID': f'{org}_{department}'}


@pytest.mark.parametrize('role', ['ORG_ADMIN', 'MANAGER', 'OPERATOR', 'MEMBER'])
@pytest.mark.parametrize('provider', PROVIDERS)
def test_connector_reads_and_secret_redaction_across_roles_and_providers(baseline, role, provider):
    _, client = baseline
    headers = auth(role)
    response = client.get(f'/api/v1/mcp/connectors/atlas_{provider}', headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()['provider'] == provider
    assert 'private-fixture-secret' not in response.text
    assert 'atla...' not in response.text
    assert client.get(f'/api/v1/mcp/connectors/boreal_{provider}', headers=headers).status_code == 404


@pytest.mark.parametrize('role', ['MANAGER', 'OPERATOR', 'MEMBER'])
def test_nonadmins_cannot_install_or_modify_connectors(baseline, role):
    db, client = baseline
    before = db.get_mcp_connector('atlas_github').name
    assert client.put('/api/v1/mcp/connectors/atlas_github', headers=auth(role), json={'name': 'Changed'}).status_code == 403
    assert client.post('/api/v1/mcp/connectors', headers=auth(role),
                       json={'provider': 'github', 'name': 'New'}).status_code == 403
    assert db.get_mcp_connector('atlas_github').name == before


def context(client, role='MEMBER'):
    response = client.get('/api/v1/workflows/ai/context', headers=auth(role),
                          params={'department_id': 'atlas_engineering'})
    assert response.status_code == 200, response.text
    return response.json()


def test_authoring_catalog_distinguishes_executable_from_descriptive_tools(baseline):
    _, client = baseline
    value = context(client)
    assert value['selection'] is None  # Real runtime capability is disabled, not replaced by a mock.
    catalog = value['catalog']
    connectors = {entry['provider']: entry for entry in catalog['connectors']}
    assert set(connectors) == {*PROVIDERS, 'postgres'}
    for provider in PROVIDERS:
        assert set(connectors[provider]['tools']) == set(TOOLS[provider])
        assert connectors[provider]['execution_supported'] is True  # Configuration-only projection.
        assert set(connectors[provider]['tool_capabilities']) == set(TOOLS[provider])
    assert connectors['postgres']['tools'] == []
    assert connectors['postgres']['execution_supported'] is False
    assert catalog['human_approval']['configured'] is False
    assert catalog['human_approval']['terminal_only'] is True
    assert 'private-fixture-secret' not in json.dumps(value)


def test_grant_changes_and_revocation_recompute_catalog_without_new_login(baseline):
    db, client = baseline
    headers = auth()
    path = '/api/v1/departments/atlas_engineering/mcp-access'
    payload = {'connector_id': 'atlas_github', 'allowed_tools': [*TOOLS['github'], 'merge_pull_request'],
               'granted_by_user_id': 'boreal_ORG_ADMIN'}
    response = client.post(path, headers=headers, json=payload)
    assert response.status_code == 201, response.text
    assert response.json()['granted_by_user_id'] == 'atlas_ORG_ADMIN'
    github = next(c for c in context(client)['catalog']['connectors'] if c['provider'] == 'github')
    assert github['server_operations'] == ['merge_pull_request']
    assert 'merge_pull_request' not in github['tools']
    assert client.delete(path + '/atlas_github', headers=headers).status_code == 200
    assert 'atlas_github' not in {c['id'] for c in context(client)['catalog']['connectors']}
    assert client.get('/api/v1/mcp/connectors/atlas_github', headers=auth('MEMBER')).status_code == 404
    assert db.get_mcp_connector('atlas_github') is not None  # Revocation does not delete the connector.


def test_wildcard_reads_do_not_offer_server_merge_authority(baseline):
    _, client = baseline
    response = client.post('/api/v1/departments/atlas_engineering/mcp-access', headers=auth(),
                           json={'connector_id': 'atlas_github', 'allowed_tools': '*'})
    assert response.status_code == 201
    github = next(c for c in context(client)['catalog']['connectors'] if c['provider'] == 'github')
    assert 'get_pull_request_review' in github['tools']
    assert github['server_operations'] == []


def test_no_grants_or_cross_department_selection_never_expands_catalog(baseline):
    _, client = baseline
    response = client.get('/api/v1/workflows/ai/context', headers=auth('ORG_ADMIN', department='finance'),
                          params={'department_id': 'atlas_finance'})
    assert response.status_code == 200 and response.json()['catalog']['connectors'] == []
    assert client.get('/api/v1/workflows/ai/context', headers=auth('MEMBER', department='finance')).status_code == 403
    assert client.get('/api/v1/workflows/ai/context', headers=auth('MEMBER'),
                      params={'department_id': 'boreal_engineering'}).status_code in (403, 404)


def test_existing_grant_does_not_make_an_unknown_operation_executable(baseline):
    _, client = baseline
    response = client.post('/api/v1/departments/atlas_engineering/mcp-access', headers=auth(),
                           json={'connector_id': 'atlas_github', 'allowed_tools': ['invented_execute_anything']})
    assert response.status_code == 201  # Legacy grant records accept names, adapter inventory remains authoritative.
    github = next(c for c in context(client)['catalog']['connectors'] if c['provider'] == 'github')
    assert github['tools'] == [] and not github['execution_supported']


def test_member_can_save_inactive_plan_but_cannot_activate_or_run_it(baseline):
    db, client = baseline
    payload = {'name': 'API-only plan', 'department_id': 'atlas_engineering', 'webhook_enabled': False,
               'definition_json': json.dumps({'steps': [{'key': 'read', 'agent_id': 'atlas_engineering', 'prompt_template': 'Read.'}]})}
    response = client.post('/api/v1/workflows/', headers=auth('MEMBER'), json=payload)
    assert response.status_code == 201, response.text
    identifier = response.json()['id']
    assert not db.get_workflow(identifier).is_active
    assert client.put(f'/api/v1/workflows/{identifier}', headers=auth('MEMBER'), json={'is_active': True}).status_code in (403, 404)
    assert client.post(f'/api/v1/workflows/{identifier}/execute', headers=auth('MEMBER'), json={}).status_code in (403, 404)
    with db._get_connection() as conn:
        assert conn.execute('SELECT COUNT(*) FROM workflow_executions').fetchone()[0] == 0
        assert conn.execute('SELECT COUNT(*) FROM task_runs').fetchone()[0] == 0
        assert conn.execute('SELECT COUNT(*) FROM mcp_tool_calls').fetchone()[0] == 0


@pytest.mark.parametrize('provider', ['telegram', 'slack'])
def test_legacy_channel_callbacks_remain_disabled(baseline, provider):
    db, client = baseline
    response = client.post(f'/api/v1/approvals/{provider}-callback', json={'action': 'approve'})
    assert response.status_code == 403, response.text
    with db._get_connection() as conn:
        assert conn.execute('SELECT COUNT(*) FROM task_runs').fetchone()[0] == 0


@pytest.mark.parametrize('status,assigned,expected', [('ACTIVE', False, 403), ('DISABLED', True, 401)])
def test_unassigned_and_disabled_users_cannot_get_a_department_catalog(baseline, status, assigned, expected):
    db, client = baseline
    db.create_user(id='atlas_edge', email='edge@atlas.example.test', full_name='Edge',
                   organization_id='atlas', role='MEMBER', status=status)
    if assigned:
        db.add_user_to_department('atlas_engineering', 'atlas_edge', role='MEMBER')
    token = create_access_token({'sub': 'atlas_edge', 'org_id': 'atlas', 'role': 'ORG_ADMIN'})
    response = client.get('/api/v1/workflows/ai/context',
                          headers={'Authorization': 'Bearer ' + token}, params={'department_id': 'atlas_engineering'})
    assert response.status_code == expected


def test_global_manager_with_member_department_has_authoring_but_not_management(baseline):
    db, client = baseline
    db.add_user_to_department('atlas_finance', 'atlas_MANAGER', role='MEMBER')
    headers = auth('MANAGER', department='finance')
    payload = {'name': 'Mixed role', 'department_id': 'atlas_finance', 'webhook_enabled': False,
               'definition_json': json.dumps({'steps': [{'key': 'read', 'agent_id': 'atlas_finance', 'prompt_template': 'Read.'}]})}
    response = client.post('/api/v1/workflows/', headers=headers, json=payload)
    assert response.status_code == 201, response.text
    workflow = response.json()
    assert not workflow['is_active']
    assert client.put(f"/api/v1/workflows/{workflow['id']}", headers=headers,
                      json={'is_active': True}).status_code in (403, 404)
    assert not db.get_workflow(workflow['id']).is_active
