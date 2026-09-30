"""
Global pytest configuration and cleanup fixtures for AI Agents Platform.
Ensures the database is clean, test agents are isolated and cleaned up,
and the total number of agents in the database never exceeds 18.
"""

import pytest
import os
import sys
from pathlib import Path

# Ensure poc directory is in sys.path
poc_dir = Path(__file__).resolve().parent.parent
if str(poc_dir) not in sys.path:
    sys.path.insert(0, str(poc_dir))

from persistence import db_manager
from config import config_manager


def pytest_sessionstart(session):
    """Clean and initialize database to baseline state at the start of pytest session."""
    db_manager.clean_database(seed_baseline=True)


@pytest.fixture(autouse=True)
def clean_test_agents_after_each_test():
    """
    Autouse fixture to prevent test agents from accumulating in the database.
    Ensures that test-created agents are deleted after each test and
    the agent count strictly respects the platform maximum of 18 agents.

    The agents API writes to BOTH stores (db_manager and the ConfigManager
    JSON file), so both are snapshotted and cleaned. Cleaning only the DB
    leaks test agents into poc/config/agents.json, where they survive the
    session and make later runs fail with "agent already exists".
    """
    # Snapshot existing agents before test (both persistence stores)
    initial_agent_ids = {a.id for a in db_manager.list_agents()}
    initial_config_agent_ids = {a.id for a in config_manager.list_agents()}

    yield

    # Clean up any new agents created during the test
    current_agents = db_manager.list_agents()
    for agent in current_agents:
        if agent.id not in initial_agent_ids:
            try:
                db_manager.delete_agent(agent.id)
            except Exception:
                pass

    for agent in config_manager.list_agents():
        if agent.id not in initial_config_agent_ids:
            try:
                config_manager.delete_agent(agent.id)
            except Exception:
                pass

    # Invariant: At all times after cleanup, agents in DB must be <= 18
    remaining = db_manager.list_agents()
    assert len(remaining) <= 18, f"Max agents exceeded: {len(remaining)} agents in DB"
