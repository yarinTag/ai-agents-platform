"""
Automated tests for database cleaning and strict max 18 agents capacity limit.
Verifies that:
- clean_database() resets the database to the 11 baseline agents (<= 18).
- The platform strictly enforces a maximum capacity of 18 agents.
- Attempting to save a 19th agent is rejected by both persistence layer and API.
"""

import pytest
import httpx
from datetime import datetime

from config import AgentConfig, AgentRole
from persistence import db_manager
from backend.main import app
from backend.dependencies import init_services, shutdown_services


@pytest.mark.asyncio
async def test_clean_database_has_baseline_agents_under_18():
    """Verify clean_database() resets DB to clean state with <= 18 agents (11 baseline)."""
    db_manager.clean_database(seed_baseline=True)
    agents = db_manager.list_agents()
    assert len(agents) == 11, f"Expected 11 baseline agents, got {len(agents)}"
    assert len(agents) <= 18, "Max agents must be <= 18"

    # Verify key canonical agents exist
    agent_ids = {a.id for a in agents}
    assert "chief-orchestrator" in agent_ids
    assert "marketing-lead" in agent_ids
    assert "lead-engineer" in agent_ids
    assert "delivery-lead" in agent_ids


def test_max_agents_capacity_enforced_in_db():
    """Verify persistence layer strictly rejects adding agents beyond the max capacity of 18."""
    db_manager.clean_database(seed_baseline=True)
    current_count = len(db_manager.list_agents())
    assert current_count == 11

    # Add agents up to exactly 18
    added_ids = []
    for i in range(current_count, 18):
        agent_id = f"test-fill-agent-{i}"
        agent = AgentConfig(
            id=agent_id,
            name=f"Fill Agent {i}",
            description="Capacity testing agent",
            system_prompt="Test agent",
            department="Engineering"
        )
        db_manager.save_agent(agent)
        added_ids.append(agent_id)

    total_agents = db_manager.list_agents()
    assert len(total_agents) == 18, f"Expected exactly 18 agents, got {len(total_agents)}"

    # Attempt to add a 19th agent - MUST RAISE ValueError
    overflow_agent = AgentConfig(
        id="test-overflow-agent-19",
        name="Overflow Agent",
        description="Should fail",
        system_prompt="Test agent",
        department="Engineering"
    )
    with pytest.raises(ValueError, match="Platform agent capacity reached: maximum 18 agents allowed"):
        db_manager.save_agent(overflow_agent)

    # Clean up the fill agents
    for aid in added_ids:
        db_manager.delete_agent(aid)

    assert len(db_manager.list_agents()) == 11


@pytest.mark.asyncio
async def test_max_agents_capacity_enforced_in_api():
    """Verify POST /api/v1/agents/ returns HTTP 400 when platform reaches 18 agents capacity."""
    db_manager.clean_database(seed_baseline=True)
    await init_services()

    # Fill up to 18 agents
    added_ids = []
    for i in range(11, 18):
        agent_id = f"api-fill-agent-{i}"
        agent = AgentConfig(
            id=agent_id,
            name=f"API Fill Agent {i}",
            description="Testing capacity",
            system_prompt="Test",
            department="Engineering"
        )
        db_manager.save_agent(agent)
        added_ids.append(agent_id)

    assert len(db_manager.list_agents()) == 18

    # Attempt to create 19th agent via API
    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        resp = await client.post("/api/v1/agents/", json={
            "name": "API Overflow Agent",
            "description": "Should fail",
            "system_prompt": "Test agent",
            "department": "Engineering"
        })
        assert resp.status_code == 400
        assert "capacity reached" in resp.text.lower()
        assert "18" in resp.text

    # Clean up
    for aid in added_ids:
        db_manager.delete_agent(aid)
    await shutdown_services()


def test_db_agent_count_in_tests_never_exceeds_18():
    """Verify that current agents in DB does not exceed 18."""
    agents = db_manager.list_agents()
    assert len(agents) <= 18, f"Database currently has {len(agents)} agents, which exceeds maximum of 18"
