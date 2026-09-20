"""
Dependency initialization and shared services for the AI Agents Platform API.
"""

import asyncio
from typing import Optional

# Import existing PoC components
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import config_manager
from persistence import db_manager
from runtime_adapter import runtime_adapter


# Service containers
_services_initialized = False
_background_tasks = set()


async def init_services():
    """Initialize all backend services."""
    global _services_initialized

    if _services_initialized:
        return

    # Initialize existing PoC components
    # These are already initialized as global instances in their respective modules
    # but we can perform any async initialization here if needed

    # For now, just verify they're accessible
    try:
        # Test config manager
        agents = config_manager.list_agents()
        projects = config_manager.list_projects()

        # Test persistence
        db_agents = db_manager.list_agents()
        db_projects = db_manager.list_projects()

        # Test runtime adapter (no async init needed)

        _services_initialized = True
        print("✅ Backend services initialized successfully")

    except Exception as e:
        print(f"❌ Failed to initialize services: {e}")
        raise


async def shutdown_services():
    """Shutdown all backend services."""
    global _services_initialized, _background_tasks

    # Cancel any background tasks
    for task in _background_tasks:
        if not task.done():
            task.cancel()

    # Wait for cancellation
    if _background_tasks:
        await asyncio.gather(*_background_tasks, return_exceptions=True)

    _background_tasks.clear()
    _services_initialized = False
    print("✅ Backend services shut down")


def get_config_manager():
    """Get the config manager instance."""
    return config_manager


def get_db_manager():
    """Get the database manager instance."""
    return db_manager


def get_runtime_adapter():
    """Get the runtime adapter instance."""
    return runtime_adapter