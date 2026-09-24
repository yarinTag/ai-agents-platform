"""
Tests for Feature B (Super Agent) and Feature C (Deep Project Intelligence).
Validates:
- Super Agent role definition and SuperAgentConfig authority limits
- Deep project intelligence targeted retrieval
- Super Agent auto-resolution and session resumption when within authority
- Escalation to HUMAN_OPERATOR when question involves destructive or sensitive actions
- Super Agent scope enforcement (project boundary)
"""

import pytest
import uuid
from datetime import datetime
from fastapi.testclient import TestClient

from backend.main import app
from backend.dependencies import get_db_manager, get_event_bus
from config import AgentConfig, AgentRole, ProjectConfig, SuperAgentConfig
from runtime_adapter import TaskStatus, AgentRun
from orchestration.supervisor_resolver import SupervisorResolver
from orchestration.project_intelligence import ProjectIntelligence


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_project_intelligence_context_retrieval():
    """Test targeted context retrieval from project memory and task context."""
    db = get_db_manager()
    intel = ProjectIntelligence(db)

    proj_id = f"proj-intel-{uuid.uuid4().hex[:6]}"
    db.save_project(ProjectConfig(
        id=proj_id,
        name="Intelligence Test Project",
        description="Testing context assembly",
        working_directory="."
    ))

    # Add ADR and Convention
    db.create_project_memory({
        "project_id": proj_id,
        "category": "ADR",
        "title": "Database Connection Pool Sizing",
        "content": "All PostgreSQL connection pools must be set to maximum 20 connections with 30s timeout.",
        "tags": ["database", "postgres", "pool", "connections"]
    })

    db.create_project_memory({
        "project_id": proj_id,
        "category": "CONVENTION",
        "title": "API Error Response Format",
        "content": "All REST errors must return RFC-7807 Problem Details with type, title, and status.",
        "tags": ["api", "error", "format", "rfc7807"]
    })

    # Retrieve context for database query
    ctx = intel.retrieve_context(proj_id, "How many connections should be configured for the postgres database pool?")
    assert ctx["total_matches"] >= 1
    best_item = ctx["items"][0]
    assert "Database Connection Pool Sizing" in best_item["title"]
    assert "maximum 20 connections" in best_item["content"]

    # Synthesize answer
    synth = intel.synthesize_answer(proj_id, "What is the max connections for postgres database pool?", "worker-1")
    assert synth is not None
    assert "maximum 20 connections" in synth["answer"]
    assert synth["confidence"] > 0.5
    assert not synth["requires_human_approval"]


def test_super_agent_resolution_within_authority():
    """
    Test that when a Super Agent is configured for a project, it answers subordinate questions
    using project intelligence and records an AgentMessage.
    """
    db = get_db_manager()
    event_bus = get_event_bus()

    # Dummy runtime adapter to verify resume_task invocation
    class MockRuntimeAdapter:
        def __init__(self):
            self.resumed_tasks = []

        def resume_task(self, task_id, answer):
            self.resumed_tasks.append((task_id, answer))
            return f"run_{task_id}"

    mock_runtime = MockRuntimeAdapter()
    resolver = SupervisorResolver(db, event_bus, mock_runtime)

    proj_id = f"proj-sa-{uuid.uuid4().hex[:6]}"
    sa_id = f"sa-{uuid.uuid4().hex[:6]}"
    worker_id = f"worker-{uuid.uuid4().hex[:6]}"
    task_id = f"task-sa-{uuid.uuid4().hex[:6]}"

    # Setup project, super agent, and worker
    db.save_project(ProjectConfig(
        id=proj_id,
        name="Core Platform App",
        description="Main production service",
        working_directory="."
    ))

    sa_agent = AgentConfig(
        id=sa_id,
        name="Platform Super Agent",
        description="Authoritative project representative",
        system_prompt="Supervise and unblock project engineers",
        role_type=AgentRole.SUPER_AGENT.value
    )
    db.save_agent(sa_agent)

    worker = AgentConfig(
        id=worker_id,
        name="Backend Worker",
        description="Worker",
        system_prompt="Develop code",
        role_type=AgentRole.WORKER.value,
        parent_id=sa_id
    )
    db.save_agent(worker)

    # Configure Super Agent authority
    sa_config = SuperAgentConfig(
        agent_id=sa_id,
        project_id=proj_id,
        can_answer_questions=True,
        can_delegate=True,
        can_make_project_decisions=True,
        require_human_approval_for=["destructive_actions", "production_changes"]
    )
    db.save_super_agent_config(sa_config)

    # Save project memory for coding convention
    db.create_project_memory({
        "project_id": proj_id,
        "category": "CONVENTION",
        "title": "State Management Architecture Pattern",
        "content": "All platform UI state must be managed via Redux Toolkit slices with RTK Query.",
        "tags": ["state", "redux", "frontend", "architecture"]
    })

    # Save worker's active task
    db.save_task_run(AgentRun(
        run_id=task_id,
        agent_id=worker_id,
        project_id=proj_id,
        prompt="Implement user preferences view",
        status=TaskStatus.RUNNING,
        created_at=datetime.now()
    ))

    # Worker asks about state management convention
    res = resolver.resolve_or_escalate_question(
        task_id=task_id,
        requester_agent_id=worker_id,
        project_id=proj_id,
        question="Which state management pattern and library should this component use?"
    )

    assert res["status"] == "AUTO_RESOLVED"
    assert res["target_approver"] == sa_id
    assert "Redux Toolkit" in res["answer"]
    assert f"SUPER_AGENT:{sa_id}" in res["resolved_by"]

    # Verify task resumed via runtime adapter
    assert len(mock_runtime.resumed_tasks) == 1
    assert mock_runtime.resumed_tasks[0][0] == task_id
    assert "Redux Toolkit" in mock_runtime.resumed_tasks[0][1]

    # Verify AgentMessage was persisted from Super Agent to Worker
    messages = db.list_agent_messages(from_agent_id=sa_id, to_agent_id=worker_id)
    assert len(messages) >= 1
    assert "Redux Toolkit" in messages[0].content


def test_super_agent_escalation_for_destructive_actions():
    """
    Test that when a question requires a destructive or sensitive decision,
    the Super Agent refuses autonomous resolution and escalates to HUMAN_OPERATOR.
    """
    db = get_db_manager()
    event_bus = get_event_bus()
    resolver = SupervisorResolver(db, event_bus)

    proj_id = f"proj-destr-{uuid.uuid4().hex[:6]}"
    sa_id = f"sa-{uuid.uuid4().hex[:6]}"
    worker_id = f"worker-{uuid.uuid4().hex[:6]}"
    task_id = f"task-destr-{uuid.uuid4().hex[:6]}"

    db.save_project(ProjectConfig(
        id=proj_id,
        name="Destructive Project",
        description="Testing authority guardrails",
        working_directory="."
    ))

    db.save_agent(AgentConfig(
        id=sa_id,
        name="Safety Super Agent",
        description="Super Agent",
        system_prompt="Safe supervisor",
        role_type=AgentRole.SUPER_AGENT.value
    ))

    db.save_agent(AgentConfig(
        id=worker_id,
        name="DB Admin Worker",
        description="DB worker",
        system_prompt="Run migrations",
        role_type=AgentRole.WORKER.value,
        parent_id=sa_id
    ))

    db.save_super_agent_config(SuperAgentConfig(
        agent_id=sa_id,
        project_id=proj_id,
        require_human_approval_for=["destructive_actions", "production_changes"]
    ))

    # Even if there is a memory mentioning table cleanup, destructive questions MUST escalate to Human
    db.create_project_memory({
        "project_id": proj_id,
        "category": "ADR",
        "title": "Drop Legacy Customers Table",
        "content": "Execute DROP TABLE legacy_customers after migration completes.",
        "tags": ["database", "drop", "table"]
    })

    db.save_task_run(AgentRun(
        run_id=task_id,
        agent_id=worker_id,
        project_id=proj_id,
        prompt="Cleanup legacy tables",
        status=TaskStatus.RUNNING,
        created_at=datetime.now()
    ))

    # Worker asks question with destructive action
    res = resolver.resolve_or_escalate_question(
        task_id=task_id,
        requester_agent_id=worker_id,
        project_id=proj_id,
        question="Should I delete and drop table legacy_customers now?"
    )

    # Must NOT auto-resolve. Must escalate to HUMAN_OPERATOR!
    assert res["status"] == "PENDING_INPUT"
    assert res["target_approver"] == "HUMAN_OPERATOR"

    # Verify task status is WAITING_INPUT
    task = db.get_task_run(task_id)
    assert task.status == TaskStatus.WAITING_INPUT
