"""Pure policy and real SQLite/FastAPI approval contracts; no live I/O or model calls."""
import json
from datetime import datetime, timedelta
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from backend.api.workflows_approvals import router
from backend.dependencies import get_db_manager
from backend.security import authenticate_request, create_access_token
from config import AgentConfig
from persistence import DatabaseManager
from runtime.models import AgentRun, TaskStatus
from integrations.github_prs import project_pull, readiness_blockers
from integrations.pr_approval_policy import authorize_subject, merge_tool
from integrations.tool_definitions import OPERATIONS, ToolAccessError, input_model, public_tool
from workflows.approval_config import approval_configuration, validate_gates
from workflows.human_approval import pinned_subjects
from workflows.parser import WorkflowParser


def test_pr_projection_and_readiness_are_explicit():
    row = {'number': 7, 'user': {'login': 'dependabot[bot]'}, 'title': 'Bump library',
           'labels': [{'name': 'dependencies'}], 'state': 'open', 'draft': False,
           'head': {'ref': 'dependabot/lib', 'sha': 'a' * 40},
           'base': {'ref': 'master', 'sha': 'b' * 40}, 'mergeable': True, 'mergeable_state': 'clean'}
    projected = project_pull(row, 'owner/repo')
    assert projected['author'] == 'dependabot[bot]'
    assert projected['labels'] == ['dependencies']
    assert projected['url'] == 'https://github.com/owner/repo/pull/7'
    assert readiness_blockers(projected, False, False, True, []) == []
    for change in ({'draft': True}, {'draft': None}, {'state': 'closed'}, {'mergeable': None}, {'mergeable_state': 'blocked'}):
        assert readiness_blockers({**projected, **change}, False, False, True, [])
    assert readiness_blockers(projected, True, False, True, [])
    assert readiness_blockers(projected, False, True, True, [])
    assert readiness_blockers(projected, False, False, False, [])
    assert readiness_blockers(projected, False, False, True, [{'state': 'CHANGES_REQUESTED'}])


def test_merge_is_not_a_model_tool_and_read_schemas_are_narrow():
    assert 'merge_pull_request' not in OPERATIONS['github']
    entry = {'provider': 'github', 'operation': 'get_pull_request_review', 'name': 'review',
             'repositories': ['owner/repo'], 'channels': []}
    schema = public_tool(entry)['input_schema']
    assert schema['properties']['repository']['enum'] == ['owner/repo']
    assert 'pull_number' in schema['required']
    with pytest.raises(ValueError):
        input_model(entry).model_validate({'repository': 'owner/repo', 'pull_number': 1, 'token': 'forbidden'})


def definition(extra=False):
    steps = [{'key': 'review', 'agent_id': 'agent', 'prompt_template': 'Review.'},
        {'key': 'approval', 'agent_id': 'agent', 'prompt_template': 'Wait.', 'depends_on': ['review'],
         'mcp_servers': ['telegram'], 'params': {'authorized_resources': [
             {'connector_id': 'telegram', 'channel_id': '12345', 'tool_name': 'send_message'}],
             'human_approval': {'source_step': 'review', 'connector_id': 'telegram', 'channel_id': '12345',
                                'kind': 'pull_requests', 'merge_after_approval': True}}}]
    if extra:
        steps.append({'key': 'after', 'agent_id': 'agent', 'prompt_template': 'Unsafe continuation.', 'depends_on': ['approval']})
    return WorkflowParser.from_dict({'steps': steps})


def test_approval_is_explicit_terminal_and_cannot_hide_work():
    valid = definition()
    validate_gates(valid)
    assert approval_configuration(valid.steps[-1]).merge_after_approval
    with pytest.raises(ValueError, match='terminal'):
        validate_gates(definition(extra=True))
    valid.steps[-1].params['authorized_resources'][0]['channel_id'] = '54321'
    with pytest.raises(ValueError, match='matching'):
        approval_configuration(valid.steps[-1])


@pytest.fixture
def state(tmp_path, monkeypatch):
    monkeypatch.setenv('JWT_SECRET_KEY', 'workflow-pr-approval-test-key-000000000000')
    db = DatabaseManager(str(tmp_path / 'approvals.db'))
    for org in ('own', 'foreign'):
        db.create_organization(id=org, name=org, slug=org)
        db.create_department(id=org, name=org, organization_id=org)
        for role in ('ORG_ADMIN', 'MANAGER', 'MEMBER'):
            db.create_user(id=org + role, email=org + role + '@example.test', full_name=role,
                           organization_id=org, role=role)
            db.add_user_to_department(department_id=org, user_id=org + role, role=role)
    db.save_agent(AgentConfig(id='agent', name='Agent', description='Review', system_prompt='', organization_id='own', department_id='own'))
    db.create_workflow(id='wf', name='Review', organization_id='own', department_id='own', definition_json='{"steps":[]}')
    db.create_workflow_execution(execution_id='exec', workflow_id='wf', trigger_type='MANUAL',
                                 department_id='own', status='WAITING_APPROVAL')
    task = AgentRun(run_id='task', agent_id='agent', project_id=None, prompt='Gate', status=TaskStatus.PENDING_APPROVAL,
                    created_at=datetime.now(), organization_id='own')
    db.save_task_run(task)
    now = datetime.now().isoformat()
    db.save_workflow_step_run({'id': 'step', 'execution_id': 'exec', 'step_key': 'approval', 'agent_id': 'agent',
        'status': 'WAITING_APPROVAL', 'task_run_id': 'task', 'input_data': 'Gate', 'started_at': now,
        'completed_at': None, 'output_data': '', 'error_message': None, 'input_tokens': 0, 'output_tokens': 0, 'cost_usd': 0})
    with db._get_connection() as conn:
        conn.execute('INSERT INTO workflow_execution_tool_contexts VALUES (?,?)', ('exec', json.dumps({'initiator_id': 'ownORG_ADMIN'})))
        conn.execute('''INSERT INTO workflow_approvals
            (id,execution_id,step_run_id,task_id,organization_id,department_id,workflow_revision,status,
             config_json,subjects_json,report,created_at,expires_at) VALUES
            ('gate','exec','step','task','own','own',1,'PENDING',?,'[]','Review report',?,?)''',
            (json.dumps({'kind': 'report', 'merge_after_approval': False}), now, (datetime.now() + timedelta(hours=1)).isoformat()))
    app = FastAPI()
    app.dependency_overrides[get_db_manager] = lambda: db
    app.include_router(router, prefix='/api/v1/workflows', dependencies=[Depends(authenticate_request)])
    with TestClient(app) as client:
        yield db, client


def headers(user):
    org = 'foreign' if user.startswith('foreign') else 'own'
    return {'Authorization': 'Bearer ' + create_access_token({'sub': user, 'org_id': org, 'role': 'ORG_ADMIN'})}


def test_approval_is_owned_requires_manager_and_records_real_actor(state):
    db, client = state
    path = '/api/v1/workflows/executions/exec/approval'
    assert client.get(path, headers=headers('foreignORG_ADMIN')).status_code == 404
    assert client.post(path, headers=headers('ownMEMBER'), json={'approve': True}).status_code == 404
    assert client.post(path, headers=headers('ownMANAGER'), json={'approve': True, 'resolved_by': 'forged'}).status_code == 422
    response = client.post(path, headers=headers('ownMANAGER'), json={'approve': True})
    assert response.status_code == 202, response.text
    result = client.get(path, headers=headers('ownORG_ADMIN')).json()
    assert result['status'] == 'APPROVED' and result['resolved_by'] == 'ownMANAGER'
    assert db.get_workflow_execution('exec').status == 'COMPLETED'
    assert db.get_task_run('task').status == TaskStatus.COMPLETED
    assert client.post(path, headers=headers('ownORG_ADMIN'), json={'approve': True}).status_code == 409


def test_expiry_and_revision_change_cannot_approve(state):
    db, client = state
    with db._get_connection() as conn:
        conn.execute("UPDATE workflow_approvals SET expires_at='2000-01-01' WHERE id='gate'")
    path = '/api/v1/workflows/executions/exec/approval'
    assert client.post(path, headers=headers('ownORG_ADMIN'), json={'approve': True}).status_code == 409
    assert client.get(path, headers=headers('ownORG_ADMIN')).json()['status'] == 'EXPIRED'
    assert db.get_workflow_execution('exec').status == 'FAILED'


def test_explicit_merge_grant_never_inherits_wildcard(state):
    db, _ = state
    db.save_mcp_connector({'id': 'github', 'name': 'GitHub', 'provider': 'github', 'status': 'CONNECTED',
        'organization_id': 'own', 'configuration': {'token': 'fixture-not-a-real-token', 'allowed_repos': ['owner/repo']}})
    tool = db.save_mcp_tool({'id': 'reviewtool', 'connector_id': 'github', 'name': 'get_pull_request_review', 'description': 'Review'})
    approval = {'execution_id': 'exec', 'organization_id': 'own', 'department_id': 'own', 'workflow_revision': 1}
    subject = {'repository': 'owner/repo', 'connector_id': 'github', 'agent_id': 'agent', 'tool_id': tool.id}
    db.grant_department_mcp_access('own', 'github', allowed_tools=['*'], organization_id='own')
    with pytest.raises(ToolAccessError, match='explicit'):
        authorize_subject(db, approval, subject, merge=True)
    db.grant_department_mcp_access('own', 'github', allowed_tools=['get_pull_request_review', 'merge_pull_request'], organization_id='own')
    assert authorize_subject(db, approval, subject, merge=True).id == 'github'
    db.update_user('ownORG_ADMIN', status='DISABLED')
    with pytest.raises(ToolAccessError, match='initiator'):
        authorize_subject(db, approval, subject, merge=True)
