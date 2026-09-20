"""
Dependency initialization and shared services for the AI Agents Platform API.

This module is the single import bridge between the backend API package
and the root-level PoC modules (config, persistence, runtime_adapter).
The sys.path setup happens here only — no other API file should modify sys.path.
"""

import asyncio
import logging
from typing import Optional

# Add PoC root to path ONCE here — the single place for this resolution
import sys
import os
_poc_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _poc_root not in sys.path:
    sys.path.insert(0, _poc_root)

from config import config_manager, ConfigManager, AgentConfig, ProjectConfig, Skill
from persistence import db_manager, DatabaseManager
from runtime_adapter import runtime_adapter, ClaudeCodeRuntimeAdapter, AgentRun, TaskStatus

logger = logging.getLogger(__name__)

# Service containers
_services_initialized = False
_background_tasks = set()


async def init_services():
    """Initialize all backend services."""
    global _services_initialized

    if _services_initialized:
        return

    try:
        agents = config_manager.list_agents()
        projects = config_manager.list_projects()
        db_agents = db_manager.list_agents()
        db_projects = db_manager.list_projects()

        _services_initialized = True
        logger.info(
            "Backend services initialized: %d config agents, %d DB agents, %d projects",
            len(agents), len(db_agents), len(db_projects)
        )

    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
        raise


async def shutdown_services():
    """Shutdown all backend services."""
    global _services_initialized, _background_tasks

    for task in _background_tasks:
        if not task.done():
            task.cancel()

    if _background_tasks:
        await asyncio.gather(*_background_tasks, return_exceptions=True)

    _background_tasks.clear()
    _services_initialized = False
    logger.info("Backend services shut down")


def get_config_manager() -> ConfigManager:
    """Get the config manager instance."""
    return config_manager


def get_db_manager() -> DatabaseManager:
    """Get the database manager instance."""
    return db_manager


def get_runtime_adapter() -> ClaudeCodeRuntimeAdapter:
    """Get the runtime adapter instance."""
    return runtime_adapter