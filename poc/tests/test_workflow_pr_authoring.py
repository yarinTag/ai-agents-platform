"""PR authoring contracts with real SQLite grants; no provider/Docker/model calls."""
import json
from types import SimpleNamespace
import pytest
from poc.tests.test_workflow_chat import setup
from backend.api.workflow_chat_models import ChatWorkflow
from backend.api.workflow_chat_policy import catalog, native_definition, validate_candidate
from integrations.repo_workspace import workspace_configuration
from runtime.direct_outcomes import final_outcome


def proposal():
    return ChatWorkflow.model_validate({'name': 'Version bump', 'steps': [{
        'key': 'create_pr', 'name': 'Create draft PR', 'agent_id': '__workflow_runner__',
        'prompt_template': 'Bump the version in the repository manifest.',
        'resources': [], 'required_outcome': 'pull_request',
        'workspace': {'connector_id': 'github', 'repository': 'team/allowed', 'mode': 'write',
                      'pr_title': 'Bump version'}}]})


def test_read_connector_or_wildcard_does_not_authorize_pr(setup):
    db, identity, _ = setup
    candidate = proposal()
    assert validate_candidate(candidate, catalog(db, identity, 'dept-chat'))
    db.grant_department_mcp_access('dept-chat', 'github', allowed_tools=['*'], organization_id='org-chat')
    resources = catalog(db, identity, 'dept-chat')
    github = next(item for item in resources['connectors'] if item['id'] == 'github')
    assert 'open_pull_request' not in github['workspace_operations']
    assert validate_candidate(candidate, resources)


def test_explicit_workspace_grants_create_native_workspace_not_connector_scope(setup):
    db, identity, _ = setup
    db.grant_department_mcp_access('dept-chat', 'github',
        allowed_tools=['clone_repository', 'open_pull_request'], organization_id='org-chat')
    resources = catalog(db, identity, 'dept-chat')
    candidate = proposal()
    assert validate_candidate(candidate, resources) == []
    native = native_definition(candidate, resources, runner_agent_id='wf-agent-new')
    step = native['steps'][0]
    assert step['agent_id'] == 'wf-agent-new'
    assert step['mcp_servers'] == []
    assert step['params']['workspace']['mode'] == 'write'
    assert step['params']['required_outcome'] == 'pull_request'
    assert 'authorized_resources' not in step['params']
    assert native['mcp_servers'] == ['github']
    db.revoke_department_mcp_access('dept-chat', 'github')
    assert validate_candidate(candidate, catalog(db, identity, 'dept-chat'))


def test_required_pr_rejects_missing_or_read_workspace():
    for workspace in (None, {'connector_id': 'github', 'repository': 'team/allowed', 'mode': 'read'}):
        step = SimpleNamespace(params={'required_outcome': 'pull_request', 'workspace': workspace}, mcp_servers=[])
        with pytest.raises(ValueError, match='write repository workspace'):
            workspace_configuration(step)


def test_blocked_or_unstructured_final_answer_is_not_completion():
    output, error = final_outcome(json.dumps({'status': 'blocked', 'output': 'Read activity only.',
                                            'blocker': 'No write tools are available.'}))
    assert output is None and 'No write tools' in error
    assert final_outcome('I cannot create this PR.')[0] is None
    assert final_outcome(json.dumps({'status': 'completed', 'output': 'Done', 'blocker': 'Missing permission'}))[0] is None
    assert final_outcome(json.dumps({'status': 'completed', 'output': 'Summary', 'blocker': None})) == ('Summary', None)
