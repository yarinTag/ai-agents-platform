"""
End-to-end integration test for Cron Jobs, Task Statuses, and Manager/HITL Approvals.
"""

import pytest
import asyncio
from datetime import datetime
from fastapi.testclient import TestClient

from backend.main import app
from backend.dependencies import get_db_manager, get_runtime_adapter
from runtime_adapter import TaskStatus


@pytest.fixture
def client():
    # Bypass auth dependency for tests if needed or use test client directly
    with TestClient(app) as c:
        yield c


def test_cron_and_approvals_flow(client):
    db = get_db_manager()

    # 1. Ensure test agent exists
    agent = db.get_agent("qa-specialist")
    if not agent:
        agents = db.list_agents()
        agent_id = agents[0].id if agents else "test-agent"
    else:
        agent_id = "qa-specialist"

    # 2. Test Cron Validation Endpoint
    val_resp = client.post("/api/v1/schedules/validate", json={"cron_expression": "*/10 * * * *"})
    assert val_resp.status_code == 200
    val_data = val_resp.json()
    assert val_data["valid"] is True
    assert len(val_data["upcoming_runs"]) == 5

    # 3. Create a Scheduled Cron Job
    create_payload = {
        "name": "Integration Test Security Scan",
        "description": "Daily automated scan",
        "cron_expression": "0 2 * * *",
        "agent_id": agent_id,
        "prompt": "Scan codebase for critical vulnerabilities",
        "concurrency_policy": "SKIP",
        "enabled": True
    }
    create_resp = client.post("/api/v1/schedules/", json=create_payload)
    assert create_resp.status_code == 201
    job = create_resp.json()
    job_id = job["id"]
    assert job["name"] == "Integration Test Security Scan"
    assert job["enabled"] is True

    # 4. List Schedules
    list_resp = client.get("/api/v1/schedules/")
    assert list_resp.status_code == 200
    jobs = list_resp.json()
    assert any(j["id"] == job_id for j in jobs)

    # 5. Toggle Schedule (pause)
    toggle_resp = client.post(f"/api/v1/schedules/{job_id}/toggle", json={"enabled": False})
    assert toggle_resp.status_code == 200
    assert toggle_resp.json()["enabled"] is False

    # 6. Test Approvals / HITL flow
    # Create a dummy task run in db
    now = datetime.now()
    task_run_id = f"test_run_{int(now.timestamp())}"
    with db._get_connection() as conn:
        conn.execute("""
            INSERT INTO task_runs (run_id, agent_id, prompt, status, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (task_run_id, agent_id, "Analyze database migration", TaskStatus.RUNNING.value, now.isoformat()))
        conn.commit()

    # Agent raises a clarification question
    app_create_resp = client.post("/api/v1/approvals/", json={
        "task_id": task_run_id,
        "requester_agent_id": agent_id,
        "interaction_type": "QUESTION",
        "title": "Which database dialect to target?",
        "content": "Should migration target PostgreSQL 16 or SQLite for embedded mode?",
    })
    assert app_create_resp.status_code == 201
    interaction = app_create_resp.json()
    interaction_id = interaction["id"]

    # Verify task status was set to waiting_input
    updated_run = db.get_task_run(task_run_id)
    assert updated_run.status == TaskStatus.WAITING_INPUT

    # List pending approvals
    pending_resp = client.get("/api/v1/approvals/pending")
    assert pending_resp.status_code == 200
    pending_list = pending_resp.json()
    assert any(p["id"] == interaction_id for p in pending_list)

    # Operator / Manager responds to the question
    respond_resp = client.post("/api/v1/approvals/respond", json={
        "interaction_id": interaction_id,
        "decision": "approve",
        "response_text": "Target PostgreSQL 16 for production and SQLite for local tests.",
        "responder": "HUMAN_OPERATOR"
    })
    assert respond_resp.status_code == 200
    res_data = respond_resp.json()
    assert res_data["status"] == "success"
    assert res_data["resumed"] is True

    # Verify task resumed to RUNNING
    resumed_run = db.get_task_run(task_run_id)
    assert resumed_run.status == TaskStatus.RUNNING

    # 7. Clean up
    del_resp = client.delete(f"/api/v1/schedules/{job_id}")
    assert del_resp.status_code == 204
