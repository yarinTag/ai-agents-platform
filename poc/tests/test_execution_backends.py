"""Backend admission contracts: pure policy plus real SQLite. Never starts a model or Docker."""
import json
import pytest
from persistence import DatabaseManager
from runtime.execution_backends import (
    BACKENDS, BackendUnavailable, ExecutionBackend, backend_catalog, parse_backend, require_backend,
)
from workflows.backend_policy import backend_for_task, preflight_backends, step_backend
from workflows.parser import WorkflowParser, validate_workflow_definition
from workflows.settings import validate_settings


def definition(backend=None, override=None):
    data = {'name': 'Backend policy', 'steps': [{
        'key': 'work', 'agent_id': 'worker', 'prompt_template': 'Inspect files.', 'params': {}}]}
    if backend is not None:
        data['settings'] = {'execution_backend': backend}
    if override is not None:
        data['steps'][0]['params']['execution_backend'] = override
    return data


def test_legacy_workflows_keep_direct_api_and_catalog_is_not_live_detection():
    parsed = WorkflowParser.from_dict(definition())
    assert step_backend(validate_settings(parsed.settings), parsed.steps[0]) == ExecutionBackend.DIRECT_API
    preflight_backends(parsed)
    rows = backend_catalog()
    assert {row['id'] for row in rows} == {value.value for value in ExecutionBackend}
    assert all(row['verification'] == 'source_contract_only' for row in rows)
    assert next(row for row in rows if row['id'] == 'claude_code')['transport'] == 'claude_agent_sdk'
    with pytest.raises(TypeError):
        BACKENDS[ExecutionBackend.CLAUDE_CODE] = BACKENDS[ExecutionBackend.DIRECT_API]


@pytest.mark.parametrize('backend', ['claude_code', 'codex_cli', 'antigravity_cli'])
def test_known_backend_can_be_authored_but_never_falls_back_at_admission(backend):
    data = definition(backend)
    validate_workflow_definition(data)
    roundtrip = WorkflowParser.from_json(WorkflowParser.from_dict(data).to_json())
    assert roundtrip.settings['execution_backend'] == backend
    with pytest.raises(ValueError, match='Workflow step work:'):
        preflight_backends(roundtrip)
    with pytest.raises(ValueError):
        require_backend(backend, playground=True)


@pytest.mark.parametrize('value', ['', 'native', 'ant', 'direct_openai', [], {}])
def test_unknown_backends_are_not_silently_defaulted(value):
    with pytest.raises(ValueError):
        parse_backend(value)
    raw = definition()
    raw['steps'][0]['params']['execution_backend'] = value
    with pytest.raises(ValueError):
        validate_workflow_definition(raw)


def test_step_override_and_null_inheritance_are_explicit():
    parsed = WorkflowParser.from_dict(definition('claude_code', 'direct_api'))
    preflight_backends(parsed)
    parsed.steps[0].params['execution_backend'] = None
    with pytest.raises(ValueError, match='Claude'):
        preflight_backends(parsed)
    parsed = WorkflowParser.from_dict(definition('direct_api', 'codex_cli'))
    with pytest.raises(ValueError, match='Codex CLI'):
        preflight_backends(parsed)


def test_later_pending_step_blocks_entire_workflow_preflight():
    raw = definition()
    raw['steps'].append({'key': 'later', 'agent_id': 'worker', 'depends_on': ['work'],
        'params': {'execution_backend': 'antigravity_cli'}})
    with pytest.raises(ValueError, match='Workflow step later'):
        preflight_backends(WorkflowParser.from_dict(raw))


def test_deterministic_delivery_does_not_launch_agent_backend():
    parsed = WorkflowParser.from_dict(definition('claude_code'))
    parsed.steps[0].params['channel_action'] = {'action': 'send_channel_message'}
    preflight_backends(parsed)  # Channel-action validation remains its own independent gate.


def test_task_backend_comes_from_persisted_step_identity(tmp_path):
    db = DatabaseManager(str(tmp_path / 'backends.db'))
    db.create_workflow(id='wf-policy', name='Policy', definition_json=json.dumps(definition('codex_cli')))
    db.create_workflow_execution(execution_id='exec-policy', workflow_id='wf-policy', trigger_type='MANUAL')
    record = dict(id='step-policy', execution_id='exec-policy', step_key='work', agent_id=None,
        status='QUEUED', task_run_id='wf_task_policy', input_data='', output_data=None,
        input_tokens=0, output_tokens=0, cost_usd=0, started_at=None, completed_at=None)
    db.save_workflow_step_run(record)
    assert backend_for_task(db, 'wf_task_policy') == ExecutionBackend.CODEX_CLI
    assert backend_for_task(db, 'ordinary-task') == ExecutionBackend.DIRECT_API
    with pytest.raises(ValueError, match='context is missing'):
        backend_for_task(db, 'wf_task_unknown')
    with db._get_connection() as conn:
        conn.execute("UPDATE workflow_step_runs SET step_key='missing' WHERE id='step-policy'")
    with pytest.raises(ValueError, match='step no longer exists'):
        backend_for_task(db, 'wf_task_policy')
