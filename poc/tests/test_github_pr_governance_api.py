"""AI-19 real HTTP/SQLite admission contracts. No agent execution or provider doubles."""
import json
from datetime import datetime, timedelta
import pytest
from poc.tests.test_generic_governance_api import baseline, auth, TOOLS

BASE = '/api/v1/governance'
DEPT = BASE + '/departments/atlas_engineering'


def decide(client, operation, **extra):
    return client.post(DEPT + '/decisions', headers=auth('OPERATOR'), json={
        'capability_id': 'github.' + operation, 'connector_id': 'atlas_github',
        'resource_id': 'owner/repository', **extra})


def grant(client, tools):
    return client.post('/api/v1/departments/atlas_engineering/mcp-access', headers=auth(),
                       json={'connector_id': 'atlas_github', 'allowed_tools': tools})


def test_pr_descriptors_separate_reads_writes_and_human_approval(baseline):
    _, client = baseline
    response = client.get(BASE + '/capabilities', headers=auth('MEMBER'))
    assert response.status_code == 200
    caps = {value['id']: value for value in response.json()['capabilities']}
    for operation in ('get_pull_request', 'get_pull_request_diff', 'get_pull_request_checks'):
        assert caps['github.' + operation]['effect'] == 'read'
        assert 'pull_number' in caps['github.' + operation]['input_schema']['required']
    for operation in ('comment_pull_request', 'review_pull_request'):
        value = caps['github.' + operation]
        assert value['effect'] == 'write' and value['implemented'] is True
        assert {'repository', 'pull_number', 'head_sha', 'body'} <= set(value['input_schema']['required'])
        assert value['input_schema']['additionalProperties'] is False
    assert caps['github.review_pull_request']['input_schema']['properties']['event']['enum'] == ['COMMENT', 'REQUEST_CHANGES']
    assert caps['github.merge_pull_request']['server_only'] and caps['github.merge_pull_request']['approval_required']
    assert set(caps['github.get_pull_request_review']['requires_capabilities']) == {
        'github.get_pull_request', 'github.get_pull_request_diff', 'github.get_pull_request_checks'}


@pytest.mark.parametrize('operation', ['comment_pull_request', 'review_pull_request'])
def test_wildcard_never_authorizes_new_pr_writes(baseline, operation):
    _, client = baseline
    assert grant(client, '*').status_code == 201
    assert decide(client, operation).json()['decision'] == 'denied'
    assert decide(client, 'get_pull_request_diff').json()['decision'] == 'allowed'
    assert grant(client, [*TOOLS['github'], operation]).status_code == 201
    assert decide(client, operation).json()['decision'] == 'allowed'
    value = client.get('/api/v1/workflows/ai/context', headers=auth('MEMBER'), params={'department_id': 'atlas_engineering'})
    connector = next(item for item in value.json()['catalog']['connectors'] if item['id'] == 'atlas_github')
    assert connector['resources_by_tool'][operation] == ['owner/repository']
    assert 'merge_pull_request' not in connector['tools']


def test_aggregate_cannot_bypass_a_narrow_read_denial(baseline):
    _, client = baseline
    response = client.put(DEPT + '/policy', headers=auth('MANAGER'), json={'expected_revision': 0, 'rules': [{
        'id': 'no_diff', 'capability_id': 'github.get_pull_request_diff', 'connector_id': 'atlas_github',
        'resource_type': 'repository', 'resource_ids': ['owner/repository'], 'effect': 'deny'}]})
    assert response.status_code == 200
    assert decide(client, 'get_pull_request').json()['decision'] == 'allowed'
    result = decide(client, 'get_pull_request_review').json()
    assert result['decision'] == 'denied' and result['reason'] == 'DEPENDENT_CAPABILITY_DENIED'
    value = client.get('/api/v1/workflows/ai/context', headers=auth('MEMBER'), params={'department_id': 'atlas_engineering'})
    connector = next(item for item in value.json()['catalog']['connectors'] if item['id'] == 'atlas_github')
    assert 'get_pull_request_review' not in connector['tools'] and 'get_pull_request_diff' not in connector['tools']


def test_aggregate_requires_explicit_read_dependencies_without_grant_backfill(baseline):
    db, client = baseline
    assert grant(client, ['get_pull_request_review']).status_code == 201
    assert decide(client, 'get_pull_request_review').json()['reason'] == 'DEPENDENT_CAPABILITY_DENIED'
    assert json.loads(db.get_department_mcp_access('atlas_engineering', 'atlas_github').allowed_tools) == ['get_pull_request_review']


def test_ready_pr_write_plan_revalidates_grant_and_saves_inactive(baseline):
    db, client = baseline
    proposal = {'name': 'PR comment plan', 'steps': [{'key': 'comment', 'name': 'Comment',
        'agent_id': 'atlas_engineering', 'prompt_template': 'Read the exact current head and post the requested comment.',
        'resources': [{'connector_id': 'atlas_github', 'repository': 'owner/repository', 'tool_name': 'comment_pull_request'}]}]}
    now = datetime.now().isoformat()
    with db._get_connection() as conn:
        conn.execute('''INSERT INTO workflow_builder_jobs
            (id,organization_id,user_id,department_id,request_hash,request_json,status,result_json,
             provider_id,model_id,cost_source,created_at,deadline_at) VALUES
            ('pr-write-ready','atlas','atlas_MEMBER','atlas_engineering','hash','{}','READY',?,
             'unused','unused','API_KEY',?,?)''', (json.dumps({'workflow': proposal}), now, now))
    path = '/api/v1/workflows/ai/chat/pr-write-ready/create'
    assert client.post(path, headers=auth('MEMBER')).status_code == 422
    assert grant(client, [*TOOLS['github'], 'comment_pull_request']).status_code == 201
    response = client.post(path, headers=auth('MEMBER'))
    assert response.status_code == 200, response.text
    workflow = db.get_workflow(response.json()['id'])
    assert not workflow.is_active
    assert json.loads(workflow.definition_json)['steps'][0]['params']['authorized_resources'][0]['tool_name'] == 'comment_pull_request'
    with db._get_connection() as conn:
        assert conn.execute('SELECT COUNT(*) FROM workflow_executions').fetchone()[0] == 0
        assert conn.execute('SELECT COUNT(*) FROM mcp_tool_calls').fetchone()[0] == 0


def test_pr_write_catalog_is_exact_per_resource_and_current_role(baseline):
    db, client = baseline
    connector = db.get_mcp_connector('atlas_github')
    db.save_mcp_connector({**connector.to_dict(), 'configuration': {**connector.configuration, 'allowed_repos': ['owner/repository', 'owner/other']}})
    assert grant(client, [*TOOLS['github'], 'comment_pull_request']).status_code == 201
    assert client.put(DEPT + '/policy', headers=auth(), json={'expected_revision': 0, 'rules': [{
        'id': 'no_comment_other', 'capability_id': 'github.comment_pull_request', 'connector_id': 'atlas_github',
        'resource_type': 'repository', 'resource_ids': ['owner/other'], 'effect': 'deny'}]}).status_code == 200
    assert decide(client, 'comment_pull_request', resource_id='owner/other').json()['decision'] == 'denied'
    assert decide(client, 'comment_pull_request', agent_id='boreal_engineering').status_code == 404
    db.update_user('atlas_OPERATOR', role='MEMBER')
    assert decide(client, 'comment_pull_request').json()['decision'] == 'denied'
    with db._get_connection() as conn:
        assert conn.execute('SELECT COUNT(*) FROM mcp_tool_calls').fetchone()[0] == 0


def test_revoked_merge_grant_stops_approved_resolution_before_provider_io(baseline):
    db, client = baseline
    client.get('/api/v1/workflows/ai/context', headers=auth(), params={'department_id': 'atlas_engineering'})
    tool = next(tool for tool in db.list_mcp_tools('atlas_github') if tool.name == 'get_pull_request_review')
    db.create_workflow(id='prwf', name='PR admission', organization_id='atlas', department_id='atlas_engineering', definition_json='{"steps":[]}', is_active=False)
    db.create_workflow_execution(execution_id='prexec', workflow_id='prwf', trigger_type='MANUAL', department_id='atlas_engineering', status='WAITING_APPROVAL')
    subject = {'connector_id': 'atlas_github', 'repository': 'owner/repository', 'pull_number': 1,
               'agent_id': 'atlas_engineering', 'tool_id': tool.id, 'head_sha': 'a' * 40, 'base_sha': 'b' * 40,
               'url': 'https://github.com/owner/repository/pull/1'}
    now = datetime.now()
    with db._get_connection() as conn:
        conn.execute('INSERT INTO workflow_execution_tool_contexts VALUES (?,?)', ('prexec', json.dumps({'initiator_id': 'atlas_ORG_ADMIN'})))
        conn.execute('''INSERT INTO workflow_approvals
            (id,execution_id,step_run_id,task_id,organization_id,department_id,workflow_revision,status,
             config_json,subjects_json,report,created_at,expires_at) VALUES
            ('prgate','prexec','prstep','prtask','atlas','atlas_engineering',1,'PENDING',?,?,?, ?,?)''',
            (json.dumps({'kind': 'pull_requests', 'merge_after_approval': True}), json.dumps([subject]),
             'Persisted policy subject, not provider proof.', now.isoformat(), (now + timedelta(hours=1)).isoformat()))
    # Baseline grants intentionally exclude merge. Authenticated approval cannot add it.
    response = client.post('/api/v1/workflows/executions/prexec/approval', headers=auth(), json={'approve': True})
    assert response.status_code == 202, response.text
    value = client.get('/api/v1/workflows/executions/prexec/approval', headers=auth()).json()
    assert value['status'] == 'FAILED' and 'explicit' in value['error']
    assert value['resolved_by'] == 'atlas_ORG_ADMIN' and value['receipts'] == []
    with db._get_connection() as conn:
        assert conn.execute('SELECT COUNT(*) FROM mcp_tool_calls').fetchone()[0] == 0
