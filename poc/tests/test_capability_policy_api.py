"""AI-16 real HTTP/SQLite policy tests. No agents, provider network or execution calls."""
import json
from datetime import datetime, timedelta, timezone
import pytest
from poc.tests.test_generic_governance_api import baseline, auth
from governance.store import capture

BASE = '/api/v1/governance'
DEPT = BASE + '/departments/atlas_engineering'
READ = 'github.list_open_pull_requests'


def rule(identifier='restrict', effect='deny', cap=READ, resource='owner/repository', **extra):
    return {'id': identifier, 'effect': effect, 'capability_id': cap, 'connector_id': 'atlas_github',
            'resource_type': 'repository', 'resource_ids': [resource], **extra}


def save(client, rules, *, role='ORG_ADMIN', revision=0, default='inherit', organization=False, path=None):
    return client.put(path or (BASE + '/organization/policy' if organization else DEPT + '/policy'),
        headers=auth(role), json={'expected_revision': revision, 'default': default, 'rules': rules})


def decision(client, *, role='OPERATOR', cap=READ, purpose='execution', **extra):
    return client.post(DEPT + '/decisions', headers=auth(role), json={
        'capability_id': cap, 'connector_id': 'atlas_github', 'resource_id': 'owner/repository',
        'purpose': purpose, **extra})


def test_registry_is_trusted_and_distinguishes_unsupported_features(baseline):
    _, client = baseline
    response = client.get(BASE + '/capabilities', headers=auth('MEMBER'))
    assert response.status_code == 200, response.text
    caps = {value['id']: value for value in response.json()['capabilities']}
    assert caps[READ]['implemented'] and caps[READ]['effect'] == 'read'
    assert caps['github.merge_pull_request']['server_only'] and caps['github.merge_pull_request']['approval_required']
    assert caps['telegram.listen_channel']['implemented'] is False
    assert caps['github.rerun_checks']['implemented'] is False
    assert save(client, [rule(cap='github.rerun_checks')]).status_code == 422
    assert decision(client, cap='invented.run_anything').json()['decision'] == 'denied'


@pytest.mark.parametrize('role,readable,writable', [('ORG_ADMIN', 200, 200), ('MANAGER', 200, 200), ('OPERATOR', 404, 404), ('MEMBER', 404, 404)])
def test_policy_edits_and_catalog_roles_are_server_authoritative(baseline, role, readable, writable):
    _, client = baseline
    assert client.get(DEPT + '/policy', headers=auth(role)).status_code == readable
    assert save(client, [rule()], role=role).status_code == writable
    assert client.get(DEPT + '/catalog', headers=auth(role)).status_code == 200


def test_manager_can_only_append_restrictions_and_never_expand_grants(baseline):
    _, client = baseline
    assert save(client, [rule(effect='allow')], role='MANAGER').status_code == 403
    assert save(client, [rule()], role='MANAGER').status_code == 200
    assert save(client, [], role='MANAGER', revision=1).status_code == 403
    assert save(client, [rule(), rule('gate', 'require_approval', cap='github.get_pull_request_review')],
                role='MANAGER', revision=1).status_code == 200
    assert save(client, [], role='MANAGER', organization=True).status_code == 403
    assert decision(client).json()['decision'] == 'denied'
    assert decision(client, cap='github.get_pull_request_review').json()['decision'] == 'requires_approval'


def test_org_department_intersection_deny_priority_and_default_deny(baseline):
    _, client = baseline
    assert save(client, [rule(effect='allow')], default='deny', organization=True).status_code == 200
    assert decision(client).json()['decision'] == 'allowed'
    assert decision(client, cap='github.get_pull_request_review').json()['decision'] == 'denied'
    assert save(client, [rule()]).status_code == 200
    assert decision(client).json()['decision'] == 'denied'
    assert save(client, [rule(effect='allow')], revision=1).status_code == 200
    assert decision(client).json()['decision'] == 'allowed'
    assert save(client, [rule(effect='allow'), rule('deny')], revision=2).status_code == 200
    assert decision(client).json()['reason'] == 'POLICY_DENIED'


def test_legacy_resource_grant_remains_a_ceiling_and_no_implicit_write_wildcard(baseline):
    db, client = baseline
    assert save(client, [rule(effect='allow', cap='github.merge_pull_request')]).status_code == 200
    assert decision(client, cap='github.merge_pull_request').json()['decision'] == 'denied'
    db.grant_department_mcp_access('atlas_engineering', 'atlas_github', allowed_tools='*', organization_id='atlas')
    assert decision(client, cap='github.merge_pull_request').json()['decision'] == 'denied'
    db.grant_department_mcp_access('atlas_engineering', 'atlas_github', allowed_tools=['merge_pull_request'], organization_id='atlas')
    result = decision(client, cap='github.merge_pull_request').json()
    assert result['decision'] == 'requires_approval' and result['non_executable'] is True
    db.revoke_department_mcp_access('atlas_engineering', 'atlas_github')
    assert decision(client, cap='github.merge_pull_request').status_code == 404


def test_revision_conflict_noop_and_actor_history(baseline):
    _, client = baseline
    response = save(client, [rule()])
    assert response.status_code == 200 and response.json()['revision'] == 1
    assert save(client, [], revision=0).status_code == 409
    assert save(client, [rule()], revision=1).json()['revision'] == 1
    assert save(client, [], revision=1).json()['revision'] == 2
    history = client.get(DEPT + '/policy/history', headers=auth('MANAGER'))
    assert history.status_code == 200
    assert [item['revision'] for item in history.json()['revisions']] == [2, 1]
    assert all(item['updated_by'] == 'atlas_ORG_ADMIN' for item in history.json()['revisions'])


@pytest.mark.parametrize('extra', [{'approved': True}, {'actor_id': 'atlas_ORG_ADMIN'}, {'frozen': {}}, {'capability_version': 2}])
def test_decision_cannot_accept_forged_authority(baseline, extra):
    _, client = baseline
    assert decision(client, **extra).status_code == 422


def test_foreign_objects_and_current_role_revocation(baseline):
    db, client = baseline
    assert save(client, [rule(connector_id='boreal_github')]).status_code == 422
    assert save(client, [rule(user_ids=['boreal_MEMBER'])]).status_code == 422
    assert decision(client, agent_id='boreal_engineering').status_code == 404
    assert client.get(BASE + '/departments/boreal_engineering/catalog', headers=auth()).status_code == 404
    assert decision(client, role='MEMBER').json()['decision'] == 'denied'
    assert decision(client, role='MEMBER', purpose='authoring').json()['decision'] == 'allowed'
    token = auth('MANAGER')
    db.update_user('atlas_MANAGER', role='MEMBER')
    assert client.put(DEPT + '/policy', headers=token, json={'expected_revision': 0, 'rules': [rule()]}).status_code in (403, 404)
    db.update_user('atlas_OPERATOR', status='DISABLED')
    assert decision(client).status_code == 401


def test_catalog_and_ai_context_are_narrowed_per_capability_resource(baseline):
    _, client = baseline
    assert save(client, [rule()]).status_code == 200
    response = client.get(DEPT + '/catalog', headers=auth('MEMBER'))
    assert response.status_code == 200
    ids = {entry['capability']['id'] for entry in response.json()['entries']}
    assert READ not in ids and 'github.get_pull_request_review' in ids
    value = client.get('/api/v1/workflows/ai/context', headers=auth('MEMBER'), params={'department_id': 'atlas_engineering'})
    assert value.status_code == 200, value.text
    github = next(connector for connector in value.json()['catalog']['connectors'] if connector['provider'] == 'github')
    assert 'list_open_pull_requests' not in github['tools']
    assert github['resources_by_tool']['get_pull_request_review'] == ['owner/repository']
    assert 'private-fixture-secret' not in json.dumps(response.json())


def test_frozen_policy_never_expands_after_current_policy_is_relaxed(baseline):
    db, client = baseline
    assert save(client, [rule()]).status_code == 200
    db.create_workflow(id='policywf', name='Policy probe', organization_id='atlas', department_id='atlas_engineering', definition_json='{"steps":[]}', is_active=False)
    db.create_workflow_execution(execution_id='policyexec', workflow_id='policywf', trigger_type='MANUAL', department_id='atlas_engineering')
    with db._get_connection() as conn:
        conn.execute('INSERT INTO workflow_execution_tool_contexts VALUES (?,?)',
            ('policyexec', json.dumps({'governance': capture(db, 'atlas', 'atlas_engineering'), 'initiator_id': 'atlas_OPERATOR'})))
    assert save(client, [], revision=1).status_code == 200
    assert decision(client).json()['decision'] == 'allowed'
    assert decision(client, execution_id='policyexec', workflow_id='policywf').json()['decision'] == 'denied'


def test_time_windows_strict_rules_and_request_bounds(baseline):
    _, client = baseline
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    assert save(client, [rule(effect='allow', expires_at=past)], default='deny').status_code == 200
    assert decision(client).json()['decision'] == 'denied'
    assert save(client, [rule(resource_ids=['*'])], revision=1).status_code == 422
    assert save(client, [rule(branches=['main'])], revision=1).status_code == 422
    assert save(client, [rule(capability_version=2)], revision=1).status_code == 422
    assert save(client, [rule(not_before='2026-01-01')], revision=1).status_code == 422
    assert client.put(DEPT + '/policy', headers=auth(), content=' ' * 262145).status_code == 413


def test_concurrent_policy_updates_have_one_winner(baseline):
    from concurrent.futures import ThreadPoolExecutor
    db, client = baseline
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda name: save(client, [rule(name)]), ['first', 'second']))
    assert sorted(response.status_code for response in responses) == [200, 409]
    with db._get_connection() as conn:
        assert conn.execute('SELECT COUNT(*) FROM capability_policy_revisions').fetchone()[0] == 1


def test_rule_cannot_forge_a_capability_implementation_or_unbounded_resource(baseline):
    _, client = baseline
    assert save(client, [rule(implementation='custom_command')]).status_code == 422
    assert save(client, [rule(resource='owner/not-configured')]).status_code == 422
    assert save(client, [rule(agent_ids=['boreal_engineering'])]).status_code == 422
    assert save(client, [rule(), rule()]).status_code == 422
    assert client.get(BASE + '/organization/policy', headers=auth('MEMBER')).status_code == 403


@pytest.mark.parametrize('provider,operation,channel', [('telegram', 'send_message', '12345'),
                                                     ('slack', 'post_chat_message', 'C12345678')])
def test_channel_policy_is_independent_from_membership_and_provider(baseline, provider, operation, channel):
    db, client = baseline
    payload = {'capability_id': provider + '.' + operation, 'connector_id': 'atlas_' + provider,
               'resource_id': channel}
    assert client.post(DEPT + '/decisions', headers=auth('OPERATOR'), json=payload).json()['decision'] == 'allowed'
    restriction = {'id': 'no_send', 'effect': 'deny', 'capability_id': payload['capability_id'],
                   'connector_id': payload['connector_id'], 'resource_type': 'channel', 'resource_ids': [channel]}
    assert save(client, [restriction], role='MANAGER').status_code == 200
    assert client.post(DEPT + '/decisions', headers=auth(), json=payload).json()['decision'] == 'denied'
    assert db.get_department_mcp_access('atlas_engineering', payload['connector_id']).is_active
    with db._get_connection() as conn:
        assert conn.execute('SELECT COUNT(*) FROM mcp_tool_calls').fetchone()[0] == 0


def test_selectors_and_current_policy_are_rechecked_against_frozen_allow(baseline):
    db, client = baseline
    db.create_workflow(id='selectorwf', name='Selector probe', organization_id='atlas',
                       department_id='atlas_engineering', definition_json='{"steps":[]}', is_active=False)
    db.create_workflow_execution(execution_id='selectorexec', workflow_id='selectorwf', trigger_type='MANUAL',
                                 department_id='atlas_engineering')
    with db._get_connection() as conn:
        conn.execute('INSERT INTO workflow_execution_tool_contexts VALUES (?,?)',
                     ('selectorexec', json.dumps({'governance': capture(db, 'atlas', 'atlas_engineering')})))
    restriction = rule(user_ids=['atlas_OPERATOR'], agent_ids=['atlas_engineering'], workflow_ids=['selectorwf'])
    assert save(client, [restriction]).status_code == 200
    assert decision(client, agent_id='atlas_engineering', workflow_id='selectorwf', execution_id='selectorexec').json()['decision'] == 'denied'
    assert decision(client, role='ORG_ADMIN', agent_id='atlas_engineering', workflow_id='selectorwf').json()['decision'] == 'allowed'
    # Missing actor context is conservative, never a way to bypass a targeted deny.
    assert decision(client).json()['decision'] == 'denied'
