"""Explicit approval authority through real FastAPI, SQLite, engine and callbacks."""
import json

import pytest
from pydantic import ValidationError

from poc.tests.test_generic_governance_api import auth, baseline
from poc.tests.test_telegram_acceptance import gate
from storage import dag_approvals
from workflows.dag_approval_config import DagApprovalPolicy, approval_mode
from workflows.engine import WorkflowEngine
from workflows.parser import validate_workflow_definition


@pytest.mark.parametrize('mode', ['CONTINUATION', 'INDEPENDENT', None])
def test_saved_mode_controls_initiator_and_author_decision(baseline, mode):
    db, client = baseline
    policy = {} if mode is None else {'mode': mode}
    definition = {'name': 'Explicit policy', 'steps': [{
        'key': 'gate', 'agent_id': '__workflow_runner__', 'depends_on': [],
        'params': {'dag_approval': policy},
    }]}
    created = client.post('/api/v1/workflows', headers=auth('MANAGER'), json={
        'name': 'Explicit policy', 'department_id': 'atlas_engineering',
        'webhook_enabled': False, 'definition_json': json.dumps(definition),
    })
    assert created.status_code == 201, created.text
    workflow_id = created.json()['id']
    execution = WorkflowEngine(db_manager=db).execute_workflow(
        workflow_id, user_context={'sub': 'atlas_MANAGER', 'org_id': 'atlas'})
    assert execution.status == 'WAITING_APPROVAL'
    scope = {'department_id': 'atlas_engineering', 'execution_id': execution.id}
    item, = client.get('/api/v1/workflows/dag-approvals', headers=auth('MANAGER'), params=scope).json()['items']
    assert item['mode'] == (mode or 'INDEPENDENT')
    assert item['can_decide'] is (mode == 'CONTINUATION')
    path = f"/api/v1/workflows/dag-approvals/{item['id']}/decision"
    response = client.post(path, headers=auth('MANAGER'), params=scope, json={'approve': True})
    if mode != 'CONTINUATION':
        assert response.status_code == 403
        response = client.post(path, headers=auth(), params=scope, json={'approve': True})
    assert response.status_code == 200 and response.json()['status'] == 'APPROVED'
    resumed = WorkflowEngine(db_manager=db).execute_workflow(workflow_id, dag_approval_id=item['id'])
    assert resumed.status == 'COMPLETED'
    assert dag_approvals.claim_resume(db, item['id'], workflow_id, db.get_workflow(workflow_id).revision) is None
    assert client.post(path, headers=auth('MANAGER'), params=scope, json={'approve': True}).status_code == 409


@pytest.mark.parametrize('mode', ['CONTINUATION', 'INDEPENDENT'])
def test_revision_author_independence_is_explicit(baseline, mode):
    db, client = baseline
    workflow = db.create_workflow(id='author-mode', name='Author mode', organization_id='atlas',
        department_id='atlas_engineering', definition_json='{}')
    workflow = db.update_workflow(workflow.id, description='Authored', actor_id='atlas_MANAGER')
    db.create_workflow_execution('author-run', workflow.id, 'MANUAL', department_id=workflow.department_id)
    identifier = dag_approvals.suspend(db, execution_id='author-run', step_key='gate',
        revision=workflow.revision, initiator_id='atlas_OPERATOR',
        policy={**DagApprovalPolicy(mode=mode).model_dump(), 'quorum': 1},
        checkpoint={'outputs': {}, 'input_tokens': 0, 'output_tokens': 0, 'cost_usd': 0})
    r = client.post(f'/api/v1/workflows/dag-approvals/{identifier}/decision', headers=auth('MANAGER'),
                    params={'department_id': workflow.department_id}, json={'approve': True})
    assert r.status_code == (200 if mode == 'CONTINUATION' else 403)


@pytest.mark.parametrize('mode', ['CONTINUATION', 'INDEPENDENT', None])
def test_telegram_uses_same_frozen_mode_without_self_approval_bypass(gate, mode):
    db, _, workflow, identifier, _, post = gate
    with db._get_connection() as conn:
        row = conn.execute('SELECT policy_json FROM workflow_dag_approvals WHERE id=?', (identifier,)).fetchone()
        policy = json.loads(row[0])
        if mode is not None:
            policy['mode'] = mode
        conn.execute('UPDATE workflow_dag_approvals SET initiator_id=?,policy_json=? WHERE id=?',
                     ('atlas_MANAGER', json.dumps(policy), identifier))
    result = post()
    if mode == 'CONTINUATION':
        assert result == 'Decision recorded.'
        assert dag_approvals.claim_resume(db, identifier, workflow.id, workflow.revision)
        assert post(callback='124').startswith('Decision unavailable')
    else:
        assert result.startswith('Decision unavailable')
        assert dag_approvals.claim_resume(db, identifier, workflow.id, workflow.revision) is None


@pytest.mark.parametrize('case', ['role', 'inactive', 'quorum', 'invalid_mode'])
def test_continuation_never_grants_role_status_or_quorum(gate, case):
    db, _, workflow, identifier, _, post = gate
    with db._get_connection() as conn:
        policy = json.loads(conn.execute('SELECT policy_json FROM workflow_dag_approvals WHERE id=?', (identifier,)).fetchone()[0])
        policy['mode'] = 'CONTINUATION'
        if case == 'quorum':
            policy['quorum'] = 2
        elif case == 'invalid_mode':
            policy['mode'] = 'allow_anyone'
        conn.execute('UPDATE workflow_dag_approvals SET policy_json=? WHERE id=?', (json.dumps(policy), identifier))
    if case == 'inactive':
        db.update_user('atlas_MANAGER', status='INACTIVE')
    result = post(sender=34567 if case == 'role' else 12345)
    assert result == 'Decision recorded.' if case == 'quorum' else result.startswith('Decision unavailable')
    assert dag_approvals.claim_resume(db, identifier, workflow.id, workflow.revision) is None


@pytest.mark.parametrize('invalid', [{'mode': 'anything'}, {'mode': True}, {'separate_initiator': False},
    {'mode': 'CONTINUATION', 'separate_initiator': True}])
def test_policy_rejects_ambiguous_or_legacy_opt_out(invalid):
    with pytest.raises(ValidationError):
        DagApprovalPolicy.model_validate(invalid)
    with pytest.raises(ValueError):
        approval_mode(invalid)


def test_protected_write_cannot_select_continuation_in_native_definition():
    definition = {'name': 'Protected write', 'steps': [
        {'key': 'approval', 'agent_id': 'agent', 'params': {'dag_approval': {'mode': 'CONTINUATION'}}},
        {'key': 'write', 'agent_id': 'agent', 'depends_on': ['approval'], 'mcp_servers': ['github'],
         'params': {'authorized_resources': [{'connector_id': 'github', 'repository': 'team/repo',
                                             'tool_name': 'comment_pull_request'}],
                    'pr_write_approval': {'connector_id': 'github', 'approval_step': 'approval',
                        'intent': {'operation': 'comment_pull_request', 'arguments': {
                            'repository': 'team/repo', 'pull_number': 1, 'head_sha': 'a' * 40, 'body': 'Review.'}}}}},
    ]}
    with pytest.raises(ValueError, match='INDEPENDENT'):
        validate_workflow_definition(definition)
    definition['steps'][0]['params']['dag_approval']['mode'] = 'INDEPENDENT'
    validate_workflow_definition(definition)


def test_sensitive_checkpoint_cannot_be_suspended_or_replayed_as_continuation(gate):
    db, _, workflow, identifier, _, post = gate
    with db._get_connection() as conn:
        policy = json.loads(conn.execute('SELECT policy_json FROM workflow_dag_approvals WHERE id=?', (identifier,)).fetchone()[0])
        policy['mode'] = 'CONTINUATION'
        conn.execute('UPDATE workflow_dag_approvals SET policy_json=?,checkpoint_json=? WHERE id=?',
            (json.dumps(policy), json.dumps({'outputs': {}, 'approved_pr_write': {'step_key': 'write'}}), identifier))
    assert post().startswith('Decision unavailable')
    assert dag_approvals.claim_resume(db, identifier, workflow.id, workflow.revision) is None
    with pytest.raises(dag_approvals.ApprovalConflict, match='INDEPENDENT'):
        dag_approvals.suspend(db, execution_id='other', step_key='approval', revision=1,
            initiator_id='atlas_MANAGER', policy=policy, checkpoint={'approved_pr_write': {'step_key': 'write'}})


def test_continuation_vote_is_revalidated_before_resume(gate):
    db, _, workflow, identifier, _, post = gate
    with db._get_connection() as conn:
        policy = json.loads(conn.execute('SELECT policy_json FROM workflow_dag_approvals WHERE id=?', (identifier,)).fetchone()[0])
        policy['mode'] = 'CONTINUATION'
        conn.execute('UPDATE workflow_dag_approvals SET policy_json=? WHERE id=?', (json.dumps(policy), identifier))
    assert post() == 'Decision recorded.'
    db.update_user('atlas_MANAGER', status='INACTIVE')
    assert dag_approvals.claim_resume(db, identifier, workflow.id, workflow.revision) is None


@pytest.mark.parametrize('mode', ['CONTINUATION', 'INDEPENDENT'])
def test_chat_and_card_preserve_and_explain_policy(mode):
    from backend.api.workflow_chat_models import ChatWorkflow
    from backend.api.workflow_chat_policy import native_definition
    from integrations.telegram_approval_cards import card_content

    candidate = ChatWorkflow.model_validate({'name': 'Pause', 'steps': [{
        'key': 'gate', 'name': 'Gate', 'agent_id': 'agent', 'prompt_template': 'Pause for confirmation.',
        'approval_checkpoint': {'mode': mode, 'expires_hours': 2},
    }]})
    native = native_definition(candidate, {'connectors': []})
    policy = native['steps'][0]['params']['dag_approval']
    assert policy == {'mode': mode, 'timeout_seconds': 7200}
    row = {'step_key': 'gate', 'expires_at': 2000000000, 'policy_json': json.dumps(policy),
           'checkpoint_json': '{}'}
    text, _ = card_content(row, 'PENDING:0/1', None)
    assert ('eligible initiator/author may approve' if mode == 'CONTINUATION'
            else 'another eligible person must approve') in text


def test_claimed_protected_write_rechecks_mode_before_tool_scope(gate):
    from integrations.tool_definitions import ToolAccessError
    from workflows.pr_write_approval import PRWriteApproval, execute_approved_write
    from workflows.parser import WorkflowStepDefinition

    db, _, _, identifier, _, _ = gate
    config = PRWriteApproval.model_validate({'connector_id': 'github', 'approval_step': 'gate',
        'intent': {'operation': 'comment_pull_request', 'arguments': {
            'repository': 'team/repo', 'pull_number': 1, 'head_sha': 'a' * 40, 'body': 'Review.'}}})
    step = WorkflowStepDefinition(key='write', name='Write', agent_id='agent', prompt_template='')
    with db._get_connection() as conn:
        policy = json.loads(conn.execute('SELECT policy_json FROM workflow_dag_approvals WHERE id=?', (identifier,)).fetchone()[0])
        policy['mode'] = 'CONTINUATION'
        checkpoint = {'approved_pr_write': {'step_key': 'write', 'fingerprint': config.fingerprint('write')}}
        conn.execute("UPDATE workflow_dag_approvals SET status='CLAIMED',policy_json=?,checkpoint_json=? WHERE id=?",
                     (json.dumps(policy), json.dumps(checkpoint), identifier))
        conn.execute("UPDATE workflow_executions SET status='RUNNING' WHERE id='acceptance-run'")
    with pytest.raises(ToolAccessError, match='INDEPENDENT'):
        execute_approved_write(db, step, config, None, 'acceptance-run')
