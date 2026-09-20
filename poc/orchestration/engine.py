"""
Orchestration Engine for AI Agents Platform.

Coordinates task delegation, multi-agent hierarchy enforcement,
concurrency limits, and lifecycle events across the platform.
"""

import uuid
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List

try:
    from config import AgentRole, AgentConfig
    from runtime_adapter import AgentRun, TaskStatus
    from persistence import DatabaseManager
    from events.models import EventType
    from events.service import EventService
except ImportError:
    from poc.config import AgentRole, AgentConfig
    from poc.runtime_adapter import AgentRun, TaskStatus
    from poc.persistence import DatabaseManager
    from poc.events.models import EventType
    from poc.events.service import EventService

logger = logging.getLogger(__name__)


class DelegationError(ValueError):
    """Raised when task delegation violates hierarchy, permissions, or rules."""
    pass


class ConcurrencyLimitExceededError(DelegationError):
    """Raised when an agent reaches or exceeds maximum allowed concurrent subtasks."""
    pass


class OrchestrationEngine:
    """
    Core engine managing multi-agent task orchestration, delegation,
    concurrency control, and task tree execution.
    """

    def __init__(
        self,
        db_manager: DatabaseManager,
        runtime_adapter: Any,
        event_service: EventService
    ):
        self.db_manager = db_manager
        self.runtime_adapter = runtime_adapter
        self.event_service = event_service

    def delegate_task(
        self,
        parent_task_id: str,
        target_agent_id: str,
        subtask_prompt: str,
        timeout_seconds: int = 300,
        project_id: Optional[str] = None
    ) -> AgentRun:
        """
        Delegate a subtask from a parent task to a target agent.

        Args:
            parent_task_id: ID of the parent task delegating work
            target_agent_id: ID of the agent receiving the delegated task
            subtask_prompt: Prompt/instruction for the subtask
            timeout_seconds: Timeout for the subtask in seconds
            project_id: Optional project context ID override

        Returns:
            The newly created and persisted AgentRun for the subtask
        """
        # 1. Retrieve parent task
        parent_task = self.db_manager.get_task_run(parent_task_id)
        if not parent_task:
            raise DelegationError("Parent task not found")

        # 2. Retrieve parent agent
        parent_agent = self.db_manager.get_agent(parent_task.agent_id)
        if not parent_agent:
            raise DelegationError("Parent agent not found")

        # 3. Retrieve target agent
        target_agent = self.db_manager.get_agent(target_agent_id)
        if not target_agent:
            raise DelegationError("Target agent not found")

        # 4. Check delegation authority:
        # Parent agent role must be MANAGER or ROOT_ORCHESTRATOR
        # (or parent_id of target agent must match parent agent, or target_agent_id in parent agent allowed_child_ids).
        parent_role = (parent_agent.role_type or "WORKER").upper() if hasattr(parent_agent, "role_type") else "WORKER"
        is_manager_or_root = parent_role in [
            AgentRole.MANAGER.value,
            AgentRole.ROOT_ORCHESTRATOR.value,
            "MANAGER",
            "ROOT_ORCHESTRATOR"
        ]
        is_direct_parent = getattr(target_agent, "parent_id", None) == parent_agent.id
        allowed_child_ids = getattr(parent_agent, "allowed_child_ids", []) or []
        in_allowed_children = target_agent.id in allowed_child_ids

        has_authority = is_manager_or_root or is_direct_parent or in_allowed_children
        if not has_authority:
            raise DelegationError(
                f"Agent '{parent_agent.id}' is not authorized to delegate to '{target_agent.id}'"
            )

        # If target agent's parent_id is set, verify it reports to parent agent (or parent agent is ROOT_ORCHESTRATOR).
        target_parent_id = getattr(target_agent, "parent_id", None)
        if target_parent_id is not None:
            is_root = parent_role in [AgentRole.ROOT_ORCHESTRATOR.value, "ROOT_ORCHESTRATOR"]
            reports_to_parent = (target_parent_id == parent_agent.id)
            if not (reports_to_parent or is_root):
                raise DelegationError(
                    f"Agent '{parent_agent.id}' is not authorized to delegate to '{target_agent.id}'"
                )

        # 5. Concurrency check:
        # Count active subtasks for parent agent
        active_count = self.db_manager.count_active_subtasks_for_parent(parent_agent.id)
        max_concurrent = getattr(parent_agent, "max_concurrent_children", 3)
        if max_concurrent is not None and active_count >= max_concurrent:
            raise ConcurrencyLimitExceededError(
                f"Agent '{parent_agent.id}' has reached maximum concurrent subtasks limit ({max_concurrent})"
            )

        # 6. Generate subtask ID and trace identifiers
        subtask_id = f"subtask-{uuid.uuid4().hex[:10]}"
        root_task_id = parent_task.root_task_id or parent_task.run_id
        effective_project_id = project_id or parent_task.project_id

        # 7. Create AgentRun record
        subtask_run = AgentRun(
            run_id=subtask_id,
            agent_id=target_agent_id,
            project_id=effective_project_id,
            prompt=subtask_prompt,
            status=TaskStatus.PENDING,
            created_at=datetime.now(),
            parent_task_id=parent_task.run_id,
            root_task_id=root_task_id,
            assigned_by=parent_agent.id
        )

        # 8. Persist subtask run
        self.db_manager.save_task_run(subtask_run)

        # 9. Emit platform events
        if self.event_service:
            try:
                self.event_service.emit(
                    event_type=EventType.TASK_DELEGATED,
                    payload={
                        "parent_task_id": parent_task.run_id,
                        "subtask_id": subtask_id,
                        "parent_agent_id": parent_agent.id,
                        "target_agent_id": target_agent.id,
                        "prompt": subtask_prompt
                    },
                    agent_id=parent_agent.id,
                    task_id=subtask_id,
                    parent_task_id=parent_task.run_id,
                    project_id=effective_project_id,
                    source="orchestration_engine"
                )
                self.event_service.emit(
                    event_type=EventType.TASK_CREATED,
                    payload=subtask_run.to_dict(),
                    agent_id=target_agent.id,
                    task_id=subtask_id,
                    parent_task_id=parent_task.run_id,
                    project_id=effective_project_id,
                    source="orchestration_engine"
                )
            except Exception as e:
                logger.warning(f"Error emitting events for subtask {subtask_id}: {e}")

        # 10. Start task execution via runtime adapter
        if self.runtime_adapter:
            try:
                if hasattr(self.runtime_adapter, "start_task"):
                    try:
                        self.runtime_adapter.start_task(subtask_id)
                    except TypeError:
                        self.runtime_adapter.start_task(
                            agent_id=target_agent_id,
                            project_id=effective_project_id,
                            prompt=subtask_prompt
                        )
            except Exception as e:
                logger.warning(f"Could not start runtime execution for subtask {subtask_id}: {e}")

        return subtask_run

    def get_subtasks(self, parent_task_id: str) -> List[AgentRun]:
        """Retrieve subtasks for a given parent task."""
        return self.db_manager.get_subtasks(parent_task_id)

    def get_task_tree(self, root_task_id: str) -> Dict[str, Any]:
        """Retrieve recursive task tree for a root task."""
        return self.db_manager.get_task_tree(root_task_id)
