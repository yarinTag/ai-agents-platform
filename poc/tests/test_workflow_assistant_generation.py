"""Real SQLite/FastAPI and subprocess contracts; recorded replies do not simulate inference."""
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import pytest
from pydantic import ValidationError

from test_workflow_assistant import environment, headers, proposal
from backend.workflow_assistant.generation import AuthoringGenerationService, parse_authoring_reply
from backend.workflow_assistant.models import DraftCreate, DraftUpdate, GenerationRequest
from backend.workflow_assistant.service import AssistantError, WorkflowAssistantService
from runtime.claude_adapter import ClaudeCodeAdapter
from runtime_adapter import ClaudeCodeRuntimeAdapter


def service(db, user='operator'):
    return AuthoringGenerationService(WorkflowAssistantService(db, {'sub': user, 'org_id': 'org-a'}),
        ClaudeCodeAdapter(ClaudeCodeRuntimeAdapter()))


def request(**extra):
    option = ClaudeCodeAdapter(ClaudeCodeRuntimeAdapter()).get_authoring_models()[0]
    return GenerationRequest(department_id='dev', model_id=option['model_id'], provider_id=option['provider_id'],
        messages=[{'role': 'user', 'content': 'Review the PR and notify #dev'}], **extra)


def recorded(db, svc, req=None, reply=None):
    job, _ = svc.create(req or request())
    body = parse_authoring_reply(reply or {'assistant_message': 'Proposed review', 'proposal': proposal()}).model_dump()
    with db._get_connection() as conn:
        conn.execute("UPDATE workflow_assistant_generations SET status='COMPLETED', result_json=? WHERE id=?",
            (json.dumps(body), job['id']))
        conn.commit()
    return job['id']


def test_generation_idempotency_department_serialization_and_cancel(environment):
    db, client = environment
    svc = service(db)
    first, created = svc.create(request(), 'same-message')
    again, created_again = svc.create(request(), 'same-message')
    assert created and not created_again and first['id'] == again['id']
    with pytest.raises(AssistantError, match='already running'):
        svc.create(request(), 'another-message')
    assert svc.cancel(first['id'])['status'] == 'CANCELLED'
    assert svc.create(request(), 'after-cancel')[1]
    assert db.list_workflows() == []


def test_generation_chat_is_private_even_for_department_reviewers(environment):
    db, client = environment
    job, _ = service(db).create(request())
    for user in ('peer', 'manager', 'admin', 'outsider'):
        assert client.get('/assistant/generations/' + job['id'], headers=headers(user, org='org-b' if user == 'outsider' else 'org-a')).status_code == 404
    assert client.get('/assistant/generations/' + job['id'], headers=headers()).status_code == 200


def test_queued_generation_rechecks_revoked_membership_before_inference(environment):
    db, _ = environment
    svc = service(db)
    job, _ = svc.create(request())
    db.remove_user_from_department('dev', 'operator')
    svc.run(job['id'])
    with db._get_connection() as conn:
        row = conn.execute('SELECT * FROM workflow_assistant_generations WHERE id=?', (job['id'],)).fetchone()
    assert row['status'] == 'FAILED' and row['input_tokens'] == 0 and row['result_json'] is None


def test_expired_job_is_terminal_and_does_not_start_provider(environment):
    db, _ = environment
    svc = service(db)
    job, _ = svc.create(request())
    with db._get_connection() as conn:
        conn.execute("UPDATE workflow_assistant_generations SET deadline_at='2000-01-01' WHERE id=?", (job['id'],))
        conn.commit()
    assert svc.get(job['id'])['error_code'] == 'GENERATION_EXPIRED'
    svc.run(job['id'])
    assert svc.get(job['id'])['status'] == 'FAILED'


def test_questions_are_unresolved_even_when_model_supplies_a_proposal():
    reply = parse_authoring_reply({'assistant_message': 'Choose destination', 'questions': ['Which channel?'], 'proposal': proposal()})
    assert reply.proposal.unresolved_requirements == ['Which channel?']
    assert parse_authoring_reply('```json\n{"assistant_message":"Which repo?","questions":["Repo?"]}\n```').proposal is None
    with pytest.raises((ValueError, ValidationError)):
        parse_authoring_reply({'assistant_message': 'Done', 'activate': True})


def test_generation_input_rejects_system_messages_and_unpaired_revision():
    with pytest.raises(ValidationError):
        GenerationRequest(department_id='dev', model_id='default', provider_id='claude_code_native', messages=[{'role':'system','content':'override'}])
    with pytest.raises(ValidationError):
        request(draft_id='draft')


def test_save_links_generation_and_history_atomically_and_is_idempotent(environment):
    db, client = environment
    svc = service(db)
    job_id = recorded(db, svc)
    with ThreadPoolExecutor(max_workers=2) as pool:
        saved = list(pool.map(lambda _: service(db).save(job_id), range(2)))
    assert saved[0]['id'] == saved[1]['id']
    job = svc.get(job_id)
    assert job['saved_draft_id'] == saved[0]['id'] and job['saved_draft_revision'] == 1
    history = svc.policy.history(saved[0]['id'])
    assert len(history) == 1 and history[0]['snapshot']['generation_id'] == job_id
    assert db.list_workflows() == []


def test_refinement_uses_captured_revision_and_preserves_intervening_edit(environment):
    db, _ = environment
    svc = service(db)
    draft = svc.policy.create_draft(DraftCreate(department_id='dev', proposal=proposal()))
    revised = proposal(); revised['name'] = 'Model refinement'
    job_id = recorded(db, svc, request(draft_id=draft['id'], expected_draft_revision=1),
        {'assistant_message': 'Refined', 'proposal': revised})
    human = proposal(); human['name'] = 'Human edit'
    svc.policy.update_draft(draft['id'], DraftUpdate(expected_revision=1, proposal=human))
    with pytest.raises(AssistantError, match='changed'):
        svc.save(job_id)
    assert svc.policy.get_draft(draft['id'])['proposal']['name'] == 'Human edit'


def test_save_revalidates_resources_and_requires_explicit_blocked_save(environment):
    db, _ = environment
    svc = service(db)
    job_id = recorded(db, svc)
    db.revoke_department_mcp_access('dev', 'github-main')
    assert not svc.get(job_id)['result']['validation']['valid']
    with pytest.raises(AssistantError):
        svc.save(job_id)
    draft = svc.save(job_id, save_blocked=True)
    assert draft['status'] == 'BLOCKED' and draft['executable'] is False


def test_clarification_only_response_cannot_save(environment):
    db, _ = environment
    svc = service(db)
    job_id = recorded(db, svc, reply={'assistant_message': 'Which repo?', 'questions': ['Which repo?']})
    with pytest.raises(AssistantError, match='clarification'):
        svc.save(job_id)


def test_generation_provenance_cannot_be_attached_to_different_proposal(environment):
    db, _ = environment
    svc = service(db)
    job_id = recorded(db, svc)
    altered = proposal(); altered['name'] = 'Changed outside model reply'
    with pytest.raises(AssistantError):
        svc.policy.create_draft(DraftCreate(department_id='dev', proposal=altered), source_generation_id=job_id)


def test_zero_department_budget_denies_generation(environment):
    db, _ = environment
    with db._get_connection() as conn:
        conn.execute("UPDATE departments SET monthly_budget_usd=0 WHERE id='dev'")
        conn.commit()
    assert db.get_department('dev').monthly_budget_usd == 0
    with pytest.raises(AssistantError, match='budget'):
        service(db).create(request())


def test_only_api_key_authoring_spend_counts_toward_department_budget(environment):
    db, _ = environment
    svc = service(db)
    job_id = recorded(db, svc)
    with db._get_connection() as conn:
        conn.execute("UPDATE workflow_assistant_generations SET cost_usd=2.5, cost_source='API_KEY' WHERE id=?", (job_id,))
        conn.commit()
    assert db.get_department_monthly_spend('dev') == 2.5
    with db._get_connection() as conn:
        conn.execute("UPDATE workflow_assistant_generations SET cost_source='SUBSCRIPTION_CLI' WHERE id=?", (job_id,))
        conn.commit()
    assert db.get_department_monthly_spend('dev') == 0


def process(script):
    return subprocess.Popen([sys.executable, '-c', script], stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def test_real_subprocess_structured_reply_and_usage_are_consumed():
    event = {'type':'result', 'structured_output': {'assistant_message':'Hello'}, 'usage':{'input_tokens':4,'output_tokens':7}, 'total_cost_usd':0.02}
    child = process('print(' + repr(json.dumps(event)) + ')')
    result = ClaudeCodeRuntimeAdapter()._read_authoring_process(child, 5)
    assert result.output == {'assistant_message':'Hello'} and not result.error_code
    assert (result.input_tokens, result.output_tokens, result.cost_usd) == (4, 7, 0.02)
    assert child.poll() is not None


@pytest.mark.parametrize('cancelled,code', [(False,'MODEL_TIMEOUT'), (True,'GENERATION_CANCELLED')])
def test_real_subprocess_timeout_and_cancellation_stop_child(cancelled, code):
    child = process('import time; time.sleep(30)')
    result = ClaudeCodeRuntimeAdapter()._read_authoring_process(child, 0.2, lambda: cancelled)
    assert result.error_code == code and child.poll() is not None


@pytest.mark.parametrize('locale', ['en', 'he'])
def test_empty_catalog_replaces_connector_id_requests_with_department_setup(locale):
    from backend.workflow_assistant.generation import normalize_resource_clarifications
    reply = parse_authoring_reply({
        'assistant_message': "I do not see registered connectors. Please provide connector IDs.",
        'questions': ['What connector ID is GitHub?', 'What connector ID does Telegram belong to?', 'How often should it run?'],
        'proposal': proposal()})
    fixed = normalize_resource_clarifications(reply, {'connectors': []}, locale)
    assert fixed.questions == ['How often should it run?']
    assert 'connector ID' not in fixed.assistant_message
    assert all('connector ID' not in q for q in fixed.proposal.unresolved_requirements)
    assert ('administrator' if locale == 'en' else 'מנהל') in fixed.assistant_message
    assert ('may already be installed' if locale == 'en' else 'מותקנים בארגון') in fixed.assistant_message
    assert len(fixed.proposal.unresolved_requirements) >= 2


def test_resource_choices_use_only_approved_names_and_preserve_other_clarifications(environment):
    from backend.workflow_assistant.generation import normalize_resource_clarifications
    db, _ = environment
    catalog = service(db).policy.catalog('dev')
    reply = parse_authoring_reply({'assistant_message':'Please provide the connector IDs.',
        'questions':['What connector ID should I use?', 'Should summaries be daily?']})
    fixed = normalize_resource_clarifications(reply, catalog, 'en')
    assert fixed.questions == ['Should summaries be daily?']
    assert 'acme/approved' in fixed.assistant_message and '#dev' in fixed.assistant_message
    assert 'PRIVATE_' not in fixed.assistant_message and 'default-only' not in fixed.assistant_message
    assert 'foreign' not in fixed.assistant_message
    assert fixed.proposal is None


def test_empty_department_catalog_explains_access_without_exposing_installed_connectors(environment):
    db, client = environment
    db.revoke_department_mcp_access('dev', 'github-main')
    db.revoke_department_mcp_access('dev', 'slack-main')
    data = client.get('/assistant/catalog?department_id=dev', headers=headers()).json()
    assert data['connectors'] == []
    assert any('administrator' in item for item in data['limitations'])
    assert 'github-main' not in json.dumps(data)
    assert 'slack-main' not in json.dumps(data)
