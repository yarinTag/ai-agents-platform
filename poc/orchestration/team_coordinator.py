"""
Agent Teams Coordination Engine.
Supports dynamic multi-agent temporary teams for parallel reviews, audits, and collaborative task decomposition.
"""

from __future__ import annotations

import uuid
import logging
from datetime import datetime
from typing import TYPE_CHECKING, Dict, Any, Optional, List

from storage.records import AgentTeam
from runtime.models import TaskStatus, AgentRun
from events.models import EventType

if TYPE_CHECKING:
    from .ports import TeamStore, EventEmitter

logger = logging.getLogger(__name__)


class TeamCoordinator:
    """Coordinates temporary teams of specialized agents executing in parallel."""

    def __init__(
        self,
        db_manager: TeamStore,
        orchestration_engine: Optional[Any] = None,
        event_service: Optional[EventEmitter] = None,
        dispatch_provider=None,
    ):
        self.db = db_manager
        self.orchestration = orchestration_engine
        self.event_service = event_service
        self.dispatch_provider = dispatch_provider

    def create_team(
        self,
        name: str,
        manager_agent_id: str,
        member_agent_ids: List[str],
        project_id: Optional[str] = None,
        description: Optional[str] = None
    ) -> AgentTeam:
        """Create and persist a temporary agent team."""
        team_id = f"team_{uuid.uuid4().hex[:10]}"
        members = [{"agent_id": aid, "role_in_team": "REVIEWER"} for aid in member_agent_ids]

        team = self.db.create_agent_team({
            "id": team_id,
            "name": name,
            "manager_agent_id": manager_agent_id,
            "project_id": project_id,
            "description": description,
            "status": "ACTIVE",
            "members": members
        })

        if self.event_service:
            try:
                self.event_service.emit(
                    event_type="team.created",
                    payload=team.to_dict(),
                    agent_id=manager_agent_id,
                    project_id=project_id,
                    source="team_coordinator"
                )
            except Exception as e:
                logger.warning(f"Error emitting team.created event: {e}")

        return team

    def dispatch_team_task(
        self,
        team_id: str,
        shared_goal: str,
        member_prompts: Optional[Dict[str, str]] = None,
        parent_task_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Dispatch parallel subtasks to all team members under the team's manager.
        """
        team = self.db.get_agent_team(team_id)
        if not team:
            raise ValueError(f"Team '{team_id}' not found")

        if self.dispatch_provider is None:
            raise RuntimeError("Team execution dispatcher is unavailable")
        dispatch = self.dispatch_provider()
        manager = self.db.get_agent(team.manager_agent_id)
        organization_id = getattr(manager, "organization_id", None)
        member_prompts = member_prompts or {}
        dispatched_tasks = []

        now = datetime.now()
        for m in (team.members or []):
            agent_id = m["agent_id"]
            prompt = member_prompts.get(agent_id, f"[{team.name}] Contribute to team goal: {shared_goal}")
            run_id = f"task_team_{uuid.uuid4().hex[:8]}"

            task_run = AgentRun(
                run_id=run_id,
                agent_id=agent_id,
                project_id=team.project_id,
                prompt=prompt,
                status=TaskStatus.QUEUED,
                organization_id=organization_id,
                created_at=now,
                parent_task_id=parent_task_id,
                assigned_by=team.manager_agent_id
            )
            self.db.save_task_run(task_run)

            try:
                dispatch(task_id=run_id, agent_id=agent_id, project_id=team.project_id, prompt=prompt)
            except Exception:
                task_run.status = TaskStatus.FAILED
                task_run.error = "Team execution dispatch failed"
                task_run.ended_at = datetime.now()
                self.db.save_task_run(task_run)
            dispatched_tasks.append({
                "task_id": run_id,
                "agent_id": agent_id,
                "prompt": prompt,
                "status": task_run.status.value.upper()
            })

            if self.event_service:
                try:
                    self.event_service.emit(
                        event_type=EventType.TASK_CREATED,
                        payload=task_run.to_dict(),
                        agent_id=agent_id,
                        task_id=run_id,
                        parent_task_id=parent_task_id,
                        project_id=team.project_id,
                        source="team_coordinator"
                    )
                except Exception:
                    pass

        if self.event_service:
            try:
                self.event_service.emit(
                    event_type="team.dispatched",
                    payload={
                        "team_id": team_id,
                        "shared_goal": shared_goal,
                        "task_count": len(dispatched_tasks),
                        "tasks": dispatched_tasks
                    },
                    agent_id=team.manager_agent_id,
                    project_id=team.project_id,
                    source="team_coordinator"
                )
            except Exception:
                pass

        return {
            "team_id": team_id,
            "status": "DISPATCHED" if dispatched_tasks and all(t["status"] != "FAILED" for t in dispatched_tasks) else "DISPATCH_FAILED",
            "shared_goal": shared_goal,
            "tasks": dispatched_tasks
        }

    def synthesize_team_results(
        self,
        team_id: str,
        task_ids: List[str]
    ) -> Dict[str, Any]:
        """
        Collect results from completed team subtasks and synthesize final output.
        """
        team = self.db.get_agent_team(team_id)
        if not team:
            raise ValueError(f"Team '{team_id}' not found")

        results = []
        all_completed = bool(task_ids)
        for tid in task_ids:
            task = self.db.get_task_run(tid)
            if task:
                status_str = task.status.value if hasattr(task.status, "value") else str(task.status)
                if status_str != "completed":
                    all_completed = False
                results.append({
                    "task_id": tid,
                    "agent_id": task.agent_id,
                    "status": status_str,
                    "result": task.result or "In progress..."
                })

            else:
                all_completed = False
                results.append({"task_id": tid, "agent_id": "unknown", "status": "missing", "result": "Task is unavailable"})

        # Synthesize executive summary
        synthesis_lines = [
            f"# Executive Synthesis for Team: {team.name}",
            f"**Manager**: {team.manager_agent_id} | **Project**: {team.project_id or 'Global'}",
            f"**Reviewers Participated**: {len(results)}",
            "",
            "## Findings & Contributions:"
        ]
        for r in results:
            synthesis_lines.append(f"- **Agent {r['agent_id']}** ({r['status']}): {str(r['result'])[:300]}")

        synthesis_lines.append("")
        synthesis_lines.append("## Conclusion:")
        synthesis_lines.append("All requested tasks completed." if all_completed else "Results remain incomplete; waiting for task completion.")

        final_synthesis = "\n".join(synthesis_lines)

        if all_completed:
            self.db.update_agent_team(team_id, status="COMPLETED")

        if self.event_service:
            try:
                self.event_service.emit(
                    event_type="team.completed" if all_completed else "team.progress",
                    payload={
                        "team_id": team_id,
                        "all_completed": all_completed,
                        "synthesis": final_synthesis
                    },
                    agent_id=team.manager_agent_id,
                    project_id=team.project_id,
                    source="team_coordinator"
                )
            except Exception:
                pass

        return {
            "team_id": team_id,
            "status": "COMPLETED" if all_completed else "IN_PROGRESS",
            "synthesis": final_synthesis,
            "member_results": results
        }
