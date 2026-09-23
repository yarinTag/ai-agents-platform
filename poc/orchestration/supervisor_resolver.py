"""
Automated Supervisor Question Resolver & Escalation Engine.
Implements a multi-tier resolution hierarchy:
Tier 1: Scans Project Shared Memory / Knowledge Base (ADRs, Conventions, Lessons) for auto-resolution.
Tier 2: Routes unanswered questions to the agent's manager (parent_id) if configured.
Tier 3: Escalates to HUMAN_OPERATOR with visual and interactive notifications.
"""

import json
import logging
import re
from datetime import datetime
from typing import Dict, Any, Optional, List

from persistence import DatabaseManager
from runtime_adapter import TaskStatus

logger = logging.getLogger(__name__)


class SupervisorResolver:
    """Multi-tier clarification and question resolution coordinator."""

    def __init__(self, db_manager: DatabaseManager, event_bus: Optional[Any] = None, runtime_adapter: Optional[Any] = None):
        self.db = db_manager
        self.event_bus = event_bus
        self.runtime_adapter = runtime_adapter

    def resolve_or_escalate_question(
        self,
        task_id: str,
        requester_agent_id: str,
        question: str,
        project_id: Optional[str] = None,
        context: Optional[str] = None,
        suggested_options: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Attempt to resolve the question using Project Shared Knowledge first.
        If no confident match is found, escalate to the agent's manager or human operator.
        """
        logger.info(f"[SupervisorResolver] Evaluating question from {requester_agent_id} on task {task_id}: '{question}'")

        # ── Tier 1: Check Project Shared Memory & Conventions ────────────────────
        auto_answer = self._try_auto_resolve_from_memory(project_id, question)
        if auto_answer:
            logger.info(f"[SupervisorResolver] Question AUTO-RESOLVED from project memory for task {task_id}")
            interaction = self.db.create_interaction({
                "task_id": task_id,
                "requester_agent_id": requester_agent_id,
                "target_approver_id": "PROJECT_SHARED_MEMORY",
                "interaction_type": "QUESTION",
                "title": f"Auto-Resolved: {question[:80]}",
                "content": question,
                "context_data": json.dumps({"context": context, "suggested_options": suggested_options or []}),
                "status": "APPROVED",
                "resolution_response": auto_answer,
                "resolved_by": "SUPERVISOR_AUTO_RESOLVE"
            })

            # Broadcast auto-resolution event
            if self.event_bus:
                try:
                    from events import PlatformEvent
                    self.event_bus.publish(PlatformEvent(
                        event_id=f"evt_{datetime.now().timestamp()}",
                        event_type="approval.auto_resolved",
                        project_id=project_id,
                        agent_id=requester_agent_id,
                        task_id=task_id,
                        payload={
                            "interaction_id": interaction["id"],
                            "question": question,
                            "resolution": auto_answer,
                            "source": "PROJECT_SHARED_MEMORY"
                        },
                        source="supervisor_resolver"
                    ))
                except Exception as eb_err:
                    logger.warning(f"Failed to publish auto_resolved event: {eb_err}")

            # Automatically resume task
            if self.runtime_adapter:
                try:
                    self.runtime_adapter.resume_task(task_id, auto_answer)
                except Exception as res_err:
                    logger.warning(f"Failed to trigger automatic resume for task {task_id}: {res_err}")

            return {
                "status": "AUTO_RESOLVED",
                "interaction_id": interaction["id"],
                "answer": auto_answer,
                "target_approver": "PROJECT_SHARED_MEMORY"
            }

        # ── Tier 2 & 3: Route to Manager (parent_id) or Human Operator ──────────
        target_approver = "HUMAN_OPERATOR"
        try:
            agent = self.db.get_agent(requester_agent_id)
            if agent and agent.parent_id:
                target_approver = agent.parent_id
        except Exception as e:
            logger.warning(f"Error checking agent parent_id: {e}")

        logger.info(f"[SupervisorResolver] Escalating question to {target_approver} for task {task_id}")

        interaction = self.db.create_interaction({
            "task_id": task_id,
            "requester_agent_id": requester_agent_id,
            "target_approver_id": target_approver,
            "interaction_type": "QUESTION",
            "title": f"Question from {requester_agent_id}",
            "content": question,
            "context_data": json.dumps({"context": context, "suggested_options": suggested_options or []}),
            "status": "PENDING"
        })

        # Ensure task is marked as WAITING_INPUT
        self.db.update_task_run(
            task_id,
            status=TaskStatus.WAITING_INPUT,
            result=f"Waiting for {target_approver} response: {question}"
        )

        # Broadcast pending approval event
        if self.event_bus:
            try:
                from events import PlatformEvent
                self.event_bus.publish(PlatformEvent(
                    event_id=f"evt_{datetime.now().timestamp()}",
                    event_type="approval.required",
                    project_id=project_id,
                    agent_id=requester_agent_id,
                    task_id=task_id,
                    payload={
                        "interaction_id": interaction["id"],
                        "title": f"Question from {requester_agent_id}",
                        "content": question,
                        "interaction_type": "QUESTION",
                        "target_approver": target_approver
                    },
                    source="supervisor_resolver"
                ))
            except Exception as eb_err:
                logger.warning(f"Failed to publish approval.required event: {eb_err}")

        return {
            "status": "PENDING_INPUT",
            "interaction_id": interaction["id"],
            "target_approver": target_approver,
            "question": question
        }

    def _try_auto_resolve_from_memory(self, project_id: Optional[str], question: str) -> Optional[str]:
        """
        Inspect project memories to check if an active ADR, convention, or insight answers the question.
        Returns the resolution response text if a confident match is found, else None.
        """
        if not project_id:
            return None

        try:
            memories = self.db.list_project_memories(project_id=project_id)
        except Exception as e:
            logger.warning(f"Failed to fetch project memories: {e}")
            return None

        if not memories:
            return None

        # Extract normalized keywords from question (words with length >= 4)
        clean_q = re.sub(r'[^a-zA-Z0-9_\u0590-\u05fe\s]', ' ', question.lower())
        q_words = set(w for w in clean_q.split() if len(w) >= 4)

        if not q_words:
            return None

        best_memory = None
        highest_score = 0

        for mem in memories:
            score = 0
            mem_title_words = set(re.sub(r'[^a-zA-Z0-9_\u0590-\u05fe\s]', ' ', mem['title'].lower()).split())
            mem_content_lower = mem['content'].lower()
            tags = [t.lower() for t in mem.get('tags', [])]

            for word in q_words:
                if word in mem_title_words:
                    score += 3
                if word in tags:
                    score += 2
                if word in mem_content_lower:
                    score += 1

            if score > highest_score:
                highest_score = score
                best_memory = mem

        # Require a threshold score of >= 3 for confident auto-resolution
        if highest_score >= 3 and best_memory:
            return (
                f"Auto-resolved from Project Standard [{best_memory['category']}: {best_memory['title']}]:\n"
                f"{best_memory['content']}"
            )

        return None
