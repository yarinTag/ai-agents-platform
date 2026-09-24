"""
Integration tests for Supervisor Clarification Question Interception & Multi-Tier Resolution.
"""

import pytest
import uuid
from datetime import datetime
from fastapi.testclient import TestClient

from backend.main import app
from backend.dependencies import get_db_manager, get_event_bus
from config import AgentConfig, ProjectConfig
from runtime_adapter import TaskStatus, AgentRun
from orchestration.supervisor_resolver import SupervisorResolver


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_supervisor_auto_resolve_from_shared_memory():
    """
    Tier 1: When a question matches an active Project Shared Memory / Convention,
    it must be AUTO_RESOLVED immediately without bothering the human operator.
    """
    db = get_db_manager()
    event_bus = get_event_bus()
    resolver = SupervisorResolver(db, event_bus)

    proj_id = f"proj-auto-{uuid.uuid4().hex[:6]}"
    agent_id = f"worker-{uuid.uuid4().hex[:6]}"
    task_id = f"task-auto-{uuid.uuid4().hex[:6]}"

    # Setup project and agent
    db.save_project(ProjectConfig(
        id=proj_id,
        name="Auto Resolve Test Project",
        description="Auto resolve test",
        working_directory="."
    ))
    db.save_agent(AgentConfig(
        id=agent_id,
        name="Backend Engineer",
        description="Builds APIs",
        system_prompt="Develop endpoints"
    ))

    # Add a project convention/ADR in shared memory
    db.create_project_memory({
        "project_id": proj_id,
        "category": "CONVENTION",
        "title": "Authentication Bearer JWT Format",
        "content": "All internal endpoints require Bearer JWT tokens in Authorization header with RS256 algorithm.",
        "tags": ["auth", "jwt", "bearer", "token"]
    })

    # Record initial task run
    db.save_task_run(AgentRun(
        run_id=task_id,
        agent_id=agent_id,
        project_id=proj_id,
        prompt="Implement auth middleware",
        status=TaskStatus.RUNNING,
        created_at=datetime.now()
    ))

    # Agent encounters missing info and asks clarification
    result = resolver.resolve_or_escalate_question(
        task_id=task_id,
        requester_agent_id=agent_id,
        project_id=proj_id,
        question="What authentication bearer token format should the middleware use for verification?"
    )

    assert result["status"] == "AUTO_RESOLVED"
    assert "Bearer JWT" in result["answer"]
    assert result["target_approver"] == "PROJECT_SHARED_MEMORY"

    # Verify interaction record in DB
    interaction = db.get_interaction(result["interaction_id"])
    assert interaction is not None
    assert interaction["status"] == "APPROVED"
    assert interaction["resolved_by"] == "SUPERVISOR_AUTO_RESOLVE"


def test_supervisor_escalate_to_manager_and_resume(client):
    """
    Tier 2: When a question cannot be resolved by memory,
    it must be escalated to the agent's manager (parent_id) in WAITING_INPUT status,
    and unblocked when the manager/human responds.
    """
    db = get_db_manager()
    event_bus = get_event_bus()
    resolver = SupervisorResolver(db, event_bus)

    proj_id = f"proj-esc-{uuid.uuid4().hex[:6]}"
    mgr_id = f"mgr-{uuid.uuid4().hex[:6]}"
    worker_id = f"worker-{uuid.uuid4().hex[:6]}"
    task_id = f"task-esc-{uuid.uuid4().hex[:6]}"

    # Setup project and hierarchy
    db.save_project(ProjectConfig(
        id=proj_id,
        name="Escalation Project",
        description="Escalation test",
        working_directory="."
    ))
    db.save_agent(AgentConfig(
        id=mgr_id,
        name="Team Lead",
        description="Manager",
        system_prompt="Coordinate work"
    ))
    db.save_agent(AgentConfig(
        id=worker_id,
        name="Junior Dev",
        description="Worker",
        system_prompt="Execute work",
        parent_id=mgr_id
    ))

    # Save running task
    db.save_task_run(AgentRun(
        run_id=task_id,
        agent_id=worker_id,
        project_id=proj_id,
        prompt="Deploy to staging cluster",
        status=TaskStatus.RUNNING,
        created_at=datetime.now(),
        session_id="claude_sess_12345"
    ))

    # Worker asks question with no matching memory
    result = resolver.resolve_or_escalate_question(
        task_id=task_id,
        requester_agent_id=worker_id,
        project_id=proj_id,
        question="Which AWS region and cluster credentials should be used for this deployment?"
    )

    assert result["status"] == "PENDING_INPUT"
    assert result["target_approver"] == mgr_id  # Routed to direct manager!

    # Verify task status is WAITING_INPUT
    task_after = db.get_task_run(task_id)
    assert task_after.status == TaskStatus.WAITING_INPUT
    assert "Waiting for" in task_after.result

    # Manager answers the question via the approvals API
    respond_resp = client.post("/api/v1/approvals/respond", json={
        "interaction_id": result["interaction_id"],
        "decision": "approve",
        "response_text": "Use eu-west-1 cluster with profile staging-deploy.",
        "responder": mgr_id
    })
    assert respond_resp.status_code == 200
    resp_data = respond_resp.json()
    assert resp_data["status"] == "success"
    assert resp_data["resumed"] is True

    # Task status resumed to RUNNING
    task_resumed = db.get_task_run(task_id)
    assert task_resumed.status == TaskStatus.RUNNING
    assert task_resumed.session_id == "claude_sess_12345"
