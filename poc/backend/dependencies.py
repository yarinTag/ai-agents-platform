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

from config import config_manager, ConfigManager, AgentConfig, AgentRole, AgentTemplate, ProjectConfig, Skill
from persistence import db_manager, DatabaseManager
from runtime_adapter import runtime_adapter, ClaudeCodeRuntimeAdapter, AgentRun, TaskStatus
from runtime.claude_adapter import ClaudeCodeAdapter
from events import EventBus, EventService, PlatformEvent, EventType
from orchestration import (
    validate_agent_hierarchy, HierarchyValidationError, OrchestrationEngine,
    DelegationError, ConcurrencyLimitExceededError
)
from .cron_engine import CronSchedulerEngine

logger = logging.getLogger(__name__)

# Service containers
_services_initialized = False
_background_tasks = set()
_event_bus: Optional[EventBus] = None
_event_service: Optional[EventService] = None
_claude_adapter: Optional[ClaudeCodeAdapter] = None
_orchestration_engine: Optional[OrchestrationEngine] = None
_cron_engine: Optional[CronSchedulerEngine] = None


async def init_services():
    """Initialize all backend services."""
    global _services_initialized, _event_bus, _event_service, _claude_adapter, _orchestration_engine, _cron_engine

    if _services_initialized:
        return

    try:
        agents = config_manager.list_agents()
        projects = config_manager.list_projects()
        db_agents = db_manager.list_agents()
        db_projects = db_manager.list_projects()

        if _event_bus is None:
            _event_bus = EventBus()
        if _event_service is None:
            _event_service = EventService(db_manager=db_manager, event_bus=_event_bus)
        if _claude_adapter is None:
            _claude_adapter = ClaudeCodeAdapter(runtime_adapter)
        if _orchestration_engine is None:
            _orchestration_engine = OrchestrationEngine(
                db_manager=db_manager,
                runtime_adapter=runtime_adapter,
                event_service=_event_service
            )
        if _cron_engine is None:
            _cron_engine = CronSchedulerEngine(
                db_manager=db_manager,
                runtime_adapter=_claude_adapter,
                event_bus=_event_bus
            )
            _cron_engine.start()

        _services_initialized = True
        logger.info(
            "Backend services initialized: %d config agents, %d DB agents, %d projects, cron engine and event bus ready",
            len(agents), len(db_agents), len(db_projects)
        )

    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
        raise


async def shutdown_services():
    """Shutdown all backend services."""
    global _services_initialized, _background_tasks, _cron_engine

    if _cron_engine:
        await _cron_engine.stop()

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


def get_event_bus() -> EventBus:
    """Get the global EventBus singleton instance."""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


def get_event_service() -> EventService:
    """Get the global EventService singleton instance."""
    global _event_service
    if _event_service is None:
        _event_service = EventService(db_manager=get_db_manager(), event_bus=get_event_bus())
    return _event_service


def get_runtime_adapter() -> ClaudeCodeAdapter:
    """Get the runtime adapter instance returning ClaudeCodeAdapter wrapping runtime_adapter."""
    global _claude_adapter
    if _claude_adapter is None:
        _claude_adapter = ClaudeCodeAdapter(runtime_adapter)
    return _claude_adapter


def get_orchestration_engine() -> OrchestrationEngine:
    """Get the global OrchestrationEngine singleton instance."""
    global _orchestration_engine
    if _orchestration_engine is None:
        _orchestration_engine = OrchestrationEngine(
            db_manager=get_db_manager(),
            runtime_adapter=runtime_adapter,
            event_service=get_event_service()
        )
    return _orchestration_engine


def get_cron_engine() -> Optional[CronSchedulerEngine]:
    """Get the global CronSchedulerEngine instance."""
    global _cron_engine
    return _cron_engine