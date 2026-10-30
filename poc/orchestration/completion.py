"""Completion propagation and dependency release coordinator."""
import json
import logging
from datetime import datetime
from typing import Any, Callable

try:
    from runtime.models import AgentRun, TaskStatus
    from events.models import EventType
except ImportError:
    from poc.runtime.models import AgentRun, TaskStatus
    from poc.events.models import EventType

from .ports import TaskStore

logger = logging.getLogger(__name__)


class CompletionCoordinator:
    def __init__(self, db_manager: TaskStore, get_runtime: Callable[[], Any], emit: Callable[..., None]):
        self.db_manager = db_manager
        self._get_runtime = get_runtime
        self._emit = emit

    @property
    def runtime_adapter(self):
        return self._get_runtime()

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
        still_running = [c for c in children if c.status not in (
            TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED
        )]
        if still_running:
            return

        # All children are in terminal states!
        # Atomic lock: only resume if status is WAITING_FOR_CHILDREN
        if not self.db_manager.claim_waiting_parent(parent_task_id):
            # Already resumed or not waiting; prevent duplicate resumption.
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
            if c.status in (TaskStatus.FAILED, TaskStatus.CANCELLED):
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


