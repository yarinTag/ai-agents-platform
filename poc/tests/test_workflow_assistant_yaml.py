"""Native YAML schema, real SQLite/FastAPI policy, and model-only request contracts."""
import json
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from test_workflow_assistant import environment, headers, proposal
from test_workflow_assistant_generation import service, request, recorded
from backend.workflow_assistant.generation import parse_model_reply, AuthoringGenerationService
from backend.workflow_assistant.models import GenerationRequest, WorkflowProposal, DraftCreate
from backend.workflow_assistant.yaml_contract import (document_to_proposal, load_workflow_yaml,
    proposal_artifact, workflow_schema)
from workflows.parser import WorkflowParser, validate_workflow_definition
from runtime.protocol import AuthoringModelSelection


def artifact():
    result = proposal_artifact(WorkflowProposal.model_validate(proposal()))
    assert result['yaml_error'] is None
    return result


def test_yaml_schema_file_matches_the_live_contract():
    path = Path(__file__).parents[1] / 'workflows' / 'workflow-authoring.schema.yaml'
    assert yaml.safe_load(path.read_text()) == workflow_schema()['schema']


def test_generated_yaml_is_runtime_native_and_semantically_round_trips():
    data = artifact()
    document = load_workflow_yaml(data['definition_yaml'])
    plan = document_to_proposal(document)
    assert plan == WorkflowProposal.model_validate(proposal())
    parsed = WorkflowParser.from_yaml(data['definition_yaml'])
    assert parsed.steps[1].depends_on == ['review']
    assert parsed.steps[1].params['channels'][0]['channel_id'] == '#dev'
    assert parsed.steps[0].mcp_servers == ['github-main']
    assert validate_workflow_definition(data['definition_json'])
    assert 'trigger' not in data['definition_json']


@pytest.mark.parametrize('kind,event', [('manual', 'manual'), ('webhook','webhook'), ('cron','cron'), ('channel','channel_message')])
def test_all_supported_trigger_shapes_preserve_meaning(kind, event):
    data = proposal()
    data['trigger'] = {'kind':kind}
    if kind == 'cron': data['trigger']['cron_expression'] = '0 9 * * *'
    if kind == 'channel': data['trigger'].update(connector_id='slack-main', channel_id='#dev', event='message')
    plan = WorkflowProposal.model_validate(data)
    result = proposal_artifact(plan)
    assert result['yaml_error'] is None
    assert result['definition_json']['triggers'][0]['event'] == event
    assert document_to_proposal(load_workflow_yaml(result['definition_yaml'])) == plan


def test_native_flow_dependencies_are_not_lost():
    data = artifact()['definition_json']
    data['steps'][1]['depends_on'] = []
    data['flow'] = [{'from':'review', 'to':'notify'}]
    parsed = load_workflow_yaml(yaml.safe_dump(data))
    assert document_to_proposal(parsed).steps[1].depends_on == ['review']


@pytest.mark.parametrize('mutation', ['cycle','unknown_dependency','unknown_flow','duplicate_key','mcp_mismatch','unapproved_extra','unexpected_trigger_field','webhook_mismatch'])
def test_invalid_native_workflows_are_rejected_without_silent_field_loss(mutation):
    data = artifact()['definition_json']
    if mutation == 'cycle': data['steps'][0]['depends_on'] = ['notify']
    elif mutation == 'unknown_dependency': data['steps'][0]['depends_on'] = ['missing']
    elif mutation == 'unknown_flow': data['flow'] = [{'from':'missing','to':'review'}]
    elif mutation == 'duplicate_key': data['steps'][1]['key'] = 'review'
    elif mutation == 'mcp_mismatch': data['steps'][0]['mcp_servers'] = []
    elif mutation == 'unapproved_extra': data['steps'][0]['params']['shell_command'] = 'echo bypass'
    elif mutation == 'unexpected_trigger_field': data['cron_expression'] = '0 9 * * *'
    elif mutation == 'webhook_mismatch': data['webhook_enabled'] = True
    with pytest.raises(ValueError):
        load_workflow_yaml(yaml.safe_dump(data))


@pytest.mark.parametrize('content', ['name: first\nname: second', 'name: &x []\nsteps: *x', '!!python/object/apply:os.system [echo unsafe]', 'name: 1\n---\nname: 2'])
def test_yaml_duplicate_keys_aliases_unsafe_tags_and_multiple_documents_fail(content):
    with pytest.raises(ValueError): load_workflow_yaml(content)


def test_native_yaml_policy_checks_and_scope_are_not_bypassed(environment):
    db, client = environment
    data = artifact()
    response = client.post('/assistant/validate-yaml', headers=headers(), json={'department_id':'dev','yaml_content':data['definition_yaml']})
    assert response.status_code == 200 and response.json()['validation']['valid']
    assert client.post('/assistant/validate-yaml', headers=headers('viewer'), json={'department_id':'dev','yaml_content':data['definition_yaml']}).status_code == 200
    assert client.post('/assistant/validate-yaml', headers=headers(), json={'department_id':'foreign','yaml_content':data['definition_yaml']}).status_code == 404
    db.revoke_department_mcp_access('dev','github-main')
    result = client.post('/assistant/validate-yaml', headers=headers(), json={'department_id':'dev','yaml_content':data['definition_yaml']}).json()
    assert not result['validation']['valid']
    assert any(e['code']=='CONNECTOR_NOT_ALLOWED' for e in result['validation']['errors'])
    assert db.list_workflows() == []


def test_yaml_invalid_returns_422_and_schema_requires_login(environment):
    _, client = environment
    assert client.get('/assistant/workflow-schema').status_code == 401
    assert client.get('/assistant/workflow-schema',headers=headers()).json()['workflow_schema_version'] == 1
    response = client.post('/assistant/validate-yaml', headers=headers(), json={'department_id':'dev','yaml_content':'name: broken'})
    assert response.status_code == 422 and response.json()['detail']['code'] == 'WORKFLOW_YAML_INVALID'


def test_authoring_model_choices_and_requests_do_not_depend_on_an_agent(environment):
    db, client = environment
    context = client.get('/assistant/context',headers=headers()).json()
    assert context['authoring_models'] and 'planner_agent_id' not in context
    agent = db.get_agent('engineer'); agent.department_id = 'finance'; db.save_agent(agent)
    assert service(db).policy.catalog('dev')['agents'] == []
    before = len(db.list_agents())
    created, _ = service(db).create(request())
    assert created['status'] == 'QUEUED'
    assert 'planner_agent_id' not in created['request'] and 'planner_agent_id' not in created
    assert len(db.list_agents()) == before


def test_arbitrary_model_provider_and_old_agent_selection_cannot_start_generation(environment):
    db, client = environment
    body = request().model_dump()
    for field, value in [('model_id','--permission-mode=bypassPermissions'),('provider_id','unconfigured-provider')]:
        invalid = {**body, field:value}
        with pytest.raises(ValueError, match='configured provider'):
            service(db).create(GenerationRequest.model_validate(invalid))
    response = client.post('/assistant/generations', headers=headers(), json={**body,'planner_agent_id':'engineer'})
    assert response.status_code == 422
    assert not any(row for row in db.list_workflows())


def test_legacy_generations_remain_readable_without_reusing_agent_authority(environment):
    db, _ = environment
    svc = service(db)
    created, _ = svc.create(request())
    legacy = request().model_dump(exclude={'model_id','provider_id'}) | {'planner_agent_id':'engineer'}
    with db._get_connection() as conn:
        conn.execute('UPDATE workflow_assistant_generations SET request_json=? WHERE id=?',(json.dumps(legacy),created['id']))
        conn.commit()
    job = svc.get(created['id'])
    assert job['request']['provider_id'] == 'legacy' and 'planner_agent_id' not in job['request']
    svc.run(created['id'])
    assert svc.get(created['id'])['error_code'] == 'AUTHORING_MODEL_NOT_ALLOWED'


def test_model_output_references_a_validated_candidate_instead_of_rewriting_yaml():
    validation_id = 'wfc_' + 'a' * 32
    reply = parse_model_reply({'assistant_message': 'Proposed workflow', 'validation_id': validation_id})
    assert reply.validation_id == validation_id
    assert parse_model_reply({'assistant_message': 'Which schedule?', 'validation_id': None}).validation_id is None
    with pytest.raises(ValidationError):
        parse_model_reply({'assistant_message': 'Done', 'proposal': proposal()})
    with pytest.raises(ValidationError):
        parse_model_reply({'assistant_message': 'Done', 'workflow': artifact()['definition_json']})
    with pytest.raises(ValidationError):
        parse_model_reply({'assistant_message': 'Done', 'validation_id': 'arbitrary-resource-id'})


def test_draft_and_history_expose_same_yaml_without_creating_live_workflow(environment):
    db, _ = environment
    svc = service(db)
    draft = svc.policy.create_draft(DraftCreate(department_id='dev',proposal=proposal()))
    assert draft['definition_yaml']
    history = svc.policy.history(draft['id'])
    assert history[0]['snapshot']['definition_yaml'] == draft['definition_yaml']
    generated = recorded(db,svc)
    saved = svc.save(generated)
    assert saved['definition_yaml'] == svc.get(generated)['result']['definition_yaml']
    assert db.list_workflows() == []


def test_final_candidate_requires_current_session_tools_and_matching_stored_hash():
    from backend.workflow_assistant.generation import verify_authoring_tool_usage
    from backend.workflow_assistant.service import AssistantError, _hash
    plan = WorkflowProposal.model_validate(proposal())
    validation_id = 'wfc_' + 'a' * 32
    reply = parse_model_reply({'assistant_message': 'Proposed', 'validation_id': validation_id})
    calls = [{'tool_name': 'workflow_catalog'}, {'tool_name': 'workflow_schema'},
             {'tool_name': 'validate_workflow_yaml', 'validation_id': validation_id,
              'proposal_json': plan.model_dump_json(), 'proposal_hash': _hash(plan.model_dump())}]
    assert verify_authoring_tool_usage(reply, calls) == plan
    with pytest.raises(AssistantError, match='catalog and schema'):
        verify_authoring_tool_usage(reply, calls[1:])
    with pytest.raises(AssistantError, match='this authoring session'):
        verify_authoring_tool_usage(reply, calls[:2])
    other = reply.model_copy(update={'validation_id': 'wfc_' + 'b' * 32})
    with pytest.raises(AssistantError, match='this authoring session'):
        verify_authoring_tool_usage(other, calls)
    changed = plan.model_copy(update={'name': 'Tampered candidate'})
    altered_calls = [*calls[:2], {**calls[-1], 'proposal_json': changed.model_dump_json()}]
    with pytest.raises(AssistantError, match='integrity'):
        verify_authoring_tool_usage(reply, altered_calls)
    clarification = parse_model_reply({'assistant_message': 'Which schedule?', 'validation_id': None})
    assert verify_authoring_tool_usage(clarification, calls[:2]) is None


def test_schema_rejects_yaml_scalar_coercion_and_oversized_input():
    data = artifact()['definition_json']
    data['steps'][0]['timeout_seconds'] = '180'
    with pytest.raises(ValidationError):
        load_workflow_yaml(yaml.safe_dump(data))
    with pytest.raises(ValueError,match='200 KB'):
        load_workflow_yaml('name: '+('x' * 200001))


def test_runtime_rejects_unlisted_model_before_launching_a_process():
    from runtime_adapter import ClaudeCodeRuntimeAdapter
    adapter = ClaudeCodeRuntimeAdapter()
    result = adapter.infer_authoring(AuthoringModelSelection('--tools=Bash','unconfigured'), 'test', 'test', {})
    assert result.error_code == 'AUTHORING_MODEL_NOT_ALLOWED'
    assert adapter._processes == {}
