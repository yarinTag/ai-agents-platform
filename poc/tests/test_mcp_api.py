"""
Test Suite for MCP API:
Verifies:
1. Catalog listing with Git, Trello, Telegram, Slack, etc.
2. Installing an MCP connector.
3. Listing installed connectors.
4. Testing connection (ping).
5. Viewing tools exposed by connector.
6. Granting and revoking agent access permissions.
7. Deleting / uninstalling connector.
"""

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from persistence import db_manager


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_mcp_catalog_contains_expected_integrations(client):
    """Verify that catalog includes git, trello, telegram, slack."""
    resp = client.get("/api/v1/mcp/catalog")
    assert resp.status_code == 200
    catalog = resp.json().get("catalog", [])
    providers = [item["provider"] for item in catalog]

    assert "github" in providers
    assert "trello" in providers
    assert "telegram" in providers
    assert "slack" in providers
    assert "postgres" in providers
    assert "brave-search" in providers
    assert "filesystem" in providers


def test_mcp_connector_lifecycle_and_tools(client):
    """Test installing, pinging, listing tools, and deleting a connector."""
    # 1. Install Trello connector
    payload = {
        "name": "Sprint Trello Board",
        "provider": "trello",
        "configuration": {
            "api_key": "dummy_trello_key",
            "token": "dummy_trello_token",
            "board_id": "test_board_123"
        }
    }
    install_resp = client.post("/api/v1/mcp/connectors", json=payload)
    assert install_resp.status_code == 201
    conn_data = install_resp.json()
    conn_id = conn_data["id"]
    assert conn_data["name"] == "Sprint Trello Board"
    assert conn_data["status"] == "CONNECTED"

    # 2. Verify tools were auto-registered from catalog
    tools_resp = client.get(f"/api/v1/mcp/connectors/{conn_id}/tools")
    assert tools_resp.status_code == 200
    tools = tools_resp.json().get("tools", [])
    tool_names = [t["name"] for t in tools]
    assert "get_cards_by_list_id" in tool_names
    assert "add_card_to_list" in tool_names

    # 3. Test ping
    test_resp = client.post(f"/api/v1/mcp/connectors/{conn_id}/test")
    assert test_resp.status_code == 200
    assert test_resp.json()["status"] == "CONNECTED"

    # 4. Permissions grant & revoke
    agents = db_manager.list_agents()
    if agents:
        agent_id = agents[0].id
        grant_resp = client.post("/api/v1/mcp/permissions/grant", json={
            "agent_id": agent_id,
            "connector_id": conn_id
        })
        assert grant_resp.status_code == 200

        # Check permissions
        perms_resp = client.get(f"/api/v1/mcp/permissions?agent_id={agent_id}")
        assert perms_resp.status_code == 200
        perms = perms_resp.json().get("permissions", [])
        assert any(p["connector_id"] == conn_id for p in perms)

        # Revoke
        revoke_resp = client.post("/api/v1/mcp/permissions/revoke", json={
            "agent_id": agent_id,
            "connector_id": conn_id
        })
        assert revoke_resp.status_code == 200

    # 5. Delete connector
    del_resp = client.delete(f"/api/v1/mcp/connectors/{conn_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "success"

    # 6. Verify deleted
    get_resp = client.get(f"/api/v1/mcp/connectors/{conn_id}")
    assert get_resp.status_code == 404


def test_discover_resources_github_and_slack(client):
    """Verify repository discovery and Slack channel discovery."""
    # 1. Discover GitHub repos
    gh_resp = client.post("/api/v1/mcp/discover-resources", json={"provider": "github"})
    assert gh_resp.status_code == 200
    repos = gh_resp.json().get("repositories", [])
    assert len(repos) > 0
    repo_names = [r["name"] for r in repos]
    assert "ai-agents-platform" in repo_names

    # 2. Discover Slack channels
    slack_resp = client.post("/api/v1/mcp/discover-resources", json={"provider": "slack"})
    assert slack_resp.status_code == 200
    channels = slack_resp.json().get("channels", [])
    ch_names = [c["name"] for c in channels]
    assert "#general" in ch_names
    assert "#pr-review" in ch_names


def test_workflow_channel_binding_and_execution_notification(client):
    """Verify binding a Slack channel to a workflow and testing message posting."""
    # 1. Create a test workflow
    wf_payload = {
        "name": "Channel Triggered Review",
        "description": "Workflow with Slack channel binding",
        "definition_yaml": """id: wf-slack-test
name: Channel Triggered Review
steps:
  - key: step1
    name: Echo Step
    agent_id: auto-agent
    prompt_template: Hello from channel
"""
    }
    wf_resp = client.post("/api/v1/workflows/", json=wf_payload)
    assert wf_resp.status_code == 201
    wf_id = wf_resp.json()["id"]

    # 2. Bind Slack channel to workflow
    bind_resp = client.post(f"/api/v1/workflows/{wf_id}/channel-binding", json={
        "provider": "slack",
        "channel_id": "#pr-review",
        "trigger_enabled": True,
        "notify_mode": "ON_COMPLETE",
        "message_template": "Report: {{workflow_name}} is {{status}}"
    })
    assert bind_resp.status_code == 200
    bound_wf = bind_resp.json()
    assert bound_wf["channel_binding"] is not None
    assert bound_wf["channel_binding"]["channel_id"] == "#pr-review"
    assert bound_wf["channel_binding"]["trigger_enabled"] is True

    # 3. Test sending channel message
    msg_resp = client.post("/api/v1/mcp/test-channel-message", json={
        "provider": "slack",
        "channel_id": "#pr-review",
        "message": "Ping from workflow test"
    })
    assert msg_resp.status_code == 200
    assert msg_resp.json()["status"] == "success"

    # 4. Unbind channel
    unbind_resp = client.delete(f"/api/v1/workflows/{wf_id}/channel-binding")
    assert unbind_resp.status_code == 200
    assert unbind_resp.json().get("channel_binding") is None
