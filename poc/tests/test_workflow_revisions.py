"""Workflow editing/history against real SQLite and FastAPI, without model calls."""
import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from backend.api.workflows import router
from backend.dependencies import get_db_manager
from persistence import DatabaseManager, WorkflowRevisionConflict


@pytest.fixture
def state(tmp_path):
    db = DatabaseManager(str(tmp_path / 'revisions.sqlite'))
    db.create_organization(id='org-a', name='A', slug='a')
    db.create_organization(id='org-b', name='B', slug='b')
    definition = {'id': 'wf', 'name': 'Original', 'steps': [
        {'key': 'first_step', 'agent_id': 'agent', 'prompt_template': 'Original prompt', 'depends_on': [],
         'custom_step_setting': {'keep': True}}],
        'metadata': {'custom': {'keep': True}}, 'runner_agent_id': 'wf-agent-wf',
        'custom_extension': {'keep': True}}
    db.create_workflow(id='wf', name='Original', definition_json=json.dumps(definition),
        description='Original description', cron_expression='0 9 * * *', organization_id='org-a',
        actor_id='creator', actor_label='Creator')
    app = FastAPI()
    @app.middleware('http')
    async def identity(request: Request, call_next):
        request.state.user = {'sub': 'editor', 'name': 'Editor', 'role': 'ORG_ADMIN',
                              'org_id': request.headers.get('x-test-org', 'org-a')}
        return await call_next(request)
    app.include_router(router, prefix='/workflows')
    app.dependency_overrides[get_db_manager] = lambda: db
    with TestClient(app) as client:
        yield db, client


def test_edit_preserves_identity_unspecified_settings_and_history(state):
    db, client = state
    token = db.get_workflow('wf').webhook_token
    response = client.put('/workflows/wf', json={'name': 'Edited', 'expected_revision': 1, 'change_summary': 'Rename'})
    assert response.status_code == 200, response.text
    assert response.json()['revision'] == 2
    assert response.json()['id'] == 'wf'
    assert response.json()['webhook_token'] == token
    assert response.json()['cron_expression'] == '0 9 * * *'
    assert response.json()['description'] == 'Original description'
    history = client.get('/workflows/wf/revisions').json()
    assert [item['revision'] for item in history] == [2, 1]
    assert history[0]['actor_id'] == 'editor'
    assert history[0]['actor_label'] == 'Editor'
    assert history[0]['changed_fields'] == ['name']
    assert history[0]['change_summary'] == 'Rename'
    assert history[1]['snapshot']['name'] == 'Original'
    assert 'webhook_token' not in history[0]['snapshot']


def test_yaml_roundtrip_keeps_unknown_fields_and_updates_in_place(state):
    db, client = state
    source = db.get_workflow('wf').definition_json
    converted = client.post('/workflows/convert-format', json={'json_content': source})
    assert converted.status_code == 200
    yaml_content = converted.json()['yaml_content'].replace('Original prompt', 'Revised prompt')
    response = client.put('/workflows/wf', json={'definition_yaml': yaml_content, 'expected_revision': 1})
    assert response.status_code == 200, response.text
    data = json.loads(response.json()['definition_json'])
    assert data['custom_extension'] == {'keep': True}
    assert data['metadata']['custom'] == {'keep': True}
    assert data['steps'][0]['custom_step_setting'] == {'keep': True}
    assert data['steps'][0]['prompt_template'] == 'Revised prompt'
    assert data['runner_agent_id'] == 'wf-agent-wf'
    assert len(db.list_workflows()) == 1


def test_noop_and_stale_revision_do_not_add_versions(state):
    db, client = state
    assert client.put('/workflows/wf', json={'name': 'Original', 'expected_revision': 1}).json()['revision'] == 1
    assert client.put('/workflows/wf', json={'name': 'New', 'expected_revision': 1}).status_code == 200
    assert client.put('/workflows/wf', json={'name': 'Stale', 'expected_revision': 1}).status_code == 409
    assert db.get_workflow('wf').name == 'New'
    assert len(db.list_workflow_revisions('wf')) == 2


@pytest.mark.parametrize('steps', [
    [{'key': 'a', 'depends_on': ['missing']}],
    [{'key': 'a', 'depends_on': ['b']}, {'key': 'b', 'depends_on': ['a']}],
    [{'key': 'a'}, {'key': 'a'}],
])
def test_invalid_graph_is_not_saved(state, steps):
    db, client = state
    response = client.put('/workflows/wf', json={'definition_json': json.dumps({'steps': steps}), 'expected_revision': 1})
    assert response.status_code == 400, response.text
    assert db.get_workflow('wf').revision == 1
    assert len(db.list_workflow_revisions('wf')) == 1


def test_history_and_edit_are_tenant_scoped(state):
    db, client = state
    headers = {'x-test-org': 'org-b'}
    assert client.get('/workflows/wf/revisions', headers=headers).status_code == 404
    assert client.put('/workflows/wf', json={'name': 'Wrong tenant'}, headers=headers).status_code == 404
    assert client.put('/workflows/wf', json={'organization_id': 'org-b'}).status_code == 403
    assert db.get_workflow('wf').revision == 1


def test_clear_schedule_and_description_are_versioned(state):
    db, client = state
    response = client.put('/workflows/wf', json={'cron_expression': None, 'description': '', 'expected_revision': 1})
    assert response.status_code == 200
    wf = db.get_workflow('wf')
    assert wf.cron_expression is None
    assert wf.description == ''
    assert set(db.list_workflow_revisions('wf')[0]['changed_fields']) == {'cron_expression', 'description'}


def test_concurrent_writers_cannot_overwrite_same_revision(state):
    db, client = state
    barrier = Barrier(2)
    def write(name):
        barrier.wait()
        try:
            db.update_workflow('wf', name=name, expected_revision=1)
            return 'saved'
        except WorkflowRevisionConflict:
            return 'conflict'
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(write, ['First editor', 'Second editor']))
    assert sorted(outcomes) == ['conflict', 'saved']
    assert len(db.list_workflow_revisions('wf')) == 2


def test_existing_workflow_migrates_to_baseline_and_history_paginates(state):
    db, client = state
    with db._get_connection() as conn:
        conn.execute('DELETE FROM workflow_revisions WHERE workflow_id = ?', ('wf',))
        conn.commit()
    migrated = DatabaseManager(str(db.db_path))
    assert migrated.list_workflow_revisions('wf')[0]['actor_label'] == 'Legacy baseline'
    for revision in range(1, 5):
        migrated.update_workflow('wf', name=f'Edit {revision}', expected_revision=revision)
    latest = client.get('/workflows/wf/revisions?limit=2').json()
    older = client.get('/workflows/wf/revisions?limit=2&before_revision=4').json()
    assert [item['revision'] for item in latest] == [5, 4]
    assert [item['revision'] for item in older] == [3, 2]


def test_channel_binding_changes_are_in_the_same_revision_history(state):
    db, client = state
    response = client.post('/workflows/wf/channel-binding', json={'provider': 'slack', 'channel_id': '#test'})
    assert response.status_code == 200
    assert response.json()['revision'] == 2
    response = client.delete('/workflows/wf/channel-binding')
    assert response.status_code == 200
    assert response.json()['revision'] == 3
    history = db.list_workflow_revisions('wf')
    assert [revision['change_summary'] for revision in history[:2]] == ['Channel binding removed', 'Channel binding updated']
    assert history[0]['actor_label'] == 'Editor'
    assert 'channel_binding' in json.loads(history[1]['snapshot']['definition_json'])['metadata']
    assert 'channel_binding' not in json.loads(history[0]['snapshot']['definition_json'])['metadata']


def test_api_creation_records_author_and_preserves_extensions(state):
    db, client = state
    response = client.post('/workflows', json={'name': 'Created in UI', 'definition_yaml':
        'name: Created in UI\nsteps: []\ncustom_extension: {keep: true}\n'})
    assert response.status_code == 201, response.text
    created = response.json()
    assert created['revision'] == 1
    assert json.loads(created['definition_json'])['custom_extension'] == {'keep': True}
    history = client.get(f"/workflows/{created['id']}/revisions").json()
    assert len(history) == 1
    assert history[0]['actor_id'] == 'editor'
    assert history[0]['change_summary'] == 'Workflow created'


def test_explicit_step_keys_keep_dependency_and_prompt_references():
    from workflows.parser import WorkflowParser
    workflow = WorkflowParser.from_dict({'name': 'Stable keys', 'steps': [
        {'key': 'pr_triage', 'prompt_template': 'Inspect input'},
        {'key': 'qa_review', 'depends_on': ['pr_triage'], 'prompt_template': '{{pr_triage.output}}'},
    ]})
    assert workflow.steps[0].key == 'pr_triage'
    assert workflow.steps[1].depends_on == [workflow.steps[0].key]
    assert workflow.steps[1].prompt_template == '{{pr_triage.output}}'


def test_execution_deduplication_is_separated_by_saved_revision():
    from workflows.engine import compute_execution_hash
    assert compute_execution_hash('wf', {'a': 1}, revision=1) != compute_execution_hash('wf', {'a': 1}, revision=2)
    assert compute_execution_hash('wf', {'b': 2, 'a': 1}, revision=2) == compute_execution_hash('wf', {'a': 1, 'b': 2}, revision=2)
