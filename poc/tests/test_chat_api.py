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

    # 1. Get an agent to chat with
    agent = db.get_agent("engineering-lead")
    if not agent:
        agents = db.list_agents()
        agent_id = agents[0].id if agents else "test-agent"
    else:
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
