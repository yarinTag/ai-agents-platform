"""Playground contracts against real SQLite/FastAPI; no model calls or test doubles.
Run with --noconftest: the shared conftest resets the application's default database.
"""
import json

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from backend.api.workflows import router
from backend.dependencies import get_db_manager, get_workflow_engine
from persistence import DatabaseManager
from config import AgentConfig
from runtime.claude_adapter import ClaudeCodeAdapter
from runtime_adapter import ClaudeCodeRuntimeAdapter
from workflows.engine import WorkflowEngine, compute_execution_hash
from workflows.sandbox import SandboxManager


@pytest.fixture
def environment(tmp_path):
    db = DatabaseManager(str(tmp_path / "test.sqlite"))
    db.create_workflow(id="wf", name="Exercise", definition_json=json.dumps({
        "name": "Exercise", "steps": [{"key": "analyze", "agent_id": "missing",
        "prompt_template": "Analyze {{text}}"}]
    }))
    engine = WorkflowEngine(db_manager=db, sandbox_manager=SandboxManager(str(tmp_path / "sandboxes")))
    app = FastAPI()
    @app.middleware("http")
    async def identity(request: Request, call_next):
        request.state.user = {"sub": "user", "role": request.headers.get("x-test-role", "ORG_ADMIN"), "org_id": request.headers.get("x-test-org")}
        return await call_next(request)
    app.include_router(router, prefix="/workflows")
    app.dependency_overrides[get_db_manager] = lambda: db
    app.dependency_overrides[get_workflow_engine] = lambda: engine
    with TestClient(app) as client:
        yield db, engine, client


def test_rejects_runtime_without_isolation(environment):
    db, engine, client = environment
    response = client.post("/workflows/wf/playground", json={"text": "hello"})
    assert response.status_code == 409
    assert db.list_workflow_executions() == []
    with pytest.raises(ValueError, match="tool-free"):
        engine.execute_workflow("wf", playground=True)


def test_validates_input_and_configured_agents(environment):
    db, engine, client = environment
    engine.runtime = ClaudeCodeAdapter(ClaudeCodeRuntimeAdapter())
    assert client.post("/workflows/wf/playground", json=[1, 2]).status_code == 422
    response = client.post("/workflows/wf/playground", json={})
    assert response.status_code == 422
    assert "Configure agent" in response.json()["detail"]
    assert db.list_workflow_executions() == []


def test_inspection_includes_step_outputs(environment):
    db, engine, client = environment
    db.save_agent(AgentConfig(id="missing", name="Test", description="Test", system_prompt="Analyze"))
    from runtime.models import AgentRun, TaskStatus
    from datetime import datetime
    db.save_task_run(AgentRun(run_id="pg_task_logs", agent_id="missing", project_id=None,
        prompt="hello", status=TaskStatus.FAILED, created_at=datetime.now(), error="CLI diagnostic",
        events=[{"type": "stderr", "content": f"diagnostic {index}"} for index in range(501)]))
    db.create_workflow_execution(execution_id="pg_exec_test", workflow_id="wf",
        trigger_type="PLAYGROUND", trigger_payload='{"text":"hello"}', status="FAILED")
    with db._get_connection() as conn:
        conn.execute("""INSERT INTO workflow_step_runs
            (id, execution_id, step_key, agent_id, status, input_data, output_data)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            ("step", "pg_exec_test", "analyze", "missing", "FAILED", "hello", "failure detail"))
        conn.commit()
    with db._get_connection() as conn:
        conn.execute("UPDATE workflow_step_runs SET task_run_id = ? WHERE id = ?", ("pg_task_logs", "step"))
        conn.commit()
    response = client.get("/workflows/executions/pg_exec_test")
    assert response.status_code == 200
    assert response.json()["step_runs"][0]["output_data"] == "failure detail"
    assert response.json()["trigger_type"] == "PLAYGROUND"
    step = response.json()["step_runs"][0]
    assert step["error"] == "CLI diagnostic"
    assert step["task_status"] == "failed"
    assert len(step["events"]) == 500
    assert step["events"][-1]["content"] == "diagnostic 500"


def test_tool_free_command_overrides_agent_permissions(tmp_path, monkeypatch):
    import base64
    from runtime.services import RuntimeServices
    from storage.runtime_settings import OrganizationRuntimeSettings

    monkeypatch.setenv('PLATFORM_SECRETS_KEY', base64.b64encode(b'p' * 32).decode())
    db = DatabaseManager(str(tmp_path / 'playground-command.sqlite'))
    db.create_organization(id='playground-org', name='Playground', slug='playground')
    OrganizationRuntimeSettings(db, 'playground-org').save(
        {'runtime_provider': 'direct_nvidia', 'runtime_model_direct_nvidia': 'configured/model'},
        {'direct_nvidia': 'test-only-key'}, None)
    services = RuntimeServices(database=lambda: db, configuration=lambda: None,
        resolve_model=lambda value: value, skills_prompt=lambda _: '', capture_session=lambda *_: None)
    runtime = ClaudeCodeRuntimeAdapter(services=services)
    agent = AgentConfig(id="test", name="Test", description="Test", system_prompt="Analyze data",
        allowed_tools=["Bash", "Write"], dangerously_skip_permissions=True, organization_id="playground-org")
    command = runtime._build_claude_command(agent, None, "hello", session_id="old-session",
        dangerously_skip_permissions=True, playground=True)
    assert command[command.index("--tools") + 1] == ""
    assert command[command.index("--mcp-config") + 1] == '{"mcpServers":{}}'
    assert "--strict-mcp-config" in command
    assert "--safe-mode" in command
    assert "--no-session-persistence" in command
    assert "--dangerously-skip-permissions" not in command
    assert "--allowedTools" not in command
    assert "--resume" not in command
    with pytest.raises(ValueError, match="fresh"):
        runtime.start_task(agent_id="test", task_id="pg_task_old", prompt="hello")
    with pytest.raises(ValueError, match="cannot be resumed"):
        runtime.resume_task("pg_task_old", "allow")


def test_playground_hash_does_not_collide_with_production():
    assert compute_execution_hash("wf", {}) != compute_execution_hash("playground:wf", {})


def test_execution_history_and_outputs_are_tenant_scoped(environment):
    db, engine, client = environment
    db.create_organization(id="org-a", name="A", slug="a")
    db.create_organization(id="org-b", name="B", slug="b")
    db.update_workflow("wf", organization_id="org-a")
    db.create_workflow_execution(execution_id="private", workflow_id="wf", trigger_type="PLAYGROUND")
    headers = {"x-test-org": "org-b"}
    assert client.get("/workflows/executions/private", headers=headers).status_code == 404
    assert client.get("/workflows/executions", headers=headers).json() == []
    assert client.post("/workflows/wf/playground", headers=headers, json={}).status_code == 404


def test_member_without_departments_cannot_inspect_department_runs(environment):
    db, engine, client = environment
    db.create_department(id="dept", name="Private")
    db.update_workflow("wf", department_id="dept")
    db.create_workflow_execution(execution_id="private", workflow_id="wf", trigger_type="PLAYGROUND")
    headers = {"x-test-role": "MEMBER"}
    assert client.get("/workflows/executions/private", headers=headers).status_code == 403
    assert client.get("/workflows/executions", headers=headers).json() == []


@pytest.mark.parametrize("mcp_scope", ["workflow", "step"])
def test_runtime_launch_failure_is_not_reported_as_success(environment, mcp_scope):
    # Real adapter cannot resolve a temp-DB-only agent from its application store.
    # Exercise that real configuration failure without launching model inference.
    from uuid import uuid4
    db, engine, client = environment
    agent_id = "pg_isolated_" + uuid4().hex
    db.save_agent(AgentConfig(id=agent_id, name="Test", description="Test", system_prompt="Analyze"))
    db.create_department(id="dept-no-grants", name="No MCP grants")
    definition = {"name": "Exercise", "steps": [
        {"key": "analyze", "agent_id": agent_id, "prompt_template": "Analyze {{text}}"}
    ]}
    if mcp_scope == "workflow":
        definition["mcp_servers"] = ["github"]
    else:
        definition["steps"][0]["mcp_servers"] = ["github"]
    db.update_workflow("wf", department_id="dept-no-grants", definition_json=json.dumps(definition))
    engine.runtime = ClaudeCodeAdapter(ClaudeCodeRuntimeAdapter())
    response = client.post("/workflows/wf/playground", json={"text": "hello"})
    assert response.status_code == 202
    execution_id = response.json()["id"]
    result = client.get(f"/workflows/executions/{execution_id}").json()
    assert result["status"] == "FAILED"
    assert result["step_runs"][0]["status"] == "FAILED"
    assert "Agent not found" in result["step_runs"][0]["output_data"]
    from pathlib import Path
    assert not Path(result["sandbox_path"]).exists()


@pytest.mark.parametrize("mcp_scope", ["workflow", "step"])
def test_live_execution_still_requires_declared_mcp_grants(environment, mcp_scope):
    from workflows.engine import MCPGovernanceViolationError
    db, engine, client = environment
    db.create_organization(id="grant-org", name="Grant scope", slug="grant-scope")
    db.create_department(id="dept-no-grants", name="No MCP grants", organization_id="grant-org")
    db.save_agent(AgentConfig(id="grant-agent", name="Grant agent", description="Scoped worker",
        system_prompt="Analyze", organization_id="grant-org", department_id="dept-no-grants"))
    db.save_mcp_connector({"id": "github", "name": "GitHub", "provider": "github",
        "status": "CONNECTED", "organization_id": "grant-org"})
    definition = {"name": "Exercise", "steps": [
        {"key": "analyze", "agent_id": "grant-agent", "prompt_template": "Analyze input"}
    ]}
    target = definition if mcp_scope == "workflow" else definition["steps"][0]
    target["mcp_servers"] = ["github"]
    db.update_workflow("wf", organization_id="grant-org", department_id="dept-no-grants", definition_json=json.dumps(definition))
    with pytest.raises(MCPGovernanceViolationError, match="github" if mcp_scope == "workflow" else "no active grant"):
        engine.execute_workflow("wf")
    record = db.list_workflow_executions()[0]
    assert record.status == "FAILED"
    expected_reason = "MCP Governance Violation" if mcp_scope == "workflow" else "no active grant"
    assert expected_reason in record.error_message


def test_output_reader_preserves_buffered_text_after_process_exit():
    import subprocess
    import sys
    import queue
    import threading
    process = subprocess.Popen([sys.executable, "-c",
        "import json; print(json.dumps(dict(type='result', result='buffered output')))"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    process.wait(timeout=10)
    events = queue.Queue()
    ClaudeCodeRuntimeAdapter()._output_reader("reader-test", process, events, threading.Event())
    captured = []
    while not events.empty():
        captured.append(events.get_nowait())
    assert any(event.get("result") == "buffered output" for event in captured)
    assert not any(event["type"] == "error" for event in captured)
    process.stdout.close()
    process.stderr.close()


def test_stderr_reader_drains_large_errors_and_bounds_diagnostics():
    import subprocess
    import sys
    import threading
    from collections import deque
    process = subprocess.Popen([sys.executable, "-c",
        'import sys; sys.stderr.write("runtime: unsupported option\\n" * 10000); sys.exit(2)'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    tail = deque(maxlen=5)
    reader = threading.Thread(target=ClaudeCodeRuntimeAdapter._stderr_reader, args=(process, tail))
    reader.start()
    assert process.wait(timeout=10) == 2
    reader.join(timeout=5)
    assert not reader.is_alive()
    assert len(tail) == 5
    assert all("unsupported option" in line for line in tail)
    process.stdout.close()
    process.stderr.close()
