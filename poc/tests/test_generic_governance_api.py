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


CHANNEL_BINDINGS = '/api/v1/governance/channel-bindings'
IDENTITIES = '/api/v1/governance/external-identities'


def test_identity_management_respects_department_role_and_shared_links(baseline):
    import time

    db, client = baseline
    path = f'{IDENTITIES}/departments/atlas_engineering/links'
    identity_id = 'idl_' + 'a' * 32
    with db._get_connection() as conn:
        conn.execute("""INSERT INTO external_identity_links
            (id,organization_id,connector_id,user_id,provider,account,subject,created_at)
            VALUES (?,?,?,?,?,?,?,?)""",
            (identity_id, 'atlas', 'atlas_telegram', 'atlas_MEMBER', 'telegram', '123456', '9876', int(time.time())))
    manager = auth('MANAGER')
    result = client.get(path, headers=manager)
    assert result.status_code == 200, result.text
    assert [(row['id'], row['can_revoke']) for row in result.json()['links']] == [(identity_id, True)]
    assert client.get(path, headers=auth('MEMBER')).status_code in (403, 404)
    assert client.get(path, headers=auth('MANAGER', 'boreal')).status_code == 404
    assert client.get(path, headers=auth(department='finance')).status_code == 404
    db.add_user_to_department('atlas_finance', 'atlas_MEMBER', role='MEMBER')
    db.grant_department_mcp_access('atlas_finance', 'atlas_telegram', allowed_tools=['send_message'], organization_id='atlas')
    assert client.get(path, headers=manager).json()['links'][0]['can_revoke'] is False
    assert client.delete(f'{path}/{identity_id}', headers=manager).status_code == 403
    db.remove_user_from_department('atlas_finance', 'atlas_MEMBER')
    db.update_user('atlas_MANAGER', role='OPERATOR')
    assert client.delete(f'{path}/{identity_id}', headers=manager).status_code in (403, 404)
    db.update_user('atlas_MANAGER', role='MANAGER')
    assert client.delete(f'{path}/{identity_id}', headers=manager).status_code == 204
    assert client.get(IDENTITIES, headers=auth('MEMBER')).json() == []
    with db._get_connection() as conn:
        row = conn.execute("SELECT actor,details FROM audit_logs WHERE action='EXTERNAL_IDENTITY_REVOKED'").fetchone()
    assert row['actor'] == 'atlas_MANAGER'
    assert json.loads(row['details']) == {'organization_id': 'atlas', 'connector_id': 'atlas_telegram'}


def test_identity_catalog_excludes_unconfigured_and_foreign_connectors(baseline):
    db, client = baseline
    for org in ('atlas', 'boreal'):
        path = f'{IDENTITIES}/connectors/{org}_slack/secret'
        setup = {'secret': 'catalog-secret-' + 'x' * 32, 'team_id': 'T12345678', 'app_id': 'A12345678'}
        assert client.put(path, headers=auth(org=org), json=setup).status_code == 204
    available = client.get(IDENTITIES + '/connectors', headers=auth('MEMBER'))
    assert available.status_code == 200, available.text
    assert available.json() == [{'id': 'atlas_slack', 'name': 'slack', 'provider': 'slack'}]
    assert 'catalog-secret' not in available.text


@pytest.mark.parametrize(('provider', 'subject'), [('telegram', '12345'), ('slack', 'U12345678')])
def test_external_identity_proof_confirmation_replay_and_unlink(baseline, provider, subject, caplog):
    import hashlib
    import hmac
    import time
    from urllib.parse import urlencode

    db, client = baseline
    secret = 'identity-test-secret-' + 'x' * 32
    connector_id = 'atlas_' + provider
    setup = {'secret': secret}
    if provider == 'telegram':
        connector = db.get_mcp_connector(connector_id)
        connector.configuration['bot_token'] = '123456:fixture'
        db.save_mcp_connector(connector)
    else:
        setup.update(team_id='T12345678', app_id='A12345678')
    path = f'{IDENTITIES}/connectors/{connector_id}'
    assert client.put(path + '/secret', headers=auth('MEMBER'), json=setup).status_code == 403
    assert client.put(path + '/secret', headers=auth(), json=setup).status_code == 204
    issued = client.post(path + '/challenges', headers=auth('MEMBER'))
    assert issued.status_code == 201, issued.text
    assert issued.headers['cache-control'] == 'no-store'
    challenge = issued.json()
    status_path = f"{IDENTITIES}/challenges/{challenge['id']}"
    assert client.get(status_path, headers=auth()).status_code == 404
    assert client.post(status_path + '/confirm', headers=auth('MEMBER'), json={'subject': subject}).status_code == 409
    timestamp = int(time.time())
    if provider == 'telegram':
        raw = json.dumps({'message': {'from': {'id': int(subject), 'is_bot': False},
            'chat': {'id': int(subject), 'type': 'private'}, 'date': timestamp,
            'text': '/start ' + challenge['code']}}).encode()
        headers = {'X-Telegram-Bot-Api-Secret-Token': secret}
    else:
        raw = urlencode({'user_id': subject, 'team_id': setup['team_id'], 'api_app_id': setup['app_id'],
                         'command': '/platform-link', 'text': challenge['code']}).encode()
        signature = hmac.new(secret.encode(), f'v0:{timestamp}:'.encode() + raw, hashlib.sha256).hexdigest()
        headers = {'X-Slack-Request-Timestamp': str(timestamp), 'X-Slack-Signature': 'v0=' + signature}
    proof_path = f'/api/v1/external-identity-proofs/{connector_id}'
    assert client.post(proof_path, content=raw).status_code == 403
    assert client.post(proof_path, headers=headers, content=raw).status_code == 200
    assert client.post(proof_path, headers=headers, content=raw).status_code == 200
    assert client.get(status_path, headers=auth('MEMBER')).json()['subject'] == subject
    link = client.post(status_path + '/confirm', headers=auth('MEMBER'), json={'subject': subject})
    assert link.status_code == 201, link.text
    assert client.post(status_path + '/confirm', headers=auth('MEMBER'), json={'subject': subject}).status_code == 409
    link_path = IDENTITIES + '/' + link.json()['id']
    assert client.delete(link_path, headers=auth()).status_code == 404
    fresh = client.post(path + '/challenges', headers=auth('MEMBER')).json()
    assert client.put(path + '/secret', headers=auth(), json={**setup, 'secret': 'rotated-' + 'y' * 32}).status_code == 204
    assert client.get(f"{IDENTITIES}/challenges/{fresh['id']}", headers=auth('MEMBER')).status_code == 409
    assert client.delete(link_path, headers=auth('MEMBER')).status_code == 204
    assert client.get(IDENTITIES, headers=auth('MEMBER')).json() == []
    with db._get_connection() as conn:
        audits = conn.execute("SELECT action, details FROM audit_logs WHERE entity_type='external_identity'").fetchall()
    assert {row['action'] for row in audits} == {
        'EXTERNAL_IDENTITY_LINKED', 'EXTERNAL_IDENTITY_UNLINKED', 'EXTERNAL_IDENTITY_SECRET_ROTATED',
    }
    assert secret not in str([dict(row) for row in audits]) + caplog.text
    assert challenge['code'] not in str([dict(row) for row in audits]) + caplog.text


def binding_payload(**overrides):
    return {'department_id': 'atlas_engineering', 'connector_id': 'atlas_telegram',
            'provider': 'telegram', 'channel_id': '12345', **overrides}


def test_channel_binding_lifecycle_is_scoped_revisioned_and_audited(baseline):
    db, client = baseline
    headers = auth()
    department = {'department_id': 'atlas_engineering'}
    original = client.post(CHANNEL_BINDINGS, headers=headers, json=binding_payload(
        uses={'send_notifications': True},
    ))
    assert original.status_code == 201, original.text
    binding = original.json()
    path = CHANNEL_BINDINGS + '/' + binding['id']
    assert binding['uses'] == {'send_notifications': True, 'trigger_workflows': False, 'approve_decisions': False}
    assert binding['revision'] == 1
    assert client.post(CHANNEL_BINDINGS, headers=headers, json=binding_payload()).status_code == 409
    organization_binding = client.post(CHANNEL_BINDINGS, headers=headers, json=binding_payload(department_id=None))
    assert organization_binding.status_code == 201
    assert client.get(CHANNEL_BINDINGS, headers=headers).json()['bindings'] == [organization_binding.json()]
    assert client.get(CHANNEL_BINDINGS, headers=auth('MANAGER'), params=department).json()['bindings'] == [binding]
    member_rows = client.get(CHANNEL_BINDINGS, headers=auth('MEMBER'), params=department)
    assert member_rows.status_code == 200
    assert member_rows.json()['bindings'] == [binding]

    replacement = {'expected_revision': 1, 'uses': {'approve_decisions': True}}
    assert client.put(path + '/uses', headers=auth('MEMBER'), params=department, json=replacement).status_code == 403
    assert client.delete(path, headers=auth('MANAGER'),
                         params={**department, 'expected_revision': 1}).status_code == 403
    assert client.put(path + '/uses', headers=headers, json=replacement).status_code == 404
    assert client.put(path + '/uses', headers=auth(org='boreal'),
                      params={'department_id': 'boreal_engineering'}, json=replacement).status_code == 404
    changed = client.put(path + '/uses', headers=headers, params=department, json=replacement)
    assert changed.status_code == 200, changed.text
    assert changed.json()['revision'] == 2
    assert changed.json()['uses'] == {'send_notifications': False, 'trigger_workflows': False, 'approve_decisions': True}
    assert client.put(path + '/uses', headers=headers, params=department, json=replacement).status_code == 409
    assert client.put(path + '/uses', headers=headers, params=department,
                      json={**replacement, 'expected_revision': 2}).json() == changed.json()
    assert client.delete(path, headers=headers, params={**department, 'expected_revision': 1}).status_code == 409
    assert client.delete(path, headers=headers, params={**department, 'expected_revision': 2}).status_code == 204
    assert client.get(CHANNEL_BINDINGS, headers=headers, params=department).json()['bindings'] == []

    with db._get_connection() as conn:
        rows = conn.execute(
            "SELECT action, actor, details FROM audit_logs WHERE entity_type = 'channel_binding' AND entity_id = ?",
            (binding['id'],),
        ).fetchall()
    assert {row['action'] for row in rows} == {
        'CHANNEL_BINDING_CREATED', 'CHANNEL_BINDING_UPDATED', 'CHANNEL_BINDING_REMOVED',
    }
    assert len(rows) == 3
    for row in rows:
        assert row['actor'] == 'atlas_ORG_ADMIN'
        assert set(json.loads(row['details'])) == {
            'organization_id', 'department_id', 'connector_id', 'provider', 'channel_id', 'revision', 'uses',
        }
    assert db.get_mcp_connector('atlas_telegram').configuration['allowed_channels'] == ['12345']
    assert db.check_department_mcp_permission('atlas_engineering', 'atlas_telegram', 'send_message')['allowed']


@pytest.mark.parametrize(('overrides', 'status'), [
    ({'connector_id': 'boreal_telegram'}, 404),
    ({'department_id': 'boreal_engineering'}, 404),
    ({'connector_id': 'atlas_slack'}, 422),
    ({'channel_id': '@mutable_alias'}, 422),
    ({'channel_id': '*'}, 422),
    ({'channel_id': '99999'}, 422),
    ({'uses': {'trigger_workflows': 'true'}}, 422),
    ({'uses': {'trigger_workflows': True, 'wildcard': True}}, 422),
])
def test_channel_binding_rejects_foreign_or_invalid_identity_and_flags(baseline, overrides, status):
    _, client = baseline
    response = client.post(CHANNEL_BINDINGS, headers=auth(), json=binding_payload(**overrides))
    assert response.status_code == status, response.text
    assert client.get(CHANNEL_BINDINGS, headers=auth(), params={'department_id': 'atlas_engineering'}).json()['bindings'] == []


def test_channel_bindings_require_admin_mutation_and_respect_selected_department(baseline):
    _, client = baseline
    department = {'department_id': 'atlas_engineering'}
    for role in ('MANAGER', 'OPERATOR', 'MEMBER'):
        assert client.post(CHANNEL_BINDINGS, headers=auth(role), json=binding_payload()).status_code == 403
        assert client.get(CHANNEL_BINDINGS, headers=auth(role)).status_code == 403
    assert client.get(CHANNEL_BINDINGS, headers=auth('MEMBER'),
                      params={'department_id': 'atlas_finance'}).status_code == 404
    assert client.get(CHANNEL_BINDINGS, headers=auth(department='finance'), params=department).status_code == 404
    slack = client.post(CHANNEL_BINDINGS, headers=auth(), json=binding_payload(
        connector_id='atlas_slack', provider='slack', channel_id='C12345678', uses={'trigger_workflows': True},
    ))
    assert slack.status_code == 201, slack.text
    assert slack.json()['uses'] == {'send_notifications': False, 'trigger_workflows': True, 'approve_decisions': False}
    assert 'private-fixture-secret' not in slack.text
    assert client.post(CHANNEL_BINDINGS, headers=auth(), json=binding_payload()).status_code == 201
    first = client.get(CHANNEL_BINDINGS, headers=auth(), params={**department, 'limit': 1}).json()
    second = client.get(CHANNEL_BINDINGS, headers=auth(), params={**department, 'limit': 1, 'after': first['next_after']}).json()
    assert first['bindings'][0]['id'] != second['bindings'][0]['id']
    assert second['next_after'] is None


def test_channel_catalog_projects_existing_mcp_channels_without_connector_configuration(baseline):
    db, client = baseline
    telegram = db.get_mcp_connector('atlas_telegram')
    telegram.configuration['channel_labels'] = {'12345': ' Legal Operations ', '99999': 'Unconfigured'}
    db.save_mcp_connector(telegram)
    path = CHANNEL_BINDINGS + '/catalog'
    department = {'department_id': 'atlas_engineering'}
    result = client.get(path, headers=auth(), params=department)
    assert result.status_code == 200, result.text
    catalog = result.json()
    assert set(catalog['providers']) == {'telegram', 'slack'}
    assert catalog['providers']['telegram']['runtime_supported_uses'] == ['send_notifications']
    assert {row['id']: row['channel_ids'] for row in catalog['connectors']} == {
        'atlas_telegram': ['12345'], 'atlas_slack': ['C12345678'],
    }
    assert {row['id']: row['channel_labels'] for row in catalog['connectors']} == {
        'atlas_telegram': {'12345': 'Legal Operations'}, 'atlas_slack': {},
    }
    assert all(set(row) == {'id', 'name', 'provider', 'status', 'channel_ids', 'channel_labels'} for row in catalog['connectors'])
    member = client.get(path, headers=auth('MEMBER'), params=department)
    assert member.status_code == 200, member.text
    assert all(not row['channel_ids'] and not row['channel_labels'] for row in member.json()['connectors'])
    assert client.post(CHANNEL_BINDINGS, headers=auth(), json=binding_payload()).status_code == 201
    bindings = client.get(CHANNEL_BINDINGS, headers=auth('MEMBER'), params=department)
    assert bindings.status_code == 200, bindings.text
    assert [(row['channel_id'], row['channel_name']) for row in bindings.json()['bindings']] == [
        ('12345', 'Legal Operations'),
    ]


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
