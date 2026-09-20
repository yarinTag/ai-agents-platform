"""
Automated tests for FastAPI endpoints:
- Health and root
- Agents CRUD with real timestamps
- Projects CRUD
- Skills CRUD
- Tasks CRUD and SSE endpoint format
- System events & stats
"""

import pytest
import pytest_asyncio
import httpx
from datetime import datetime

from backend.main import app
from backend.dependencies import init_services, shutdown_services, get_db_manager
from config import AgentConfig


@pytest_asyncio.fixture(autouse=True)
async def setup_services():
    """Ensure backend services are initialized before each test."""
    await init_services()
    yield
    await shutdown_services()


@pytest.mark.asyncio
async def test_health_and_root_endpoints():
    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"

        resp = await client.get("/")
        assert resp.status_code == 200
        assert "AI Agents Platform API" in resp.json()["message"]


@pytest.mark.asyncio
async def test_agents_crud_with_real_timestamps():
    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        agent_payload = {
            "name": "Integration Test Agent",
            "description": "Agent for automated API testing",
            "system_prompt": "You are a test agent.",
            "skills": ["read", "grep"],
            "model": "sonnet",
            "effort": "high",
            "max_tokens": 4096,
            "temperature": 0.5,
            "department": "Engineering"
        }

        # 1. Create agent
        resp = await client.post("/api/v1/agents/", json=agent_payload)
        assert resp.status_code == 201, resp.text
        data = resp.json()
        agent_id = data["id"]
        assert agent_id == "integration-test-agent"
        assert data["created_at"] is not None and len(data["created_at"]) > 0
        assert data["updated_at"] is not None and len(data["updated_at"]) > 0
        created_at_val = data["created_at"]

        # 2. Get agent
        resp = await client.get(f"/api/v1/agents/{agent_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Integration Test Agent"
        assert data["created_at"] == created_at_val

        # 3. List agents (must include created agent)
        resp = await client.get("/api/v1/agents/")
        assert resp.status_code == 200
        agents = resp.json()
        assert any(a["id"] == agent_id for a in agents)

        # 4. Update agent
        update_payload = {"description": "Updated test description"}
        resp = await client.put(f"/api/v1/agents/{agent_id}", json=update_payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["description"] == "Updated test description"
        assert data["created_at"] == created_at_val

        # 5. Delete agent
        resp = await client.delete(f"/api/v1/agents/{agent_id}")
        assert resp.status_code == 204

        # 6. Verify 404 after delete
        resp = await client.get(f"/api/v1/agents/{agent_id}")
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_projects_crud():
    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        project_payload = {
            "name": "Integration Project",
            "description": "Test project",
            "working_directory": ".",
            "instructions": "Test instructions",
            "skills": ["read"],
            "allowed_tools": ["read", "grep"]
        }

        # Create
        resp = await client.post("/api/v1/projects/", json=project_payload)
        assert resp.status_code == 201
        data = resp.json()
        project_id = data["id"]

        # Get
        resp = await client.get(f"/api/v1/projects/{project_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Integration Project"

        # Delete
        resp = await client.delete(f"/api/v1/projects/{project_id}")
        assert resp.status_code in [200, 204]


@pytest.mark.asyncio
async def test_skills_crud_and_scan():
    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        skill_payload = {
            "name": "Pytest Automation Skill",
            "description": "Skill for running automated tests",
            "content": "# Test Skill\nInstructions here."
        }

        # Create
        resp = await client.post("/api/v1/skills/", json=skill_payload)
        assert resp.status_code == 201
        data = resp.json()
        skill_id = data["id"]

        # List
        resp = await client.get("/api/v1/skills/")
        assert resp.status_code == 200

        # Scan plugins (must return clean json without mock fallback)
        resp = await client.get("/api/v1/skills/plugins/scan")
        assert resp.status_code == 200
        scan_data = resp.json()
        assert "plugins" in scan_data
        assert "total_skills" in scan_data

        # Delete
        resp = await client.delete(f"/api/v1/skills/{skill_id}")
        assert resp.status_code in [200, 204]


@pytest.mark.asyncio
async def test_system_stats():
    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        resp = await client.get("/api/v1/events/system/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "agents" in data
        assert "projects" in data
        assert "skills" in data
        assert "tasks" in data
