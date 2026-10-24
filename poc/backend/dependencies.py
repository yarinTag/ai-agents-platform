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
from persistence import db_manager, DatabaseManager, WorkflowRevisionConflict
from runtime_adapter import runtime_adapter, ClaudeCodeRuntimeAdapter, AgentRun, TaskStatus
import runtime_providers
from runtime.protocol import RuntimeAdapter, RuntimeCapabilities
from runtime.claude_adapter import ClaudeCodeAdapter
from runtime.registry import runtime_registry, RuntimeRegistry
from runtime.model_policy import model_policy_resolver, ModelPolicyResolver
from events import EventBus, EventService, PlatformEvent, EventType
from orchestration import (
    validate_agent_hierarchy, HierarchyValidationError, OrchestrationEngine,
    DelegationError, ConcurrencyLimitExceededError,
    validate_agent_communication, CommunicationAuthorizationError,
    ProjectIntelligence, TeamCoordinator
)
from .cron_engine import CronSchedulerEngine
from .queue import get_message_broker, get_queue_worker, TaskQueuePublisher, MessageBroker, QueueWorkerDaemon

logger = logging.getLogger(__name__)

# Service containers
_services_initialized = False
_background_tasks = set()
_event_bus: Optional[EventBus] = None
_event_service: Optional[EventService] = None
_claude_adapter: Optional[ClaudeCodeAdapter] = None
_orchestration_engine: Optional[OrchestrationEngine] = None
_cron_engine: Optional[CronSchedulerEngine] = None
_project_intelligence: Optional[ProjectIntelligence] = None
_team_coordinator: Optional[TeamCoordinator] = None


async def init_services():
    """Initialize all backend services."""
    global _services_initialized, _event_bus, _event_service, _claude_adapter, _orchestration_engine, _cron_engine, _project_intelligence, _team_coordinator

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
            runtime_registry.register("claude_code", _claude_adapter, set_default=True)
        if _orchestration_engine is None:
            _orchestration_engine = OrchestrationEngine(
                db_manager=db_manager,
                runtime_adapter=_claude_adapter,
                event_service=_event_service
            )
            runtime_adapter.on_task_completed = _orchestration_engine.handle_task_completion
            try:
                _orchestration_engine.recover_pending_tasks()
            except Exception as e:
                logger.warning(f"Error during startup pending task recovery: {e}")
        if _cron_engine is None:
            _cron_engine = CronSchedulerEngine(
                db_manager=db_manager,
                runtime_adapter=_claude_adapter,
                event_bus=_event_bus
            )
            _cron_engine.start()
        if _project_intelligence is None:
            _project_intelligence = ProjectIntelligence(db_manager=db_manager)
        if _team_coordinator is None:
            _team_coordinator = TeamCoordinator(
                db_manager=db_manager,
                orchestration_engine=_orchestration_engine,
                event_service=_event_service
            )

        # Initialize Message Broker and Worker Daemon
        broker = get_message_broker()
        await broker.connect()
        worker = get_queue_worker()
        worker.runtime_adapter = get_runtime_adapter()
        worker.event_bus = _event_bus
        worker.db_manager = db_manager
        worker.workflow_engine = get_workflow_engine()
        await worker.start()

        _services_initialized = True
        logger.info(
            "Backend services initialized: %d config agents, %d DB agents, %d projects, cron engine, event bus, rabbitmq/worker ready",
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

    worker = get_queue_worker()
    if worker:
        await worker.stop()

    broker = get_message_broker()
    if broker:
        await broker.disconnect()

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


def get_runtime_adapter() -> RuntimeAdapter:
    """Get the active runtime adapter instance from the RuntimeRegistry."""
    global _claude_adapter
    if _claude_adapter is None:
        _claude_adapter = ClaudeCodeAdapter(runtime_adapter)
        runtime_registry.register("claude_code", _claude_adapter, set_default=True)
    return runtime_registry.get()


def get_model_policy_resolver() -> ModelPolicyResolver:
    """Get the global ModelPolicyResolver instance."""
    return model_policy_resolver


def get_orchestration_engine() -> OrchestrationEngine:
    """Get the global OrchestrationEngine singleton instance."""
    global _orchestration_engine
    if _orchestration_engine is None:
        _orchestration_engine = OrchestrationEngine(
            db_manager=get_db_manager(),
            runtime_adapter=runtime_adapter,
            event_service=get_event_service()
        )
        runtime_adapter.on_task_completed = _orchestration_engine.handle_task_completion
    return _orchestration_engine



def get_cron_engine() -> Optional[CronSchedulerEngine]:
    """Get the global CronSchedulerEngine instance."""
    global _cron_engine
    return _cron_engine



def get_project_intelligence() -> ProjectIntelligence:
    """Get the global ProjectIntelligence instance."""
    global _project_intelligence
    if _project_intelligence is None:
        _project_intelligence = ProjectIntelligence(db_manager=get_db_manager())
    return _project_intelligence


def get_team_coordinator() -> TeamCoordinator:
    """Get the global TeamCoordinator instance."""
    global _team_coordinator
    if _team_coordinator is None:
        _team_coordinator = TeamCoordinator(
            db_manager=get_db_manager(),
            orchestration_engine=get_orchestration_engine(),
            event_service=get_event_service()
        )
    return _team_coordinator


_workflow_engine = None


def get_workflow_engine():
    """Get the global WorkflowEngine singleton instance."""
    global _workflow_engine
    if _workflow_engine is None:
        from workflows.engine import WorkflowEngine
        from workflows.sandbox import SandboxManager
        _workflow_engine = WorkflowEngine(
            db_manager=get_db_manager(),
            runtime_adapter=get_runtime_adapter(),
            orchestration_engine=get_orchestration_engine(),
            sandbox_manager=SandboxManager()
        )
    return _workflow_engine


_task_queue_publisher: Optional[TaskQueuePublisher] = None


def get_task_queue_publisher() -> TaskQueuePublisher:
    """Get the global TaskQueuePublisher singleton instance."""
    global _task_queue_publisher
    if _task_queue_publisher is None:
        _task_queue_publisher = TaskQueuePublisher(get_message_broker())
    return _task_queue_publisher

