"""
Tests for Feature J: Temporary Agent Teams.
Validates:
- Team creation with manager and members
- Persistence in SQLite (agent_teams and team_members)
- Parallel task dispatching to all team members
- Executive summary synthesis from member outputs
- Event emission for team.created, team.dispatched, team.completed
"""

import pytest
import uuid
from fastapi.testclient import TestClient
from datetime import datetime

from backend.main import app
from backend.dependencies import get_db_manager, get_event_bus
from config import AgentConfig, AgentRole
from runtime_adapter import TaskStatus


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def setup_team_agents():
    db = get_db_manager()
    mgr_id = f"lead-{uuid.uuid4().hex[:6]}"
    auditor_id = f"auditor-{uuid.uuid4().hex[:6]}"
    sec_id = f"sec-{uuid.uuid4().hex[:6]}"

    mgr = AgentConfig(
        id=mgr_id,
        name="Team Lead",
        description="Coordinates team audits",
        system_prompt="Lead audits",
        role_type=AgentRole.MANAGER.value
    )
    auditor = AgentConfig(
        id=auditor_id,
        name="Code Auditor",
        description="Audits code quality",
        system_prompt="Audit code",
        role_type=AgentRole.WORKER.value,
        parent_id=mgr_id
    )
    sec = AgentConfig(
        id=sec_id,
        name="Security Specialist",
        description="Reviews vulnerabilities",
        system_prompt="Review security",
        role_type=AgentRole.WORKER.value,
        parent_id=mgr_id
    )

    db.save_agent(mgr)
    db.save_agent(auditor)
    db.save_agent(sec)

    return {
        "manager_id": mgr_id,
        "auditor_id": auditor_id,
        "security_id": sec_id
    }


def test_agent_team_lifecycle_and_dispatch(client, setup_team_agents):
    mgr_id = setup_team_agents["manager_id"]
    auditor_id = setup_team_agents["auditor_id"]
    sec_id = setup_team_agents["security_id"]
    event_bus = get_event_bus()

    captured_events = []

    def on_event(event):
        if event.event_type.startswith("team."):
            captured_events.append(event)

    event_bus.subscribe(on_event)

    # 1. Create a Team
    create_resp = client.post(
        "/api/v1/teams",
        json={
            "name": "Architecture Review Board",
            "manager_agent_id": mgr_id,
            "member_agent_ids": [auditor_id, sec_id],
            "description": "Cross-cutting architecture review"
        }
    )
    assert create_resp.status_code == 201, create_resp.text
    team_data = create_resp.json()
    team_id = team_data["id"]
    assert team_data["name"] == "Architecture Review Board"
    assert len(team_data["members"]) == 2

    # Verify team in GET list
    list_resp = client.get("/api/v1/teams")
    assert list_resp.status_code == 200
    assert any(t["id"] == team_id for t in list_resp.json())

    # 2. Dispatch parallel tasks to team
    dispatch_resp = client.post(
        f"/api/v1/teams/{team_id}/dispatch",
        json={
            "shared_goal": "Perform comprehensive audit of auth service",
            "member_prompts": {
                auditor_id: "Review auth code complexity and test coverage",
                sec_id: "Inspect auth token handling for OWASP vulnerabilities"
            }
        }
    )
    assert dispatch_resp.status_code == 200, dispatch_resp.text
    dispatch_data = dispatch_resp.json()
    assert dispatch_data["status"] == "DISPATCHED"
    tasks = dispatch_data["tasks"]
    assert len(tasks) == 2

    # Verify tasks created in DB
    db = get_db_manager()
    task_ids = [t["task_id"] for t in tasks]
    for tid in task_ids:
        task = db.get_task_run(tid)
        assert task is not None
        assert task.assigned_by == mgr_id

    # 3. Simulate completion of member tasks
    for tid, agent_id in [(task_ids[0], auditor_id), (task_ids[1], sec_id)]:
        db.update_task_run(
            tid,
            status=TaskStatus.COMPLETED,
            result=f"Completed audit by {agent_id}: No issues found."
        )

    # 4. Synthesize team results
    synth_resp = client.post(
        f"/api/v1/teams/{team_id}/synthesize",
        json={"task_ids": task_ids}
    )
    assert synth_resp.status_code == 200, synth_resp.text
    synth_data = synth_resp.json()
    assert synth_data["status"] == "COMPLETED"
    assert "Executive Synthesis" in synth_data["synthesis"]
    assert len(synth_data["member_results"]) == 2

    # Verify team status updated to COMPLETED in DB
    updated_team = db.get_agent_team(team_id)
    assert updated_team.status == "COMPLETED"

    # Verify events were fired
    event_types = [e.event_type for e in captured_events]
    assert "team.created" in event_types
    assert "team.dispatched" in event_types
    assert "team.completed" in event_types


def test_agent_team_validation_errors(client):
    # Non-existent manager
    resp = client.post(
        "/api/v1/teams",
        json={
            "name": "Bad Team",
            "manager_agent_id": "non_existent_mgr",
            "member_agent_ids": ["some_member"]
        }
    )
    assert resp.status_code == 404

    # Non-existent team dispatch
    resp = client.post(
        "/api/v1/teams/non_existent_team/dispatch",
        json={"shared_goal": "Do something"}
    )
    assert resp.status_code == 404
