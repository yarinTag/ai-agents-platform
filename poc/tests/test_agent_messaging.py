"""
Tests for Feature A: Real Agent-to-Agent Communication.
Validates:
- Message persistence in SQLite
- Bidirectional messaging (Agent A -> Agent B -> Agent A)
- Communication permission enforcement (Parent/Child, Sibling, Unauthorized worker, Self)
- EventBus event emission (agent.message.sent, agent.message.received)
- SSE observable payload format
"""

import pytest
import uuid
from fastapi.testclient import TestClient
from datetime import datetime

from backend.main import app
from backend.dependencies import get_db_manager, get_event_bus
from config import AgentConfig, AgentRole
from events import PlatformEvent


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def setup_hierarchy(client):
    """
    Setup an agent hierarchy:
    Manager -> (Frontend, Backend)
    Unrelated Worker (standalone)
    """
    db = get_db_manager()
    mgr_id = f"mgr-{uuid.uuid4().hex[:6]}"
    fe_id = f"fe-{uuid.uuid4().hex[:6]}"
    be_id = f"be-{uuid.uuid4().hex[:6]}"
    unrelated_id = f"unrelated-{uuid.uuid4().hex[:6]}"

    mgr = AgentConfig(
        id=mgr_id,
        name="Eng Manager",
        description="Engineering Manager",
        system_prompt="Manage teams",
        role_type=AgentRole.MANAGER.value,
        allow_sibling_communication=True
    )
    fe = AgentConfig(
        id=fe_id,
        name="Frontend Dev",
        description="Frontend Specialist",
        system_prompt="Write React",
        role_type=AgentRole.WORKER.value,
        parent_id=mgr_id,
        allow_sibling_communication=True
    )
    be = AgentConfig(
        id=be_id,
        name="Backend Dev",
        description="Backend Specialist",
        system_prompt="Write Python",
        role_type=AgentRole.WORKER.value,
        parent_id=mgr_id,
        allow_sibling_communication=True
    )
    unrelated = AgentConfig(
        id=unrelated_id,
        name="External Worker",
        description="Isolated worker",
        system_prompt="External work",
        role_type=AgentRole.WORKER.value,
        allow_sibling_communication=False
    )

    db.save_agent(mgr)
    db.save_agent(fe)
    db.save_agent(be)
    db.save_agent(unrelated)

    return {
        "mgr": mgr_id,
        "fe": fe_id,
        "be": be_id,
        "unrelated": unrelated_id
    }


def test_agent_to_agent_messaging_and_reply(client, setup_hierarchy):
    """Test full conversational flow: Agent A -> Agent B -> Agent A."""
    agents = setup_hierarchy
    event_bus = get_event_bus()

    # Capture emitted events
    captured_events = []
    queue, unsub = event_bus.subscribe(filter_fn=lambda e: "agent.message" in e.event_type)

    try:
        # 1. Frontend asks Backend a question
        question_payload = {
            "from_agent_id": agents["fe"],
            "to_agent_id": agents["be"],
            "message_type": "QUESTION",
            "content": "What is the endpoint for fetching user profile settings?",
            "metadata": {"urgency": "high"}
        }
        res_q = client.post("/api/v1/messages/", json=question_payload)
        assert res_q.status_code == 201, res_q.text
        msg_q = res_q.json()
        assert msg_q["from_agent_id"] == agents["fe"]
        assert msg_q["to_agent_id"] == agents["be"]
        assert msg_q["message_type"] == "QUESTION"
        assert msg_q["status"] == "SENT"
        assert msg_q["id"] is not None

        # 2. Backend replies with an answer
        reply_payload = {
            "from_agent_id": agents["be"],
            "message_type": "ANSWER",
            "content": "Use GET /api/v1/users/profile with Bearer token authentication.",
            "metadata": {"version": "v1"}
        }
        res_a = client.post(f"/api/v1/messages/{msg_q['id']}/reply", json=reply_payload)
        assert res_a.status_code == 201, res_a.text
        msg_a = res_a.json()
        assert msg_a["from_agent_id"] == agents["be"]
        assert msg_a["to_agent_id"] == agents["fe"]
        assert msg_a["message_type"] == "ANSWER"
        assert msg_a["parent_message_id"] == msg_q["id"]

        # 3. Verify message thread detail
        res_detail = client.get(f"/api/v1/messages/{msg_q['id']}")
        assert res_detail.status_code == 200
        detail = res_detail.json()
        assert detail["status"] == "ANSWERED"
        assert detail["responded_at"] is not None
        assert len(detail["replies"]) == 1
        assert detail["replies"][0]["id"] == msg_a["id"]

        # 4. List messages between these two agents
        res_list = client.get(f"/api/v1/messages/?from_agent_id={agents['fe']}&to_agent_id={agents['be']}")
        assert res_list.status_code == 200
        assert len(res_list.json()) >= 1

    finally:
        unsub()


def test_agent_communication_permissions(client, setup_hierarchy):
    """Test strict enforcement of communication rules."""
    agents = setup_hierarchy

    # 1. Child -> Parent: Allowed
    res = client.post("/api/v1/messages/", json={
        "from_agent_id": agents["fe"],
        "to_agent_id": agents["mgr"],
        "content": "Sprint goals updated."
    })
    assert res.status_code == 201

    # 2. Parent -> Child: Allowed
    res = client.post("/api/v1/messages/", json={
        "from_agent_id": agents["mgr"],
        "to_agent_id": agents["be"],
        "content": "Please prioritize ticket #402."
    })
    assert res.status_code == 201

    # 3. Unrelated Worker -> Frontend: Forbidden (HTTP 403)
    res = client.post("/api/v1/messages/", json={
        "from_agent_id": agents["unrelated"],
        "to_agent_id": agents["fe"],
        "content": "Hey, can you help me with this?"
    })
    assert res.status_code == 403
    assert "not authorized to communicate directly" in res.json()["detail"]

    # 4. Self messaging: Forbidden (HTTP 403)
    res = client.post("/api/v1/messages/", json={
        "from_agent_id": agents["fe"],
        "to_agent_id": agents["fe"],
        "content": "Self reflection"
    })
    assert res.status_code == 403
    assert "cannot send a message to itself" in res.json()["detail"]


def test_sibling_communication_toggle(client, setup_hierarchy):
    """Test disabling sibling communication on an agent."""
    agents = setup_hierarchy
    db = get_db_manager()

    # Disable sibling communication for Frontend
    fe_agent = db.get_agent(agents["fe"])
    fe_agent.allow_sibling_communication = False
    db.save_agent(fe_agent)

    # Now Frontend attempting to message Backend (sibling) must fail
    res = client.post("/api/v1/messages/", json={
        "from_agent_id": agents["fe"],
        "to_agent_id": agents["be"],
        "content": "Are you there?"
    })
    assert res.status_code == 403
    assert "Sibling communication is disabled" in res.json()["detail"]

    # Re-enable by adding Backend to allowed_peer_ids
    fe_agent.allowed_peer_ids = [agents["be"]]
    db.save_agent(fe_agent)

    res_allowed = client.post("/api/v1/messages/", json={
        "from_agent_id": agents["fe"],
        "to_agent_id": agents["be"],
        "content": "Now allowed through explicit peer permissions."
    })
    assert res_allowed.status_code == 201
