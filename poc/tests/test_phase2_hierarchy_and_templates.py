"""
Automated tests for Phase 2: Agent Hierarchy, Templates, and Tree APIs.
ZERO MOCKS POLICY: All tests run against live FastAPI routes, SQLite database, and real validation.
"""

import pytest
from httpx import AsyncClient, ASGITransport
import tempfile
import os

from config import AgentConfig, AgentRole, AgentTemplate
from persistence import DatabaseManager
from orchestration import validate_agent_hierarchy, HierarchyValidationError
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
async def test_hierarchy_validator_rules(temp_db):
    """Test all organizational hierarchy constraints directly."""
    # Create a root orchestrator and manager
    root = AgentConfig(
        id="root-ceo",
        name="Root CEO",
        description="Head orchestrator",
        system_prompt="Coordinate all operations.",
        role_type=AgentRole.ROOT_ORCHESTRATOR.value
    )
    temp_db.save_agent(root)

    mgr = AgentConfig(
        id="eng-lead",
        name="Engineering Lead",
        description="Manages developers",
        system_prompt="Manage tech teams.",
        role_type=AgentRole.MANAGER.value,
        parent_id="root-ceo"
    )
    temp_db.save_agent(mgr)

    worker = AgentConfig(
        id="dev-worker",
        name="Developer Worker",
        description="Writes code",
        system_prompt="Write code.",
        role_type=AgentRole.WORKER.value,
        parent_id="eng-lead"
    )
    temp_db.save_agent(worker)

    # 1. ROOT cannot have a parent
    with pytest.raises(HierarchyValidationError, match="cannot have a parent"):
        validate_agent_hierarchy("root-2", AgentRole.ROOT_ORCHESTRATOR.value, "root-ceo", temp_db)

    # 2. Cannot be own parent
    with pytest.raises(HierarchyValidationError, match="cannot be its own parent"):
        validate_agent_hierarchy("eng-lead", AgentRole.MANAGER.value, "eng-lead", temp_db)

    # 3. Nonexistent parent
    with pytest.raises(HierarchyValidationError, match="does not exist"):
        validate_agent_hierarchy("dev-2", AgentRole.WORKER.value, "ghost-parent", temp_db)

    # 4. WORKER cannot have children
    with pytest.raises(HierarchyValidationError, match="cannot have children"):
        validate_agent_hierarchy("sub-worker", AgentRole.WORKER.value, "dev-worker", temp_db)

    # 5. Circular reference detection (eng-lead -> dev-worker -> eng-lead)
    # If we tried to make eng-lead's parent dev-worker:
    with pytest.raises(HierarchyValidationError, match="cannot have children"):
        # dev-worker is a worker, but even if it was a manager:
        validate_agent_hierarchy("eng-lead", AgentRole.MANAGER.value, "dev-worker", temp_db)

    # Test cycle with two managers:
    mgr2 = AgentConfig(
        id="mgr-2",
        name="Manager 2",
        description="Second manager",
        system_prompt="Manage.",
        role_type=AgentRole.MANAGER.value,
        parent_id="eng-lead"
    )
    temp_db.save_agent(mgr2)

    # If eng-lead tried to set mgr-2 as parent, that's an ancestor cycle
    with pytest.raises(HierarchyValidationError, match="Circular reference detected"):
        validate_agent_hierarchy("eng-lead", AgentRole.MANAGER.value, "mgr-2", temp_db)

    # 6. Demoting manager with children to WORKER
    with pytest.raises(HierarchyValidationError, match="Cannot set role of 'eng-lead' to 'WORKER'"):
        validate_agent_hierarchy("eng-lead", AgentRole.WORKER.value, "root-ceo", temp_db)


@pytest.mark.asyncio
async def test_templates_api_and_seeding(temp_db):
    """Test templates API endpoints and default seeding."""
    app.dependency_overrides[get_db_manager] = lambda: temp_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Default seeded templates should be present
        res = await client.get("/api/v1/templates/")
        assert res.status_code == 200
        templates = res.json()
        assert len(templates) >= 3
        template_ids = [t["id"] for t in templates]
        assert "engineering-manager" in template_ids
        assert "frontend-developer" in template_ids
        assert "backend-developer" in template_ids

        # Get specific template
        res = await client.get("/api/v1/templates/frontend-developer")
        assert res.status_code == 200
        data = res.json()
        assert data["name"] == "Frontend Developer"
        assert data["role"] == "WORKER"

        # Create new template
        new_tpl = {
            "name": "Security Auditor",
            "description": "Performs code security audits",
            "role": "SPECIALIST",
            "system_prompt": "Audit source code for OWASP vulnerabilities.",
            "category": "Security",
            "tools": ["grep_search", "read_files"]
        }
        res = await client.post("/api/v1/templates/", json=new_tpl)
        assert res.status_code == 201
        created = res.json()
        assert created["id"] == "security-auditor"
        assert created["category"] == "Security"

        # Filter by category
        res = await client.get("/api/v1/templates/?category=Security")
        assert res.status_code == 200
        sec_templates = res.json()
        assert len(sec_templates) == 1
        assert sec_templates[0]["id"] == "security-auditor"

        # Delete template
        res = await client.delete("/api/v1/templates/security-auditor")
        assert res.status_code == 204

        # Verify deletion
        res = await client.get("/api/v1/templates/security-auditor")
        assert res.status_code == 404

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_template_instantiation_and_hierarchy_tree(temp_db):
    """Test instantiating agents from templates and querying hierarchy trees."""
    app.dependency_overrides[get_db_manager] = lambda: temp_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Instantiate an Engineering Manager
            mgr_payload = {
                "name": "VP of Architecture",
                "department": "Architecture",
                "repo_path": "/workspace"
            }
            res = await client.post("/api/v1/templates/engineering-manager/instantiate", json=mgr_payload)
            assert res.status_code == 201
            mgr = res.json()
            assert mgr["id"] == "vp-of-architecture"
            assert mgr["role_type"] == "MANAGER"
            assert mgr["template_id"] == "engineering-manager"

            # 2. Instantiate a Frontend Developer reporting to the VP
            dev_payload = {
                "name": "Lead UI Engineer",
                "parent_id": "vp-of-architecture",
                "department": "Frontend"
            }
            res = await client.post("/api/v1/templates/frontend-developer/instantiate", json=dev_payload)
            assert res.status_code == 201
            dev = res.json()
            assert dev["id"] == "lead-ui-engineer"
            assert dev["parent_id"] == "vp-of-architecture"
            assert dev["role_type"] == "WORKER"

            # 3. Query VP's children
            res = await client.get("/api/v1/agents/vp-of-architecture/children")
            assert res.status_code == 200
            children = res.json()
            assert len(children) == 1
            assert children[0]["id"] == "lead-ui-engineer"

            # 4. Query VP's subtree
            res = await client.get("/api/v1/agents/vp-of-architecture/hierarchy")
            assert res.status_code == 200
            subtree = res.json()
            assert len(subtree) == 1
            assert subtree[0]["id"] == "vp-of-architecture"
            assert len(subtree[0]["children"]) == 1
            assert subtree[0]["children"][0]["id"] == "lead-ui-engineer"

            # 5. Query entire hierarchy tree
            res = await client.get("/api/v1/agents/hierarchy/tree")
            assert res.status_code == 200
            forest = res.json()
            assert len(forest) >= 1
            arch_roots = [tree for tree in forest if tree["id"] == "vp-of-architecture"]
            assert len(arch_roots) == 1

            # 6. Deleting manager with active children must be blocked
            res = await client.delete("/api/v1/agents/vp-of-architecture")
            assert res.status_code == 400
            assert "subordinate child agents" in res.json()["detail"]

            # 7. Delete child first, then delete manager
            res = await client.delete("/api/v1/agents/lead-ui-engineer")
            assert res.status_code == 204

            res = await client.delete("/api/v1/agents/vp-of-architecture")
            assert res.status_code == 204
    finally:
        app.dependency_overrides.clear()
