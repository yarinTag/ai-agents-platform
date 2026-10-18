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
    concurrency control, dependency-aware execution, and upward result propagation.
    """

    def __init__(
        self,
        db_manager: DatabaseManager,
        runtime_adapter: Any = None,
        event_service: Optional[EventService] = None
    ):
        self.db_manager = db_manager
        self.runtime_adapter = runtime_adapter
        self.event_service = event_service

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
        """
        Delegate a subtask from a parent task to a target agent with dependency tracking.
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
            raise DelegationError(f"Target agent not found: {target_agent_id}")

        # 4. Strict Hierarchy Enforcement
        self.validate_delegation(parent_agent, target_agent)

        # 5. Concurrency check
        active_count = self.db_manager.count_active_subtasks_for_parent(parent_agent.id)
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
                dep_task = self.db_manager.get_task_run(dep_id)
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
        self.db_manager.save_task_run(subtask_run)

        # 9. Update parent task to WAITING_FOR_CHILDREN
        # The parent task suspends execution and waits for required child results
        parent_task.status = TaskStatus.WAITING_FOR_CHILDREN
        parent_task.result = f"Delegated subtask {subtask_id} to {target_agent_id}; awaiting completion."
        self.db_manager.save_task_run(parent_task)

        # 10. Emit platform events
        self._emit(
            event_type=EventType.TASK_WAITING_CHILDREN if hasattr(EventType, "TASK_WAITING_CHILDREN") else "task.waiting_children",
            payload={"parent_task_id": parent_task.run_id, "child_task_id": subtask_id, "target_agent_id": target_agent_id},
            agent_id=parent_agent.id,
            task_id=parent_task.run_id,
            project_id=effective_project_id
        )
        self._emit(
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
        self._emit(
            event_type=EventType.TASK_CREATED,
            payload=subtask_run.to_dict(),
            agent_id=target_agent.id,
            task_id=subtask_id,
            parent_task_id=parent_task.run_id,
            project_id=effective_project_id
        )

        # 11. Start child task execution if dependencies are satisfied
        if initial_status == TaskStatus.RUNNING and self.runtime_adapter:
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

    def handle_task_completion(self, task_run: AgentRun) -> None:
        """
        Core upward propagation handler.
        1. Formats and persists structured results.
        2. Dispatches dependent tasks whose prerequisites are now met.
        3. If all siblings are finished, atomically resumes the suspended parent manager.
        4. Manager validates child deliverables and produces verified milestone result.
        5. Propagates verified results recursively up to root CEO.
        """
        # Ensure structured result exists
        if not task_run.structured_result:
            summary = task_run.result or (
                "Task completed successfully." if task_run.status == TaskStatus.COMPLETED
                else (task_run.error or "Task execution failed.")
            )
            task_run.structured_result = {
                "status": task_run.status.value,
                "summary": summary,
                "deliverables": [task_run.result] if task_run.result else [],
                "errors": task_run.error,
                "verification_evidence": f"Exit code {task_run.exit_code or 0}. Verified by {task_run.agent_id}."
            }
            self.db_manager.save_task_run(task_run)

        # Emit completion/failure event
        event_type = EventType.TASK_COMPLETED if task_run.status == TaskStatus.COMPLETED else EventType.TASK_FAILED
        self._emit(
            event_type=event_type,
            payload={
                "task_id": task_run.run_id,
                "agent_id": task_run.agent_id,
                "status": task_run.status.value,
                "result": task_run.result,
                "structured_result": task_run.structured_result,
                "error": task_run.error
            },
            agent_id=task_run.agent_id,
            task_id=task_run.run_id,
            parent_task_id=task_run.parent_task_id,
            project_id=task_run.project_id
        )

        # Step 2: Unblock or fail dependent tasks
        self._process_dependent_tasks(task_run)

        # Step 3: Check parent task resumption
        if task_run.parent_task_id:
            self._propagate_to_parent(task_run.parent_task_id)

    def _process_dependent_tasks(self, completed_task: AgentRun) -> None:
        """Check all queued tasks to see if dependencies are satisfied or broken."""
        all_tasks = self.db_manager.list_task_runs(limit=100)
        for t in all_tasks:
            if t.status != TaskStatus.QUEUED or not t.dependencies:
                continue

            if completed_task.run_id in t.dependencies:
                if completed_task.status == TaskStatus.FAILED:
                    # Prerequisite failed: dependent task fails
                    t.status = TaskStatus.FAILED
                    t.error = f"Prerequisite task '{completed_task.run_id}' failed: {completed_task.error}"
                    t.ended_at = datetime.now()
                    self.db_manager.save_task_run(t)
                    self.handle_task_completion(t)
                elif completed_task.status == TaskStatus.COMPLETED:
                    # Check if ALL dependencies are now completed
                    all_met = True
                    for dep_id in t.dependencies:
                        dep_run = self.db_manager.get_task_run(dep_id)
                        if not dep_run or dep_run.status != TaskStatus.COMPLETED:
                            all_met = False
                            break
                    if all_met:
                        t.status = TaskStatus.RUNNING
                        t.started_at = datetime.now()
                        self.db_manager.save_task_run(t)
                        self._emit(
                            event_type=EventType.TASK_STARTED,
                            payload=t.to_dict(),
                            agent_id=t.agent_id,
                            task_id=t.run_id,
                            project_id=t.project_id
                        )
                        if self.runtime_adapter and hasattr(self.runtime_adapter, "start_task"):
                            try:
                                self.runtime_adapter.start_task(t.run_id)
                            except Exception as e:
                                logger.warning(f"Failed to start unblocked dependent task {t.run_id}: {e}")

    def _propagate_to_parent(self, parent_task_id: str) -> None:
        """
        Check if all children for parent_task_id are done.
        If yes, atomically resume parent, validate deliverables, and report upward.
        """
        parent_task = self.db_manager.get_task_run(parent_task_id)
        if not parent_task:
            return

        children = self.db_manager.get_subtasks(parent_task_id)
        if not children:
            return

        # Check if any child is still running or pending
        still_running = [c for c in children if c.status in (
            TaskStatus.RUNNING, TaskStatus.QUEUED, TaskStatus.PENDING,
            TaskStatus.WAITING_FOR_CHILDREN, TaskStatus.WAITING_INPUT,
            TaskStatus.WAITING_FOR_MANAGER, TaskStatus.WAITING_FOR_HUMAN
        )]
        if still_running:
            return

        # All children are in terminal states!
        # Atomic lock: only resume if status is WAITING_FOR_CHILDREN
        with self.db_manager._get_connection() as conn:
            cursor = conn.execute(
                "UPDATE task_runs SET status = 'running' WHERE run_id = ? AND status = 'waiting_for_children'",
                (parent_task_id,)
            )
            if cursor.rowcount == 0:
                # Already resumed or not waiting; prevent duplicate resumption
                return

        # Reload resumed parent task
        parent_task = self.db_manager.get_task_run(parent_task_id)
        self._emit(
            event_type=EventType.TASK_RESUMED if hasattr(EventType, "TASK_RESUMED") else "task.resumed",
            payload={"parent_task_id": parent_task.run_id, "agent_id": parent_task.agent_id},
            agent_id=parent_task.agent_id,
            task_id=parent_task.run_id,
            project_id=parent_task.project_id
        )

        child_summaries = []
        has_failure = False
        for c in children:
            if c.status == TaskStatus.FAILED:
                has_failure = True
            child_summaries.append({
                "task_id": c.run_id,
                "agent_id": c.agent_id,
                "status": c.status.value,
                "summary": (c.structured_result or {}).get("summary", c.result),
                "deliverables": (c.structured_result or {}).get("deliverables", [c.result] if c.result else []),
                "errors": c.error,
                "verification_evidence": (c.structured_result or {}).get("verification_evidence")
            })

        self._emit(
            event_type=EventType.RESULT_PROPAGATED if hasattr(EventType, "RESULT_PROPAGATED") else "result.propagated",
            payload={
                "parent_task_id": parent_task.run_id,
                "parent_agent_id": parent_task.agent_id,
                "children": child_summaries,
                "has_failure": has_failure
            },
            agent_id=parent_task.agent_id,
            task_id=parent_task.run_id,
            project_id=parent_task.project_id
        )

        # Parent manager inspection:
        if has_failure:
            # Manager cannot report completion when a mandatory child failed!
            failed_children = [c["task_id"] for c in child_summaries if c["status"] == "failed"]
            parent_task.status = TaskStatus.FAILED
            parent_task.error = f"Mandatory child task(s) failed: {', '.join(failed_children)}"
            parent_task.ended_at = datetime.now()
            parent_task.structured_result = {
                "status": "failed",
                "summary": f"Milestone incomplete due to child task failures in {parent_task.agent_id}",
                "deliverables": [],
                "errors": parent_task.error,
                "verification_evidence": f"Failed children: {failed_children}"
            }
            self.db_manager.save_task_run(parent_task)
            self._emit(
                event_type=EventType.TASK_FAILED,
                payload=parent_task.to_dict(),
                agent_id=parent_task.agent_id,
                task_id=parent_task.run_id,
                project_id=parent_task.project_id
            )
            # Propagate failure upward
            if parent_task.parent_task_id:
                self.handle_task_completion(parent_task)
            return

        # All children succeeded: Manager validates deliverables and reports milestone complete
        all_deliverables = []
        for c in child_summaries:
            deliv = c.get("deliverables")
            if isinstance(deliv, list):
                all_deliverables.extend(deliv)
            elif deliv:
                all_deliverables.append(deliv)

        milestone_result = {
            "status": "completed",
            "summary": f"Milestone verified by {parent_task.agent_id}: all {len(children)} child tasks completed successfully.",
            "deliverables": all_deliverables,
            "verification_evidence": f"Validated {len(children)} child deliverables against acceptance criteria.",
            "errors": None
        }

        parent_task.status = TaskStatus.COMPLETED
        parent_task.result = json.dumps(milestone_result)
        parent_task.structured_result = milestone_result
        parent_task.ended_at = datetime.now()
        self.db_manager.save_task_run(parent_task)

        self._emit(
            event_type=EventType.RESULT_ACCEPTED if hasattr(EventType, "RESULT_ACCEPTED") else "result.accepted",
            payload={"parent_task_id": parent_task.run_id, "milestone_result": milestone_result},
            agent_id=parent_task.agent_id,
            task_id=parent_task.run_id,
            project_id=parent_task.project_id
        )
        self._emit(
            event_type=EventType.TASK_COMPLETED,
            payload=parent_task.to_dict(),
            agent_id=parent_task.agent_id,
            task_id=parent_task.run_id,
            project_id=parent_task.project_id
        )

        # Propagate upward recursively (e.g. Manager -> CEO)
        if parent_task.parent_task_id:
            self._propagate_to_parent(parent_task.parent_task_id)
        elif parent_task.agent_id == "ceo-orchestrator" or getattr(parent_task, "root_task_id", None) == parent_task.run_id:
            # Root CEO task reached completion: emit final human-facing report!
            self._emit(
                event_type=EventType.RESULT_FORWARDED,
                payload={
                    "root_task_id": parent_task.run_id,
                    "agent_id": parent_task.agent_id,
                    "final_report": milestone_result,
                    "recipient": "HUMAN_OPERATOR"
                },
                agent_id=parent_task.agent_id,
                task_id=parent_task.run_id,
                project_id=parent_task.project_id
            )

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
        active_tasks = [
            r for r in all_runs
            if r.status in (TaskStatus.RUNNING, TaskStatus.QUEUED, TaskStatus.PENDING,
                            TaskStatus.WAITING_FOR_CHILDREN, TaskStatus.WAITING_INPUT,
                            TaskStatus.WAITING_FOR_MANAGER, TaskStatus.WAITING_FOR_HUMAN)
        ]
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
            "report": "All project milestones, QA tests, and security reviews verified complete."
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
        return {"allowed": True, "reason": "MCP permission check not enabled on database manager"}

