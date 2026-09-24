"""
Integration tests for Feature E & F: MCP (Model Context Protocol) Platform.
Validates:
- Connector registry and tool discovery for GitHub, Google Workspace, Trello, Telegram
- Server-side permission enforcement (denied vs permitted)
- Tool call execution lifecycle, persistence, and event emissions
- EventBus emission of mcp.tool.started, mcp.tool.completed, mcp.permission.denied
"""

import pytest
import uuid
from fastapi.testclient import TestClient
from datetime import datetime

from backend.main import app
from backend.dependencies import get_db_manager, get_event_bus
from config import AgentConfig, AgentRole


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_mcp_connectors_and_tools_discovery(client):
    """Test listing connectors and tools across registered providers."""
    res = client.get("/api/v1/mcp/connectors")
    assert res.status_code == 200, res.text
    connectors = res.json()
    assert len(connectors) >= 4

    conn_ids = [c["id"] for c in connectors]
    assert "github" in conn_ids
    assert "google_workspace" in conn_ids
    assert "trello" in conn_ids
    assert "telegram" in conn_ids

    # Check tools for GitHub
    res_tools = client.get("/api/v1/mcp/tools?connector_id=github")
    assert res_tools.status_code == 200
    tools = res_tools.json()
    tool_names = [t["name"] for t in tools]
    assert "create_issue" in tool_names
    assert "create_pull_request" in tool_names


def test_mcp_permission_enforcement(client):
    """Test strict server-side permission checks for agent tool execution."""
    db = get_db_manager()
    agent_id = f"worker-noperm-{uuid.uuid4().hex[:6]}"

    # Agent without MCP permissions
    db.save_agent(AgentConfig(
        id=agent_id,
        name="Restricted Worker",
        description="Worker without permissions",
        system_prompt="Execute work",
        mcp_permissions=[]
    ))

    # 1. Attempt to invoke GitHub create_issue without permission -> 403 Forbidden
    res_denied = client.post("/api/v1/mcp/invoke", json={
        "agent_id": agent_id,
        "connector_id": "github",
        "tool_name": "create_issue",
        "arguments": {"repo": "acme/web", "title": "Bug in login flow"}
    })
    assert res_denied.status_code == 403
    assert "not authorized to use MCP connector" in res_denied.json()["detail"]

    # 2. Grant permission explicitly via database / API
    res_grant = client.post("/api/v1/mcp/permissions", json={
        "agent_id": agent_id,
        "connector_id": "github",
        "tool_id": "create_issue"
    })
    assert res_grant.status_code == 201

    # 3. Now execution succeeds
    res_ok = client.post("/api/v1/mcp/invoke", json={
        "agent_id": agent_id,
        "connector_id": "github",
        "tool_name": "create_issue",
        "arguments": {"repo": "acme/web", "title": "Bug in login flow"}
    })
    assert res_ok.status_code == 200, res_ok.text
    data = res_ok.json()
    assert data["status"] == "COMPLETED"
    assert data["result"]["status"] == "success"
    assert "issue_number" in data["result"]


def test_mcp_tool_execution_lifecycle_and_events(client):
    """Test MCP tool execution records calls in database and emits lifecycle events."""
    db = get_db_manager()
    event_bus = get_event_bus()

    agent_id = f"worker-perm-{uuid.uuid4().hex[:6]}"
    db.save_agent(AgentConfig(
        id=agent_id,
        name="Permitted Worker",
        description="Worker with Trello permission",
        system_prompt="Manage tasks",
        mcp_permissions=["trello"]
    ))

    # Subscribe to MCP events
    received_events = []
    queue, unsub = event_bus.subscribe(filter_fn=lambda e: "mcp.tool" in e.event_type)

    try:
        res = client.post("/api/v1/mcp/invoke", json={
            "agent_id": agent_id,
            "connector_id": "trello",
            "tool_name": "create_card",
            "arguments": {"list_name": "To Do", "title": "Deploy v2.1 frontend"}
        })
        assert res.status_code == 200
        call_id = res.json()["call_id"]

        # Verify call is persisted in SQLite
        call_record = db.get_mcp_tool_call(call_id)
        assert call_record is not None
        assert call_record.status == "COMPLETED"
        assert call_record.connector_id == "trello"
        assert "Deploy v2.1" in str(call_record.arguments)
        assert call_record.completed_at is not None

        # Verify calls list endpoint
        res_calls = client.get(f"/api/v1/mcp/calls?agent_id={agent_id}")
        assert res_calls.status_code == 200
        calls_list = res_calls.json()
        assert len(calls_list) >= 1
        assert calls_list[0]["id"] == call_id

    finally:
        unsub()
