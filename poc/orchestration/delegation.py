"""Hierarchical delegation use case and its explicit collaborators."""
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
try:
    from config import AgentConfig
    from runtime.models import AgentRun, TaskStatus
    from events.models import EventType
except ImportError:
    from poc.config import AgentConfig
    from poc.runtime.models import AgentRun, TaskStatus
    from poc.events.models import EventType

from .ports import TaskStore
from .errors import DelegationError, ConcurrencyLimitExceededError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DelegationContext:
    db_manager: TaskStore
    runtime_adapter: Any
    validate_delegation: Callable[[AgentConfig, AgentConfig], None]
    emit: Callable[..., None]


def delegate_task(
    context: DelegationContext,
    parent_task_id: str,
    target_agent_id: str,
    subtask_prompt: str,
    timeout_seconds: int = 300,
    project_id: Optional[str] = None,
    dependencies: Optional[List[str]] = None,
    acceptance_criteria: Optional[str] = None
) -> AgentRun:
    """
    Delegate a subtask from a parent task to a target agent with dependency tracking.
    """
    # 1. Retrieve parent task
    parent_task = context.db_manager.get_task_run(parent_task_id)
    if not parent_task:
        raise DelegationError("Parent task not found")

    # 2. Retrieve parent agent
    parent_agent = context.db_manager.get_agent(parent_task.agent_id)
    if not parent_agent:
        raise DelegationError("Parent agent not found")

    # 3. Retrieve target agent
    target_agent = context.db_manager.get_agent(target_agent_id)
    if not target_agent:
        raise DelegationError(f"Target agent not found: {target_agent_id}")

    # 4. Strict Hierarchy Enforcement
    context.validate_delegation(parent_agent, target_agent)

    # 5. Concurrency check
    active_count = context.db_manager.count_active_subtasks_for_parent(parent_agent.id)
    max_concurrent = getattr(parent_agent, "max_concurrent_children", 5)
    if max_concurrent is not None and active_count >= max_concurrent:
        raise ConcurrencyLimitExceededError(
            f"Agent '{parent_agent.id}' has reached maximum concurrent subtasks limit ({max_concurrent})"
        )

    # 6. Evaluate initial status based on dependencies
    deps = list(dependencies) if dependencies else []
    has_pending_deps = False
    if deps:
        for dep_id in deps:
            dep_task = context.db_manager.get_task_run(dep_id)
            if not dep_task or dep_task.status != TaskStatus.COMPLETED:
                has_pending_deps = True
                break

    initial_status = TaskStatus.QUEUED if has_pending_deps else TaskStatus.RUNNING

    # 7. Generate subtask ID and trace identifiers
    subtask_id = f"subtask-{uuid.uuid4().hex[:10]}"
    root_task_id = parent_task.root_task_id or parent_task.run_id
    effective_project_id = project_id or parent_task.project_id

    # 8. Create AgentRun record for subtask
    now = datetime.now()
    subtask_run = AgentRun(
        run_id=subtask_id,
        agent_id=target_agent_id,
        project_id=effective_project_id,
        prompt=subtask_prompt,
        status=initial_status,
        created_at=now,
        started_at=now if initial_status == TaskStatus.RUNNING else None,
        parent_task_id=parent_task.run_id,
        root_task_id=root_task_id,
        assigned_by=parent_agent.id,
        dependencies=deps,
        acceptance_criteria=acceptance_criteria,
        organization_id=getattr(parent_task, "organization_id", None)
    )
    context.db_manager.save_task_run(subtask_run)

    # 9. Update parent task to WAITING_FOR_CHILDREN
    # The parent task suspends execution and waits for required child results
    parent_task.status = TaskStatus.WAITING_FOR_CHILDREN
    parent_task.result = f"Delegated subtask {subtask_id} to {target_agent_id}; awaiting completion."
    context.db_manager.save_task_run(parent_task)

    # 10. Emit platform events
    context.emit(
        event_type=EventType.TASK_WAITING_CHILDREN if hasattr(EventType, "TASK_WAITING_CHILDREN") else "task.waiting_children",
        payload={"parent_task_id": parent_task.run_id, "child_task_id": subtask_id, "target_agent_id": target_agent_id},
        agent_id=parent_agent.id,
        task_id=parent_task.run_id,
        project_id=effective_project_id
    )
    context.emit(
        event_type=EventType.TASK_DELEGATED,
        payload={
            "parent_task_id": parent_task.run_id,
            "subtask_id": subtask_id,
            "parent_agent_id": parent_agent.id,
            "target_agent_id": target_agent.id,
            "prompt": subtask_prompt,
            "dependencies": deps,
            "acceptance_criteria": acceptance_criteria,
            "status": initial_status.value
        },
        agent_id=parent_agent.id,
        task_id=subtask_id,
        parent_task_id=parent_task.run_id,
        project_id=effective_project_id
    )
    context.emit(
        event_type=EventType.TASK_CREATED,
        payload=subtask_run.to_dict(),
        agent_id=target_agent.id,
        task_id=subtask_id,
        parent_task_id=parent_task.run_id,
        project_id=effective_project_id
    )

    # 11. Start child task execution if dependencies are satisfied
    if initial_status == TaskStatus.RUNNING and context.runtime_adapter:
        try:
            if hasattr(context.runtime_adapter, "start_task"):
                try:
                    context.runtime_adapter.start_task(subtask_id)
                except TypeError:
                    context.runtime_adapter.start_task(
                        agent_id=target_agent_id,
                        project_id=effective_project_id,
                        prompt=subtask_prompt
                    )
        except Exception as e:
            logger.warning(f"Could not start runtime execution for subtask {subtask_id}: {e}")

    return subtask_run

