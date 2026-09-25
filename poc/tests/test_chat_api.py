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


def test_agent_sessions_multi_tab_and_supervisor_link(client):
    """
    Test that:
    1. Each agent has its session in the DB.
    2. Creating a new session via POST /{agent_id}/sessions closes the old active session and creates a new one.
    3. The child agent's session is linked with the supervisor's active session.
    4. Switching between sessions (activate) loads the correct history for each session.
    """
    db = get_db_manager()
    from config import AgentConfig

    # 1. Create a Manager agent (supervisor)
    manager = AgentConfig(
        id="eng-manager-test",
        name="Engineering Manager",
        description="Engineering Manager",
        system_prompt="You manage engineers."
    )
    db.save_agent(manager)

    # 2. Create a Worker agent reporting to Manager
    worker = AgentConfig(
        id="fe-worker-test",
        name="Frontend Worker",
        description="Frontend Worker",
        system_prompt="You build UI.",
        parent_id="eng-manager-test"
    )
    db.save_agent(worker)

    # Ensure manager has an active session
    mgr_sess = db.get_or_create_conversation("eng-manager-test")

    # 3. List worker sessions and verify supervisor link
    worker_sess_resp = client.get("/api/v1/chat/fe-worker-test/sessions")
    assert worker_sess_resp.status_code == 200
    w_sessions = worker_sess_resp.json()["sessions"]
    assert len(w_sessions) >= 1
    first_worker_sess = w_sessions[0]
    assert first_worker_sess["status"] == "ACTIVE"
    assert first_worker_sess["supervisor_agent_id"] == "eng-manager-test"
    assert first_worker_sess["supervisor_agent_name"] == "Engineering Manager"
    assert first_worker_sess["supervisor_session_id"] == mgr_sess["id"]

    # 4. Send a message in Worker's first session
    send_resp1 = client.post("/api/v1/chat/fe-worker-test/messages", json={
        "content": "Message in Session 1",
        "conversation_id": first_worker_sess["id"]
    })
    assert send_resp1.status_code == 200

    # 5. Create a NEW session for the worker (simulating clicking '+' in drawer)
    new_sess_resp = client.post("/api/v1/chat/fe-worker-test/sessions", json={
        "title": "Session 2"
    })
    assert new_sess_resp.status_code == 200
    new_sess = new_sess_resp.json()["session"]
    assert new_sess["title"] == "Session 2"
    assert new_sess["status"] == "ACTIVE"
    assert new_sess["id"] != first_worker_sess["id"]

    # Verify old session was closed
    old_sess_db = db.get_conversation(first_worker_sess["id"])
    assert old_sess_db["status"] == "CLOSED"

    # 6. Send a message in Session 2
    send_resp2 = client.post("/api/v1/chat/fe-worker-test/messages", json={
        "content": "Message in Session 2",
        "conversation_id": new_sess["id"]
    })
    assert send_resp2.status_code == 200

    # 7. Check message isolation: Session 1 has only msg 1; Session 2 has only msg 2
    hist_sess1 = client.get(f"/api/v1/chat/fe-worker-test/messages?conversation_id={first_worker_sess['id']}")
    assert hist_sess1.status_code == 200
    s1_msgs = [m["content"] for m in hist_sess1.json()["messages"]]
    assert "Message in Session 1" in s1_msgs
    assert "Message in Session 2" not in s1_msgs

    hist_sess2 = client.get(f"/api/v1/chat/fe-worker-test/messages?conversation_id={new_sess['id']}")
    assert hist_sess2.status_code == 200
    s2_msgs = [m["content"] for m in hist_sess2.json()["messages"]]
    assert "Message in Session 2" in s2_msgs
    assert "Message in Session 1" not in s2_msgs

    # 8. Switch back to Session 1 via activate
    act_resp = client.post(f"/api/v1/chat/fe-worker-test/sessions/{first_worker_sess['id']}/activate")
    assert act_resp.status_code == 200
    assert act_resp.json()["session"]["status"] == "ACTIVE"

    # Verify Session 2 is now closed
    s2_db = db.get_conversation(new_sess["id"])
    assert s2_db["status"] == "CLOSED"


def test_no_duplicate_execution_messages_on_poll(client):
    """
    Test that repeated polling of GET /messages does NOT duplicate user prompts or assistant outputs.
    """
    db = get_db_manager()
    agent_id = "eng-manager-test"
    from config import AgentConfig
    agent = AgentConfig(
        id=agent_id,
        name="Engineering Manager",
        description="Engineering Manager",
        system_prompt="You manage engineers."
    )
    db.save_agent(agent)

    # Clear chat
    client.post(f"/api/v1/chat/{agent_id}/clear")

    # Send a single task
    send_resp = client.post(f"/api/v1/chat/{agent_id}/messages", json={
        "content": "Check repository branches"
    })
    assert send_resp.status_code == 200

    # Poll multiple times consecutively
    p1 = client.get(f"/api/v1/chat/{agent_id}/messages").json()["messages"]
    p2 = client.get(f"/api/v1/chat/{agent_id}/messages").json()["messages"]
    p3 = client.get(f"/api/v1/chat/{agent_id}/messages").json()["messages"]

    # There should only be exactly ONE user message with this content
    user_prompts = [m for m in p3 if m["sender_type"] == "USER" and m["content"] == "Check repository branches"]
    assert len(user_prompts) == 1
    assert len(p1) == len(p2) == len(p3)

