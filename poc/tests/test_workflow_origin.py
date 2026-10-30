"""Real SQLite origin resolution and persistent event isolation contracts."""
from datetime import datetime, timedelta
import json
import pytest
from persistence import DatabaseManager
from config import AgentConfig
from runtime.models import AgentRun, TaskStatus
from events.service import EventService
from events.bus import EventBus


@pytest.fixture
def db(tmp_path):
    db = DatabaseManager(str(tmp_path / 'origin.sqlite'))
    db.save_agent(AgentConfig(id='shared', name='Shared', description='Shared definition', system_prompt='Work'))
    db.create_workflow(id='wf', name='Workflow', definition_json='{}')
    db.create_workflow_execution(execution_id='execution', workflow_id='wf', trigger_type='MANUAL')
    base = datetime.now()
    for index, (run_id, parent, root) in enumerate([
        ('office', None, None), ('legacy-step', None, None),
        ('child', 'legacy-step', 'legacy-step'), ('grandchild', 'child', 'legacy-step')
    ]):
        db.save_task_run(AgentRun(run_id=run_id, agent_id='shared', project_id=None,
            prompt='work', status=TaskStatus.RUNNING, created_at=base + timedelta(seconds=index),
            parent_task_id=parent, root_task_id=root))
    with db._get_connection() as conn:
        conn.execute("""INSERT INTO workflow_step_runs
            (id, execution_id, step_key, agent_id, status, task_run_id)
            VALUES ('step', 'execution', 'work', 'shared', 'RUNNING', 'legacy-step')""")
        conn.commit()
    return db


def test_office_filter_precedes_limit_and_preserves_shared_agent(db):
    assert [run.run_id for run in db.list_task_runs(execution_scope='office', limit=1)] == ['office']
    assert {run.run_id for run in db.list_task_runs(execution_scope='workflow')} == {'legacy-step', 'child', 'grandchild'}
    assert len(db.list_task_runs()) == 4
    assert not db.get_agent('shared').is_workflow_agent


def test_lineage_resolves_legacy_steps_and_descendants(db):
    contexts = db.get_workflow_task_contexts()
    for run_id in ('legacy-step', 'child', 'grandchild'):
        assert contexts[run_id] == db.get_task_workflow_context(run_id)
        assert contexts[run_id]['workflow_execution_id'] == 'execution'
    assert db.get_task_workflow_context('office') == {}
    assert db.get_task_workflow_context('missing') == {}


def test_runtime_events_are_tagged_without_mutating_caller(db):
    service = EventService(db, EventBus())
    payload = {'status': 'running'}
    event = service.emit('task_started', payload, agent_id='shared', task_id='grandchild')
    assert event.payload['workflow_execution_id'] == 'execution'
    assert payload == {'status': 'running'}
    assert service.get_events(task_id='grandchild')[0].payload['workflow_id'] == 'wf'
    assert 'workflow_execution_id' not in service.emit('task_started', {}, task_id='office').payload


def test_invalid_scope_is_rejected(db):
    with pytest.raises(ValueError, match='scope'):
        db.list_task_runs(execution_scope='invalid')


def test_task_api_scopes_snapshots_and_returns_workflow_identity(db):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.api.tasks import router
    from backend.dependencies import get_db_manager, get_runtime_adapter
    from runtime.claude_adapter import ClaudeCodeAdapter
    from runtime_adapter import ClaudeCodeRuntimeAdapter
    app = FastAPI()
    app.include_router(router, prefix='/tasks')
    app.dependency_overrides[get_db_manager] = lambda: db
    runtime = ClaudeCodeAdapter(ClaudeCodeRuntimeAdapter())
    app.dependency_overrides[get_runtime_adapter] = lambda: runtime
    with TestClient(app) as client:
        office = client.get('/tasks/?execution_scope=office&limit=1')
        assert office.status_code == 200
        assert [task['id'] for task in office.json()] == ['office']
        workflow = client.get('/tasks/?execution_scope=workflow')
        assert workflow.status_code == 200
        assert {task['workflow_execution_id'] for task in workflow.json()} == {'execution'}
        assert len(client.get('/tasks/').json()) == 4
        assert client.get('/tasks/?execution_scope=invalid').status_code == 422


def test_history_stream_enriches_legacy_events_and_activity_filters_office(db):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.events.router import router
    from backend.dependencies import get_db_manager, get_event_service, get_event_bus
    from events.models import PlatformEvent
    bus = EventBus()
    service = EventService(db, bus)
    db.save_event(PlatformEvent(event_type='task_started', task_id='child', payload={}))
    app = FastAPI()
    app.include_router(router, prefix='/events')
    app.dependency_overrides[get_db_manager] = lambda: db
    app.dependency_overrides[get_event_service] = lambda: service
    app.dependency_overrides[get_event_bus] = lambda: bus
    with TestClient(app) as client:
        response = client.get('/events/stream?after_sequence=0&live=false')
        assert response.status_code == 200
        assert '"workflow_execution_id": "execution"' in response.text
        response = client.get('/events/system/recent-activity?execution_scope=office&limit=1')
        assert response.status_code == 200
        assert [row['entity_id'] for row in response.json()['activity']] == ['office']
        assert client.get('/events/system/recent-activity?execution_scope=bad').status_code == 422
