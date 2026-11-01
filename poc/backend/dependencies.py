"""
Dependency initialization and shared services for the AI Agents Platform API.

This module is the single import bridge between the backend API package
and the root-level PoC modules (config, persistence, runtime_adapter).
The sys.path setup happens here only — no other API file should modify sys.path.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional, Any

# Add PoC root to path ONCE here — the single place for this resolution
import sys
import os
_poc_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _poc_root not in sys.path:
    sys.path.insert(0, _poc_root)

from config import config_manager, ConfigManager, AgentConfig, AgentRole, AgentTemplate, ProjectConfig, Skill
from persistence import db_manager, DatabaseManager, WorkflowRevisionConflict
from runtime.models import AgentRun, TaskStatus
from runtime.protocol import RuntimeAdapter, RuntimeCapabilities
from runtime.registry import runtime_registry, RuntimeRegistry
from runtime.model_policy import model_policy_resolver, ModelPolicyResolver
from events import EventBus, EventService, PlatformEvent, EventType
from .capabilities import capabilities

# Compatibility type exports load only the implementation requested by a caller.
_LAZY_EXPORTS = {
    "TaskQueuePublisher": (f"{__package__}.queue.publisher", "TaskQueuePublisher"),
    "get_message_broker": (f"{__package__}.queue.broker", "get_message_broker"),
    "get_queue_worker": (f"{__package__}.queue.worker", "get_queue_worker"),
    "runtime_adapter": ("runtime_adapter", "runtime_adapter"),
    "ClaudeCodeRuntimeAdapter": ("runtime_adapter", "ClaudeCodeRuntimeAdapter"),
    "runtime_providers": ("runtime_providers", None),
    "ClaudeCodeAdapter": ("runtime.claude_adapter", "ClaudeCodeAdapter"),
    "CronSchedulerEngine": (f"{__package__}.scheduler.engine", "CronSchedulerEngine"),
    **{name: ("orchestration.hierarchy_validator", name) for name in (
        "validate_agent_hierarchy", "HierarchyValidationError",
        "validate_agent_communication", "CommunicationAuthorizationError")},
    **{name: ("orchestration.engine", name) for name in (
        "OrchestrationEngine",)},
    "DelegationError": ("orchestration.errors", "DelegationError"),
    "ConcurrencyLimitExceededError": ("orchestration.errors", "ConcurrencyLimitExceededError"),
    "ProjectIntelligence": ("orchestration.project_intelligence", "ProjectIntelligence"),
    "TeamCoordinator": ("orchestration.team_coordinator", "TeamCoordinator"),
}


def __getattr__(name):
    from importlib import import_module
    if name not in _LAZY_EXPORTS:
        raise AttributeError(name)
    module_name, attribute = _LAZY_EXPORTS[name]
    module = import_module(module_name)
    value = getattr(module, attribute) if attribute else module
    return value


def _implementation(name):
    return __getattr__(name)


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
    """Start independent optional capabilities after required persistence is ready."""
    global _services_initialized
    if _services_initialized:
        return
    # Core persistence errors intentionally prevent functional readiness.
    get_db_manager().list_agents()
    get_event_service()
    for name, start in (
        ("runtime", get_runtime_adapter),
        ("orchestration", get_orchestration_engine),
        ("scheduler-worker", _start_scheduler),
        ("intelligence", get_project_intelligence),
        ("team-coordinator", get_team_coordinator),
    ):
        if not capabilities.enabled(name):
            capabilities.mark(name, "DISABLED")
            continue
        capabilities.mark(name, "STARTING")
        try:
            start()
            capabilities.mark(name, "READY")
        except Exception:
            logger.exception("Optional capability %s failed to start", name)
            capabilities.mark(name, "UNAVAILABLE", "Initialization failed")
    from .queue_lifecycle import start_queue
    await start_queue()
    _services_initialized = True


def _start_scheduler():
    global _cron_engine
    capabilities.require("scheduler")
    scheduler_type = _implementation("CronSchedulerEngine")
    scheduler = scheduler_type(
        db_manager=get_db_manager(), runtime_adapter=get_runtime_adapter(),
        event_bus=get_event_bus(),
    )
    scheduler.start()
    _cron_engine = scheduler
    return scheduler


async def shutdown_services():
    """Close started resources independently, even after partial startup failure."""
    global _services_initialized, _cron_engine, _claude_adapter
    global _orchestration_engine, _project_intelligence, _team_coordinator, _workflow_engine
    from .queue_lifecycle import stop_queue
    await stop_queue()
    try:
        if _cron_engine:
            capabilities.mark("scheduler-worker", "STOPPING")
            try:
                await _cron_engine.stop()
            except Exception:
                logger.exception("Scheduler shutdown failed")
            finally:
                _cron_engine = None
                capabilities.mark("scheduler-worker", "UNAVAILABLE", "Stopped")
    finally:
        if _claude_adapter is not None:
            capabilities.mark("runtime", "STOPPING")
            try:
                await asyncio.to_thread(_claude_adapter.shutdown)
            except Exception:
                logger.exception("Runtime shutdown failed")
            finally:
                runtime_registry.unregister("claude_code")
                _claude_adapter = None
                capabilities.mark("runtime", "UNAVAILABLE", "Stopped")
        if _project_intelligence is not None:
            try:
                indexer = getattr(_project_intelligence, "code_indexer", None)
                if indexer:
                    await asyncio.to_thread(indexer.close)
            except Exception:
                logger.exception("Intelligence shutdown failed")
        _orchestration_engine = None
        _project_intelligence = None
        _team_coordinator = None
        _workflow_engine = None
        for name in ("orchestration", "intelligence", "team-coordinator", "notifications"):
            capabilities.mark(name, "UNAVAILABLE", "Stopped")
        for task in _background_tasks:
            if not task.done():
                task.cancel()
        if _background_tasks:
            await asyncio.gather(*_background_tasks, return_exceptions=True)
        _background_tasks.clear()
        _services_initialized = False


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
    capabilities.require("runtime")
    if _claude_adapter is None:
        from .runtime_wiring import configure_runtime
        concrete_runtime = _implementation("runtime_adapter")
        configure_runtime(concrete_runtime, get_db_manager(), get_config_manager(), get_event_service(), get_event_bus(), get_project_intelligence, get_skill_context)
        _claude_adapter = _implementation("ClaudeCodeAdapter")(concrete_runtime)
        runtime_registry.register("claude_code", _claude_adapter, set_default=True)
    return runtime_registry.get()


def get_optional_runtime_adapter():
    """Persisted reads remain available when execution is disabled or unavailable."""
    from fastapi import HTTPException
    try:
        return get_runtime_adapter()
    except HTTPException as error:
        if error.status_code != 503:
            raise
        return None


def get_model_policy_resolver() -> ModelPolicyResolver:
    """Get the global ModelPolicyResolver instance."""
    return model_policy_resolver


def get_orchestration_engine() -> Any:
    """Get the global OrchestrationEngine singleton instance."""
    global _orchestration_engine
    capabilities.require("orchestration")
    if _orchestration_engine is None:
        _orchestration_engine = _implementation("OrchestrationEngine")(
            db_manager=get_db_manager(),
            runtime_adapter=get_runtime_adapter(),
            event_service=get_event_service()
        )
        _implementation("runtime_adapter").on_task_completed = _orchestration_engine.handle_task_completion
        try:
            _orchestration_engine.recover_pending_tasks()
        except Exception:
            logger.exception("Pending task recovery failed")
    return _orchestration_engine



def get_cron_engine() -> Optional[Any]:
    """Get the global CronSchedulerEngine instance."""
    global _cron_engine
    return _cron_engine



def get_project_intelligence() -> Any:
    """Get the global ProjectIntelligence instance."""
    global _project_intelligence
    capabilities.require("intelligence")
    if _project_intelligence is None:
        _project_intelligence = _implementation("ProjectIntelligence")(db_manager=get_db_manager())
    return _project_intelligence


def get_team_coordinator() -> Any:
    """Get the global TeamCoordinator instance."""
    global _team_coordinator
    capabilities.require("teams")
    capabilities.require("team-coordinator")
    if _team_coordinator is None:
        _team_coordinator = _implementation("TeamCoordinator")(
            db_manager=get_db_manager(),
            dispatch_provider=lambda: get_runtime_adapter().start_task,
            event_service=get_event_service()
        )
    return _team_coordinator


_workflow_engine = None


def get_skill_context(skill_ids, organization_id=None):
    """Resolve optional skill context only for work that explicitly needs it."""
    capabilities.require("skills")
    if organization_id:
        from plugins.workflow_skills import skill_context
        return skill_context(get_db_manager(), organization_id, skill_ids)
    from skills_service import build_skills_system_prompt
    return build_skills_system_prompt(skill_ids)


def get_workflow_engine():
    """Get the global WorkflowEngine singleton instance."""
    global _workflow_engine
    capabilities.require("workflows")
    if _workflow_engine is None:
        from .workflow_wiring import prompt_guard, sanitize_output, approval_dispatch
        from workflows.engine import WorkflowEngine
        from workflows.sandbox import SandboxManager
        notifier = None
        if capabilities.enabled("notifications"):
            try:
                from workflows.notifications import WorkflowNotifier
                from integrations.channels import find_channel_connector, deliver_channel_message
                notifier = WorkflowNotifier(get_db_manager(), find_channel_connector, deliver_channel_message)
                capabilities.mark("notifications", "READY")
            except Exception:
                capabilities.mark("notifications", "UNAVAILABLE", "Notification adapter unavailable")
                logger.exception("Optional notification adapter unavailable")
        _workflow_engine = WorkflowEngine(
            db_manager=get_db_manager(),
            runtime_adapter=get_runtime_adapter(),
            sandbox_manager=SandboxManager(), notifier=notifier, skill_context=get_skill_context,
            prompt_guard=prompt_guard(get_db_manager()), output_sanitizer=sanitize_output,
            approval_dispatch=approval_dispatch(get_db_manager())
        )
    return _workflow_engine


_task_queue_publisher: Optional[TaskQueuePublisher] = None


def get_task_queue_publisher() -> TaskQueuePublisher:
    """Get the global TaskQueuePublisher singleton instance."""
    global _task_queue_publisher
    capabilities.require("queue")
    if _task_queue_publisher is None:
        _task_queue_publisher = _implementation("TaskQueuePublisher")(_implementation("get_message_broker")())
    return _task_queue_publisher

