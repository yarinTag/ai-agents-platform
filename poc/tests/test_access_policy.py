"""Real SQLite/FastAPI permission boundaries; no workers, providers or live sends."""
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request
from config import AgentConfig, ConfigManager
from persistence import DatabaseManager
from backend.dependencies import get_db_manager, get_config_manager
from backend.router_registry import register_routers
from backend.security.tokens import create_access_token
from backend.security.identity import load_actor
from backend.security.resource_access import Resources
from backend.security.response_policy import filter_payload
from runtime.tenant_workspace import tenant_workspace


@pytest.fixture
def access_lab(tmp_path, monkeypatch):
    monkeypatch.setenv('JWT_SECRET_KEY', 'isolated-access-policy-contract-key-000000000')
    monkeypatch.setenv('PLATFORM_TENANT_STORAGE_ROOT', str(tmp_path / 'files'))
    db = DatabaseManager(str(tmp_path / 'policy.db'))
    actors = {}
    for org in ('atlas', 'boreal'):
        db.create_organization(id=org, name=org, slug=org)
        for department in ('engineering', 'finance', 'operations'):
            db.create_department(id=f'{org}_{department}', name=department, organization_id=org)
            db.save_agent(AgentConfig(id=f'{org}_{department}_agent', name=department,
                description='Isolated policy fixture', system_prompt='Read only.', model='default',
                organization_id=org, department_id=f'{org}_{department}', allowed_tools=['Read']))
            db.create_workflow(id=f'{org}_{department}_workflow', name=department,
                department_id=f'{org}_{department}', organization_id=org,
                definition_json=json.dumps({'steps': []}), is_active=False)
        for role in ('ORG_ADMIN', 'MANAGER', 'OPERATOR', 'MEMBER'):
            user = db.create_user(id=f'{org}_{role}', organization_id=org,
                email=f'{role.lower()}@{org}.example.test', full_name=role, role=role, status='ACTIVE')
            if role != 'ORG_ADMIN':
                db.add_user_to_department(department_id=f'{org}_engineering', user_id=user.id, role=role)
            actors[(org, role)] = user
    app = FastAPI()
    app.dependency_overrides[get_db_manager] = lambda: db
    config = ConfigManager(str(tmp_path / 'config'))
    app.dependency_overrides[get_config_manager] = lambda: config
    register_routers(app)
    with TestClient(app) as client:
        yield db, client, actors


def headers(user, role=None, department=None):
    result = {'Authorization': 'Bearer ' + create_access_token({'sub': user.id,
        'org_id': user.organization_id, 'role': role or user.role})}
    if department:
        result['X-Department-ID'] = department
    return result


def test_lists_details_and_selected_department_are_scoped(access_lab):
    db, client, actors = access_lab
    member = actors['atlas', 'MEMBER']
    response = client.get('/api/v1/agents/', headers=headers(member))
    assert response.status_code == 200
    assert {row['id'] for row in response.json()} == {'atlas_engineering_agent'}
    for identifier in ('atlas_finance_agent', 'boreal_engineering_agent', 'missing'):
        assert client.get(f'/api/v1/agents/{identifier}', headers=headers(member)).status_code == 404
    admin = actors['atlas', 'ORG_ADMIN']
    workflows = client.get('/api/v1/workflows/', headers=headers(admin, department='atlas_finance'))
    assert workflows.status_code == 200
    assert {row['id'] for row in workflows.json()} == {'atlas_finance_workflow'}
    assert client.get('/api/v1/workflows/', headers=headers(admin, department='boreal_finance')).status_code == 403


def test_stale_admin_claims_and_disabled_users_cannot_restore_rights(access_lab):
    db, client, actors = access_lab
    member = actors['atlas', 'MEMBER']
    forged_role = headers(member, role='ORG_ADMIN')
    assert client.post('/api/v1/departments', json={'name': 'Forbidden'}, headers=forged_role).status_code == 403
    admin = actors['atlas', 'ORG_ADMIN']
    token = headers(admin)
    db.update_user(admin.id, status='DISABLED')
    assert client.get('/api/v1/auth/me', headers=token).status_code == 401


def test_membership_role_limits_global_manager_and_revocation_takes_effect(access_lab):
    db, client, actors = access_lab
    manager = actors['atlas', 'MANAGER']
    db.add_user_to_department(department_id='atlas_finance', user_id=manager.id, role='MEMBER')
    request = Request({'type': 'http', 'method': 'GET', 'path': '/', 'headers': [(b'x-department-id', b'atlas_finance')], 'query_string': b''})
    request.state.user = {'sub': manager.id, 'org_id': 'atlas', 'role': 'ORG_ADMIN'}
    actor = load_actor(request, db)
    assert not actor.admin
    assert actor.allows('atlas_finance', 1)
    assert not actor.allows('atlas_finance', 3)
    db.remove_user_from_department('atlas_engineering', manager.id)
    assert client.get('/api/v1/agents/atlas_engineering_agent', headers=headers(manager)).status_code == 404


def test_member_write_and_foreign_nested_reference_fail_before_mutation(access_lab):
    db, client, actors = access_lab
    member = actors['atlas', 'MEMBER']
    assert client.put('/api/v1/agents/atlas_engineering_agent', json={'name': 'Forbidden'}, headers=headers(member)).status_code in (403, 404)
    manager = actors['atlas', 'MANAGER']
    response = client.put('/api/v1/agents/atlas_engineering_agent',
        json={'parent_id': 'boreal_engineering_agent'}, headers=headers(manager))
    assert response.status_code == 404
    assert db.get_agent('atlas_engineering_agent').parent_id is None
    assert client.post('/api/v1/departments', json={'name': 'Forbidden', 'organization_id': 'boreal'}, headers=headers(manager)).status_code in (403, 404)


def test_manager_can_update_own_workflow_but_cannot_change_tenant(access_lab):
    db, client, actors = access_lab
    manager = actors['atlas', 'MANAGER']
    response = client.put('/api/v1/workflows/atlas_engineering_workflow',
        json={'name': 'Managed', 'expected_revision': 1}, headers=headers(manager))
    assert response.status_code == 200
    assert db.get_workflow('atlas_engineering_workflow').name == 'Managed'
    assert client.put('/api/v1/agents/atlas_engineering_agent', json={'organization_id': 'boreal'}, headers=headers(manager)).status_code in (403, 404)


def test_org_admin_is_never_a_platform_admin(access_lab):
    db, client, actors = access_lab
    admin = actors['atlas', 'ORG_ADMIN']
    organizations = client.get('/api/v1/organizations', headers=headers(admin))
    assert organizations.status_code == 200
    assert {row['id'] for row in organizations.json()} == {'atlas'}
    assert client.get('/api/v1/organizations/boreal', headers=headers(admin)).status_code == 404
    assert client.post('/api/v1/organizations', json={'name': 'No', 'slug': 'no'}, headers=headers(admin)).status_code == 403
    assert client.get('/api/v1/queue/status', headers=headers(admin)).status_code == 403
    assert client.post('/api/v1/fs/pick-folder', json={}, headers=headers(admin)).status_code == 403


def test_current_department_events_and_unattributed_records_are_fail_closed(access_lab):
    db, client, actors = access_lab
    admin = actors['atlas', 'ORG_ADMIN']
    request = Request({'type': 'http', 'method': 'GET', 'path': '/api/v1/events/system/recent-activity', 'headers': [], 'query_string': b''})
    request.state.user = {'sub': admin.id, 'org_id': 'atlas', 'role': 'ORG_ADMIN'}
    actor = load_actor(request, db)
    request.state.access_actor, request.state.access_resources = actor, Resources(actor)
    payload = filter_payload(request, {'activity': [{'entity_id': 'unattributed_task', 'description': 'Private'}]})
    assert payload['activity'] == []


def test_tenant_paths_cannot_escape_via_sibling_absolute_or_symlink(tmp_path, monkeypatch):
    monkeypatch.setenv('PLATFORM_TENANT_STORAGE_ROOT', str(tmp_path))
    allowed = tenant_workspace('atlas', 'engineering', create=True)
    assert allowed.is_relative_to(tmp_path / 'atlas' / 'departments' / 'engineering')
    with pytest.raises(ValueError):
        tenant_workspace('atlas', 'engineering', tmp_path / 'boreal' / 'shared')
    with pytest.raises(ValueError):
        tenant_workspace('atlas', 'engineering', tmp_path / 'atlas' / 'departments' / 'finance')
    external = tmp_path / 'boreal'; external.mkdir(exist_ok=True)
    (allowed / 'escape').symlink_to(external, target_is_directory=True)
    with pytest.raises(ValueError):
        tenant_workspace('atlas', 'engineering', allowed / 'escape')


def test_operator_can_operate_own_agent_but_not_manage_it(access_lab):
    db, client, actors = access_lab
    operator = actors['atlas', 'OPERATOR']
    request = Request({'type': 'http', 'method': 'GET', 'path': '/', 'headers': [], 'query_string': b''})
    request.state.user = {'sub': operator.id, 'org_id': 'atlas', 'role': 'ORG_ADMIN'}
    resources = Resources(load_actor(request, db))
    assert resources.allows('agent', 'atlas_engineering_agent', 2)
    assert not resources.allows('agent', 'atlas_engineering_agent', 3)
    assert not resources.allows('agent', 'atlas_finance_agent', 2)
    response = client.put('/api/v1/agents/atlas_engineering_agent', json={'name': 'No'}, headers=headers(operator))
    assert response.status_code in (403, 404)


def test_unknown_endpoint_requires_explicit_reviewed_permission_entry():
    from backend.security.route_permissions import required_level
    from fastapi import HTTPException
    request = Request({'type': 'http', 'method': 'GET', 'path': '/api/v1/agents/unreviewed', 'headers': [], 'query_string': b''})
    with pytest.raises(HTTPException) as caught:
        required_level(request, 'agents')
    assert caught.value.status_code == 403


def test_engine_admission_uses_current_roles_and_never_admin_cross_department_bypass(access_lab):
    from workflows.agent_scope import require_agent_scope
    from workflows.execution_models import UnauthorizedUserDepartmentError
    db, client, actors = access_lab
    workflow = db.get_workflow('atlas_engineering_workflow')
    admin = actors['atlas', 'ORG_ADMIN']
    with pytest.raises(UnauthorizedUserDepartmentError):
        require_agent_scope(db.get_agent('atlas_finance_agent'), workflow,
                            {'sub': admin.id, 'org_id': 'atlas', 'role': 'ORG_ADMIN'}, db=db)
    member = actors['atlas', 'MEMBER']
    with pytest.raises(UnauthorizedUserDepartmentError):
        require_agent_scope(db.get_agent('atlas_engineering_agent'), workflow,
                            {'sub': member.id, 'org_id': 'atlas', 'role': 'ORG_ADMIN'}, db=db)


def test_department_transfer_cannot_silently_transfer_history(access_lab):
    db, client, actors = access_lab
    response = client.put('/api/v1/agents/atlas_engineering_agent',
        json={'department_id': 'atlas_finance'}, headers=headers(actors['atlas', 'ORG_ADMIN']))
    assert response.status_code == 409
    assert db.get_agent('atlas_engineering_agent').department_id == 'atlas_engineering'


@pytest.mark.parametrize('role', ['MEMBER', 'OPERATOR', 'MANAGER'])
def test_all_department_members_can_author_workflows(access_lab, role):
    db, client, actors = access_lab
    user = actors['atlas', role]
    auth = headers(user, department='atlas_engineering')
    context = client.get('/api/v1/workflows/ai/context', headers=auth)
    assert context.status_code == 200, context.text
    assert {d['id'] for d in context.json()['departments']} == {'atlas_engineering'}
    payload = {'name': 'Member-authored', 'department_id': 'atlas_engineering',
               'definition_json': json.dumps({'steps': [{'key': 'work',
                   'agent_id': 'atlas_engineering_agent', 'prompt_template': 'Review.'}]})}
    created = client.post('/api/v1/workflows/', headers=auth, json=payload)
    assert created.status_code == 201, created.text
    workflow_id = created.json()['id']
    assert db.get_workflow(workflow_id).is_active == (role == 'MANAGER')
    if role == 'MEMBER':
        assert client.put(f'/api/v1/workflows/{workflow_id}', headers=auth,
                          json={'is_active': True}).status_code in (403, 404)
        assert client.post(f'/api/v1/workflows/{workflow_id}/execute', headers=auth,
                           json={}).status_code in (403, 404)
        assert not db.get_workflow(workflow_id).is_active
    for department in ('atlas_finance', 'boreal_engineering'):
        denied = client.post('/api/v1/workflows/', headers=auth,
                             json={**payload, 'department_id': department})
        assert denied.status_code in (403, 404)
    db.remove_user_from_department('atlas_engineering', user.id)
    assert client.get('/api/v1/workflows/ai/context', headers=auth).status_code == 403
