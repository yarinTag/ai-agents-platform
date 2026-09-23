"""
Integration tests for Multi-Agent War Room and Project Shared Memory APIs.
"""

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.dependencies import get_db_manager
from config import AgentConfig, ProjectConfig


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_project_memories_lifecycle(client):
    db = get_db_manager()
    project_id = "test-project-alpha"
    agent_id = "architect-lead"

    # Ensure project and agent exist for foreign key constraints
    db.save_project(ProjectConfig(
        id=project_id,
        name="Alpha Project",
        description="Test Project for memories",
        working_directory="."
    ))
    db.save_agent(AgentConfig(
        id=agent_id,
        name="Architect Lead",
        description="Architecture specialist",
        system_prompt="Design architectures"
    ))

    # 1. Create a memory (ADR)
    create_resp = client.post(f"/api/v1/projects/{project_id}/memories", json={
        "category": "ADR",
        "title": "Use FastAPI for Microservices",
        "content": "All internal agent services must use FastAPI with Pydantic v2 schemas.",
        "tags": ["architecture", "fastapi", "python"],
        "author_agent_id": agent_id
    })
    assert create_resp.status_code == 201
    memory = create_resp.json()
    assert memory["id"] is not None
    assert memory["category"] == "ADR"
    assert memory["title"] == "Use FastAPI for Microservices"
    memory_id = memory["id"]

    # 2. List memories
    list_resp = client.get(f"/api/v1/projects/{project_id}/memories")
    assert list_resp.status_code == 200
    memories = list_resp.json()
    assert any(m["id"] == memory_id for m in memories)

    # 3. Retrieve context prompt for LLM injection
    prompt_resp = client.get(f"/api/v1/projects/{project_id}/context-prompt")
    assert prompt_resp.status_code == 200
    prompt_data = prompt_resp.json()
    assert prompt_data["memories_count"] >= 1
    assert "PROJECT SHARED KNOWLEDGE" in prompt_data["context_prompt"]
    assert "Use FastAPI for Microservices" in prompt_data["context_prompt"]

    # 4. Delete memory
    del_resp = client.delete(f"/api/v1/projects/{project_id}/memories/{memory_id}")
    assert del_resp.status_code == 204

    # Verify deletion
    list_after = client.get(f"/api/v1/projects/{project_id}/memories").json()
    assert not any(m["id"] == memory_id for m in list_after)


def test_war_room_session_and_synthesis(client):
    db = get_db_manager()
    project_id = "data-platform"
    mod_id = "engineering-lead"
    p1_id = "database-architect"
    p2_id = "qa-specialist"

    # Ensure project and agents exist
    db.save_project(ProjectConfig(
        id=project_id,
        name="Data Platform",
        description="Data platform project",
        working_directory="."
    ))
    for aid, aname in [(mod_id, "Engineering Lead"), (p1_id, "DB Architect"), (p2_id, "QA Specialist")]:
        db.save_agent(AgentConfig(
            id=aid,
            name=aname,
            description="Agent role",
            system_prompt="Execute role"
        ))

    # 1. Create a new War Room deliberation session
    create_resp = client.post("/api/v1/war-room/", json={
        "title": "Database Sharding Strategy",
        "topic": "Evaluating PostgreSQL Partitioning vs Citus cluster for Q4 scaling.",
        "project_id": project_id,
        "moderator_agent_id": mod_id,
        "participant_agent_ids": [p1_id, p2_id]
    })
    assert create_resp.status_code == 201
    session = create_resp.json()
    session_id = session["id"]
    assert session["status"] == "DEBATING"
    assert session["moderator_agent_id"] == mod_id

    # 2. Add deliberation messages (Round 1: Proposals & Critiques)
    msg1_resp = client.post(f"/api/v1/war-room/{session_id}/messages", json={
        "agent_id": p1_id,
        "round_number": 1,
        "message_type": "PROPOSAL",
        "content": "I propose native declarative partitioning by tenant_id on high-volume tables."
    })
    assert msg1_resp.status_code == 200
    assert msg1_resp.json()["message_type"] == "PROPOSAL"

    msg2_resp = client.post(f"/api/v1/war-room/{session_id}/messages", json={
        "agent_id": p2_id,
        "round_number": 1,
        "message_type": "CRITIQUE",
        "content": "Native partitioning requires careful migration of foreign keys. Cross-partition queries must be tested."
    })
    assert msg2_resp.status_code == 200

    # 3. Retrieve session with all messages
    detail_resp = client.get(f"/api/v1/war-room/{session_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["session"]["id"] == session_id
    assert len(detail["messages"]) == 2

    # 4. Synthesize plan and reach consensus
    synthesized_text = "Consensus reached: Adopt native PostgreSQL partitioning with automated partition management scripts and a dedicated migration verification suite."
    synth_resp = client.post(f"/api/v1/war-room/{session_id}/synthesize", json={
        "synthesized_plan": synthesized_text
    })
    assert synth_resp.status_code == 200
    updated_session = synth_resp.json()
    assert updated_session["synthesized_plan"] == synthesized_text

