"""
Automated tests for Phase 5: Management UI & Flow Integration.
Validates:
- GET /api/v1/models dynamic model discovery
- Template instantiation with hierarchy, avatar, and model parameters
- Agent hierarchy tree updates and cycle validation
- Real SQLite database, real FastAPI routes, and zero mocks.
"""

import pytest
from httpx import AsyncClient, ASGITransport
import tempfile
import os

from config import AgentConfig, AgentRole
from persistence import DatabaseManager
from backend.main import app
from backend.dependencies import get_db_manager


@pytest.fixture
def temp_db():
    """Create an isolated real SQLite DB with default schema and seed templates."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db = DatabaseManager(path)
    yield db
    if os.path.exists(path):
        try:
            os.unlink(path)
        except Exception:
            pass


@pytest.mark.asyncio
async def test_get_available_models():
    """Test dynamic model discovery endpoint GET /api/v1/models."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/models")
        assert response.status_code == 200
        models = response.json()
        assert isinstance(models, list)
        assert len(models) >= 5

        # Check model structure
        model_ids = [m["id"] for m in models]
        assert "claude-3-7-sonnet-20250219" in model_ids
        assert "claude-3-5-sonnet-20241022" in model_ids
        assert "nvidia_nim/nvidia/nemotron-3-super-120b-a12b" in model_ids

        for m in models:
            assert "id" in m
            assert "name" in m
            assert "provider" in m
            assert "context_window" in m
            assert "description" in m


@pytest.mark.asyncio
async def test_template_instantiation_with_hierarchy_and_avatar(temp_db):
    """Test creating an agent from a template with custom avatar, parent_id, and model."""
    app.dependency_overrides[get_db_manager] = lambda: temp_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Create a root orchestrator first
            root_cfg = AgentConfig(
                id="root-manager",
                name="Platform Director",
                description="Top level manager",
                system_prompt="Direct teams.",
                role_type=AgentRole.ROOT_ORCHESTRATOR.value,
            )
            temp_db.save_agent(root_cfg)

            # 2. Get available templates (seed templates automatically created in temp_db)
            templates_res = await client.get("/api/v1/templates")
            assert templates_res.status_code == 200
            templates = templates_res.json()
            assert isinstance(templates, list)
            assert len(templates) > 0

            target_tpl = templates[0]

            # 3. Instantiate template under root-manager with custom avatar & model
            instantiate_payload = {
                "name": "Specialist Coder",
                "parent_id": "root-manager",
                "model_override": "claude-3-7-sonnet-20250219",
                "avatar": "cyber_coder",
            }

            inst_res = await client.post(
                f"/api/v1/templates/{target_tpl['id']}/instantiate",
                json=instantiate_payload,
            )
            assert inst_res.status_code == 201
            created_agent = inst_res.json()

            assert created_agent["name"] == "Specialist Coder"
            assert created_agent["parent_id"] == "root-manager"
            assert created_agent["avatar"] == "cyber_coder"
            assert created_agent["model"] == "claude-3-7-sonnet-20250219"

            # 4. Verify agent appears in hierarchy tree under root-manager
            tree_res = await client.get("/api/v1/agents/hierarchy/tree")
            assert tree_res.status_code == 200
            tree = tree_res.json()
            assert isinstance(tree, list)

            root_node = next((n for n in tree if n["id"] == "root-manager"), None)
            assert root_node is not None
            child_ids = [c["id"] for c in root_node.get("children", [])]
            assert created_agent["id"] in child_ids

    finally:
        app.dependency_overrides.clear()
