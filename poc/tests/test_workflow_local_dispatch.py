"""Real FastAPI/SQLite local-dispatch contracts. No broker or model calls.

Use --noconftest when verification is authorized.
"""
import json
from fastapi import FastAPI
from fastapi.testclient import TestClient
from persistence import DatabaseManager
from workflows.engine import WorkflowEngine
from workflows.sandbox import SandboxManager
from backend.api.workflows_execution import router
from backend.dependencies import get_workflow_engine


def test_local_dispatch_returns_promptly_and_records_real_failure_without_runtime(tmp_path):
    db = DatabaseManager(str(tmp_path / 'dispatch.db'))
    db.max_agents = 100
    db.create_workflow(id='wf_local', name='Local', definition_json=json.dumps({
        'name': 'Local', 'steps': [{'key': 'work', 'name': 'Work', 'agent_id': 'local-test-agent',
            'prompt_template': 'Do the requested work.'}]}))
    engine = WorkflowEngine(db_manager=db, sandbox_manager=SandboxManager(base_sandboxes_dir=str(tmp_path / 'sandboxes')))
    app = FastAPI()
    app.include_router(router, prefix='/api/v1/workflows')
    app.dependency_overrides[get_workflow_engine] = lambda: engine
    client = TestClient(app)
    response = client.post('/api/v1/workflows/wf_local/execute?use_queue=false&background=true', json={})
    assert response.status_code == 200, response.text
    assert response.json()['status'] == 'QUEUED'
    execution_id = response.json()['id']
    stored = db.get_workflow_execution(execution_id)
    assert stored.status == 'FAILED'
    assert 'Runtime capability is unavailable' in stored.error_message
    assert stored.total_input_tokens == stored.total_output_tokens == 0
    assert db.list_workflow_executions(workflow_id='wf_local')[0].id == execution_id
