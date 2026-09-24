"""
Integration tests for Interactive Agent Mini-Chat API.
"""

import pytest
from datetime import datetime
from fastapi.testclient import TestClient

from backend.main import app
from backend.dependencies import get_db_manager
from runtime_adapter import TaskStatus


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_agent_chat_flow(client):
    db = get_db_manager()

    # 1. Get or create an agent to chat with
    agent = db.get_agent("engineering-lead")
    if not agent:
        from config import AgentConfig
        agent = AgentConfig(id="engineering-lead", name="Engineering Lead", description="Lead Engineer", system_prompt="You are a lead engineer.")
        db.save_agent(agent)
    agent_id = "engineering-lead"

    # 2. Clear existing chat history
    clear_resp = client.post(f"/api/v1/chat/{agent_id}/clear")
    assert clear_resp.status_code == 200

    # 3. Send message from user to agent
    msg_content = "Hello, please summarize the current sprint backlog."
    send_resp = client.post(f"/api/v1/chat/{agent_id}/messages", json={
        "content": msg_content
    })
    assert send_resp.status_code == 200
    send_data = send_resp.json()
    assert send_data["user_message"]["content"] == msg_content
    assert send_data["user_message"]["sender_type"] == "USER"

    # 4. Fetch history and verify message is present
    hist_resp = client.get(f"/api/v1/chat/{agent_id}/messages")
    assert hist_resp.status_code == 200
    hist_data = hist_resp.json()
    assert len(hist_data["messages"]) >= 1
    assert any(m["content"] == msg_content for m in hist_data["messages"])

    # 5. Test in-chat interactive resolution:
    # Simulate an agent with a pending clarification question
    now = datetime.now()
    task_run_id = f"test_chat_task_{int(now.timestamp())}"
    with db._get_connection() as conn:
        conn.execute("""
            INSERT INTO task_runs (run_id, agent_id, prompt, status, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (task_run_id, agent_id, "Review security policies", TaskStatus.WAITING_INPUT.value, now.isoformat()))
        conn.commit()

    db.create_interaction({
        "task_id": task_run_id,
        "requester_agent_id": agent_id,
        "target_approver_id": "HUMAN_OPERATOR",
        "interaction_type": "QUESTION",
        "title": "Authentication protocol question",
        "content": "Should we enforce MFA on all admin accounts?"
    })

    # User replies inside the chat
    reply_content = "Yes, enforce MFA on all accounts immediately."
    resolve_resp = client.post(f"/api/v1/chat/{agent_id}/messages", json={
        "content": reply_content
    })
    assert resolve_resp.status_code == 200
    resolve_data = resolve_resp.json()
    assert resolve_data["status"] == "resolved_interaction"

    # Verify task resumed to RUNNING
    updated_run = db.get_task_run(task_run_id)
    assert updated_run.status == TaskStatus.RUNNING


def test_completed_task_response_visible_in_chat(client):
    db = get_db_manager()
    agent_id = "engineering-lead"
    agent = db.get_agent(agent_id)
    if not agent:
        from config import AgentConfig
        agent = AgentConfig(id=agent_id, name="Engineering Lead", description="Lead Engineer", system_prompt="You are a lead engineer.")
        db.save_agent(agent)
    now = datetime.now()

    # Simulate a completed task dispatched to this agent
    task_id = f"test_completed_task_{int(now.timestamp())}"
    task_prompt = "Build user authentication endpoint"
    task_result = "SUCCESS: User auth endpoint implemented and verified with 100% test coverage."

    with db._get_connection() as conn:
        conn.execute("""
            INSERT INTO task_runs (run_id, agent_id, prompt, status, result, created_at, ended_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (task_id, agent_id, task_prompt, TaskStatus.COMPLETED.value, task_result, now.isoformat(), now.isoformat()))
        conn.commit()

    # When fetching chat messages for this agent, the completed task should be automatically synced as ASSISTANT message
    resp = client.get(f"/api/v1/chat/{agent_id}/messages")
    assert resp.status_code == 200
    data = resp.json()

    # Check tasks array in response
    assert "tasks" in data
    assert any(t["run_id"] == task_id and t["result"] == task_result for t in data["tasks"])

    # Check messages array has the assistant response
    assert "messages" in data
    matching_msgs = [
        m for m in data["messages"]
        if (m.get("metadata") or {}).get("task_id") == task_id or m.get("task_id") == task_id or m.get("content") == task_result
    ]
    assert len(matching_msgs) >= 1
    # Check that at least one matching message is an ASSISTANT response
    assistant_msgs = [m for m in matching_msgs if m.get("sender_type") == "ASSISTANT"]
    assert len(assistant_msgs) >= 1
    assert assistant_msgs[0]["content"] == task_result
