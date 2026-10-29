"""
Orchestration Engine for AI Agents Platform.

Coordinates hierarchical task delegation, dependency tracking,
asynchronous lifecycle suspension/resumption, upward result propagation,
manager-level validation, and server restart recovery.
"""

import uuid
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List

try:
    from config import AgentRole, AgentConfig
    from runtime.models import AgentRun, TaskStatus
    from events.models import EventType
except ImportError:
    from poc.config import AgentRole, AgentConfig
    from poc.runtime.models import AgentRun, TaskStatus
    from poc.events.models import EventType

from .ports import TaskStore, EventEmitter
from .errors import DelegationError, ConcurrencyLimitExceededError
from .delegation import DelegationContext, delegate_task
from .completion import CompletionCoordinator

logger = logging.getLogger(__name__)


class OrchestrationEngine:
    """
    Core engine managing multi-agent task orchestration, delegation,
    concurrency control, dependency-aware execution, and upward result propagation.
    """

    def __init__(
        self,
        db_manager: TaskStore,
        runtime_adapter: Any = None,
        event_service: Optional[EventEmitter] = None
    ):
        self.db_manager = db_manager
        self.runtime_adapter = runtime_adapter
        self.event_service = event_service
        self._completion = CompletionCoordinator(
            db_manager, lambda: self.runtime_adapter, self._emit
        )

    def _emit(self, event_type: Any, payload: Dict[str, Any], **kwargs):
        """Helper to safely emit events through event_service if available."""
        if not self.event_service:
            return
        try:
            self.event_service.emit(
                event_type=event_type,
                payload=payload,
                source="orchestration_engine",
                **kwargs
            )
        except Exception as e:
            logger.warning(f"Error emitting event {event_type}: {e}")

    def validate_delegation(self, parent_agent: AgentConfig, target_agent: AgentConfig) -> None:
        """
        Validate organizational reporting hierarchy strictly.
        Rules:
        - CEO / Root Orchestrator: can delegate to direct reports (PM Manager, Software Architect, Release Reviewer).
        - PM Manager: can delegate ONLY to UI/UX Designer.
        - Software Architect: can delegate ONLY to Backend Developer, Frontend Developer, QA Engineer.
        - Release Reviewer & Workers: cannot delegate to anyone.
        """
        if parent_agent.id == target_agent.id:
            raise DelegationError(f"Agent '{parent_agent.id}' cannot delegate to itself.")

        parent_role = (getattr(parent_agent, "role_type", "") or "WORKER").upper()
        if parent_role in ("WORKER", "SPECIALIST"):
            raise DelegationError(
                f"Agent '{parent_agent.id}' has role '{parent_role}', which cannot delegate tasks. "
                f"Only ROOT_ORCHESTRATOR or MANAGER may delegate."
            )

        # Canonical default mapping for standard agents if allowed_child_ids not populated
        canonical_hierarchy = {
            "ceo-orchestrator": ["product-manager", "software-architect", "release-security-reviewer"],
            "product-manager": ["ui-ux-designer"],
            "software-architect": ["backend-developer", "frontend-developer", "qa-test-engineer"],
        }
        canonical_allowed = canonical_hierarchy.get(parent_agent.id, [])
        allowed_children = getattr(parent_agent, "allowed_child_ids", []) or []
        effective_allowed = set(allowed_children).union(canonical_allowed)

        # Generic hierarchy verification based on direct reporting line or allowed children
        target_parent_id = getattr(target_agent, "parent_id", None)

        is_direct_parent = (target_parent_id == parent_agent.id)
        is_allowed_child = (target_agent.id in effective_allowed)
        is_root = parent_role in ("ROOT_ORCHESTRATOR", AgentRole.ROOT_ORCHESTRATOR.value)

        if not (is_direct_parent or is_allowed_child or (is_root and not target_parent_id)):
            raise DelegationError(
                f"Agent '{parent_agent.id}' is not authorized to delegate to '{target_agent.id}'. "
                f"Reporting lines require direct management."
            )

    def delegate_task(
        self,
        parent_task_id: str,
        target_agent_id: str,
        subtask_prompt: str,
        timeout_seconds: int = 300,
        project_id: Optional[str] = None,
        dependencies: Optional[List[str]] = None,
        acceptance_criteria: Optional[str] = None
    ) -> AgentRun:
        return delegate_task(
            DelegationContext(self.db_manager, self.runtime_adapter, self.validate_delegation, self._emit),
            parent_task_id, target_agent_id, subtask_prompt, timeout_seconds, project_id, dependencies, acceptance_criteria
        )

    def handle_task_completion(self, task_run: AgentRun) -> None:
        return self._completion.handle_task_completion(task_run)

    def _process_dependent_tasks(self, completed_task: AgentRun) -> None:
        return self._completion._process_dependent_tasks(completed_task)

    def _propagate_to_parent(self, parent_task_id: str) -> None:
        return self._completion._propagate_to_parent(parent_task_id)

    def complete_task(
        self,
        task_id: str,
        result: str,
        structured_result: Optional[Dict[str, Any]] = None
    ) -> AgentRun:
        """Helper to mark a task as completed with results and trigger upward propagation."""
        task = self.db_manager.get_task_run(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")

        task.status = TaskStatus.COMPLETED
        task.result = result
        task.ended_at = datetime.now()
        if structured_result:
            task.structured_result = structured_result
        self.db_manager.save_task_run(task)
        self.handle_task_completion(task)
        return self.db_manager.get_task_run(task_id)

    def fail_task(self, task_id: str, error: str) -> AgentRun:
        """Helper to mark a task as failed and trigger upward propagation."""
        task = self.db_manager.get_task_run(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")

        task.status = TaskStatus.FAILED
        task.error = error
        task.ended_at = datetime.now()
        self.db_manager.save_task_run(task)
        self.handle_task_completion(task)
        return self.db_manager.get_task_run(task_id)

    def retry_task(self, task_id: str, reason: Optional[str] = None) -> AgentRun:
        """
        Retry a failed or stalled task according to manager policy.
        Resets status, increments retry_count, and relaunches execution.
        """
        task = self.db_manager.get_task_run(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")

        task.status = TaskStatus.RUNNING
        task.error = None
        task.ended_at = None
        task.retry_count = getattr(task, "retry_count", 0) + 1
        self.db_manager.save_task_run(task)

        # If parent was marked failed due to this child, reset parent to waiting_for_children
        if task.parent_task_id:
            parent = self.db_manager.get_task_run(task.parent_task_id)
            if parent and parent.status == TaskStatus.FAILED:
                parent.status = TaskStatus.WAITING_FOR_CHILDREN
                parent.error = None
                parent.ended_at = None
                self.db_manager.save_task_run(parent)

        self._emit(
            event_type=EventType.TASK_RETRIED if hasattr(EventType, "TASK_RETRIED") else "task.retried",
            payload={"task_id": task.run_id, "retry_count": task.retry_count, "reason": reason},
            agent_id=task.agent_id,
            task_id=task.run_id,
            project_id=task.project_id
        )

        if self.runtime_adapter and hasattr(self.runtime_adapter, "start_task"):
            try:
                self.runtime_adapter.start_task(task.run_id)
            except Exception as e:
                logger.warning(f"Failed to relaunch retried task {task.run_id}: {e}")

        return task

    def create_remediation_task(
        self,
        parent_task_id: str,
        target_agent_id: str,
        remediation_prompt: str,
        failed_task_id: str
    ) -> AgentRun:
        """Create a dedicated remediation task linked to a failed subtask."""
        prompt = f"[REMEDIATION for {failed_task_id}]\n{remediation_prompt}"
        return self.delegate_task(
            parent_task_id=parent_task_id,
            target_agent_id=target_agent_id,
            subtask_prompt=prompt,
            acceptance_criteria="Fix issues identified in previous failed run."
        )

    def recover_pending_tasks(self) -> int:
        """
        Server restart recovery: scans SQLite for pending/interrupted tasks and resumes them.
        Prevents losing tasks or leaving parent tasks permanently suspended.
        """
        recovered_count = 0
        all_runs = self.db_manager.list_task_runs(limit=200)

        # 1. Recover waiting_for_children parent tasks
        waiting_parents = [r for r in all_runs if r.status == TaskStatus.WAITING_FOR_CHILDREN]
        for parent in waiting_parents:
            children = self.db_manager.get_subtasks(parent.run_id)
            if not children:
                continue

            terminal_children = [c for c in children if c.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED)]
            if len(terminal_children) == len(children):
                # All children finished while server was restarting; resume parent!
                self._propagate_to_parent(parent.run_id)
                recovered_count += 1
            else:
                # Some children were interrupted; resume uncompleted children
                for child in children:
                    if child.status in (TaskStatus.RUNNING, TaskStatus.QUEUED):
                        if self.runtime_adapter and hasattr(self.runtime_adapter, "start_task"):
                            try:
                                self.runtime_adapter.start_task(child.run_id)
                                recovered_count += 1
                            except Exception:
                                pass

        return recovered_count

    def verify_project_completion(self, project_id: str, root_task_id: str) -> Dict[str, Any]:
        """
        Verify that all project milestones, dependencies, QA, and security gates
        have reached acceptable terminal states.
        """
        tree = self.db_manager.get_task_tree(root_task_id)
        if not tree:
            return {"completed": False, "verdict": "NO-GO", "reason": f"Task tree for {root_task_id} not found."}

        all_runs = self.db_manager.list_task_runs(project_id=project_id, limit=200)
        # Check for any active or blocked tasks
        active_tasks = [r for r in all_runs if r.status != TaskStatus.COMPLETED]
        if active_tasks:
            return {
                "completed": False,
                "verdict": "NO-GO",
                "reason": f"Active tasks still pending: {[t.run_id for t in active_tasks]}"
            }

        # Check for QA or Security check failures
        qa_failures = [r for r in all_runs if r.agent_id == "qa-test-engineer" and r.status == TaskStatus.FAILED]
        sec_failures = [r for r in all_runs if r.agent_id == "release-security-reviewer" and r.status == TaskStatus.FAILED]

        if qa_failures:
            return {"completed": False, "verdict": "NO-GO", "reason": "QA validation tests failed."}
        if sec_failures:
            return {"completed": False, "verdict": "NO-GO", "reason": "Security review audit failed."}

        return {
            "completed": True,
            "verdict": "GO",
            "report": "Requested task records are completed. External verification is not inferred from status alone."
        }

    def get_subtasks(self, parent_task_id: str) -> List[AgentRun]:
        """Retrieve subtasks for a given parent task."""
        return self.db_manager.get_subtasks(parent_task_id)

    def get_task_tree(self, root_task_id: str) -> Dict[str, Any]:
        """Retrieve recursive task tree for a root task."""
        return self.db_manager.get_task_tree(root_task_id)

    def check_department_mcp_access(
        self,
        department_id: Optional[str],
        connector_id: str,
        tool_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Verify that an agent's department possesses permission to execute an MCP connector or tool.
        Returns access check evaluation from DatabaseManager.
        """
        if not department_id:
            return {"allowed": True, "reason": "No department scoping restriction"}
        if hasattr(self.db_manager, "check_department_mcp_permission"):
            return self.db_manager.check_department_mcp_permission(
                department_id=department_id,
                connector_id=connector_id,
                tool_name=tool_name
            )
        return {"allowed": False, "reason": "MCP permission policy is unavailable"}

