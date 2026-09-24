"""
Automated Supervisor Question Resolver & Escalation Engine.
Implements a multi-tier resolution hierarchy:
Tier 1: Scans Deep Project Intelligence (ADRs, Conventions, Lessons, Docs, Active Context).
Tier 2: Super Agent / Authorized Manager Decision Authority.
Tier 3: Escalates to HUMAN_OPERATOR with visual and interactive notifications.
"""

import json
import logging
import re
from datetime import datetime
from typing import Dict, Any, Optional, List

from persistence import DatabaseManager, AgentMessage
from runtime_adapter import TaskStatus
from .project_intelligence import ProjectIntelligence

logger = logging.getLogger(__name__)


class SupervisorResolver:
    """Multi-tier clarification and question resolution coordinator."""

    def __init__(self, db_manager: DatabaseManager, event_bus: Optional[Any] = None, runtime_adapter: Optional[Any] = None):
        self.db = db_manager
        self.event_bus = event_bus
        self.runtime_adapter = runtime_adapter
        self.project_intelligence = ProjectIntelligence(db_manager)

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
        Attempt to resolve the question using Deep Project Intelligence and Super Agent authority first.
        If no confident match is found or the decision exceeds authority, escalate to manager or human.
        """
        logger.info(f"[SupervisorResolver] Evaluating question from {requester_agent_id} on task {task_id}: '{question}'")

        # ── 1. Check Super Agent Configuration for the Project ───────────────────
        super_cfg = self.db.get_super_agent_for_project(project_id) if project_id else None

        # Check if question requires human approval due to Super Agent authority limits
        requires_human_approval = False
        if super_cfg and super_cfg.require_human_approval_for:
            q_lower = question.lower()
            for restricted in super_cfg.require_human_approval_for:
                if restricted == "destructive_actions" and any(k in q_lower for k in ("delete", "drop", "truncate", "rm -rf", "wipe")):
                    requires_human_approval = True
                    break
                if restricted == "production_changes" and any(k in q_lower for k in ("prod", "production", "live cluster", "deploy")):
                    requires_human_approval = True
                    break
                if restricted == "financial_actions" and any(k in q_lower for k in ("payment", "stripe", "credit card", "billing", "invoice")):
                    requires_human_approval = True
                    break
                if restricted == "external_messages" and any(k in q_lower for k in ("email", "sms", "tweet", "post to")):
                    requires_human_approval = True
                    break

        # ── 2. Deep Project Intelligence & Super Agent Resolution ────────────────
        if not requires_human_approval:
            intel = self.project_intelligence.synthesize_answer(project_id, question, requester_agent_id, context) if project_id else None
            if intel and intel.get("requires_human_approval"):
                requires_human_approval = True

            if intel and not requires_human_approval:
                answer = intel["answer"]
                target_approver = super_cfg.agent_id if (super_cfg and super_cfg.can_answer_questions) else "PROJECT_SHARED_MEMORY"
                resolved_by = f"SUPER_AGENT:{super_cfg.agent_id}" if (super_cfg and super_cfg.can_answer_questions) else "SUPERVISOR_AUTO_RESOLVE"

                logger.info(f"[SupervisorResolver] Question AUTO-RESOLVED by {target_approver} for task {task_id}")

                interaction = self.db.create_interaction({
                    "task_id": task_id,
                    "requester_agent_id": requester_agent_id,
                    "target_approver_id": target_approver,
                    "interaction_type": "QUESTION",
                    "title": f"Resolved: {question[:80]}",
                    "content": question,
                    "context_data": json.dumps({
                        "context": context,
                        "suggested_options": suggested_options or [],
                        "source": intel.get("source"),
                        "confidence": intel.get("confidence")
                    }),
                    "status": "APPROVED",
                    "resolution_response": answer,
                    "resolved_by": resolved_by
                })

                # If resolved by Super Agent, record an AgentMessage in SQLite
                if super_cfg and super_cfg.can_answer_questions:
                    try:
                        self.db.save_agent_message(AgentMessage(
                            id=f"msg_sa_{datetime.now().timestamp()}",
                            from_agent_id=super_cfg.agent_id,
                            to_agent_id=requester_agent_id,
                            content=answer,
                            task_id=task_id,
                            message_type="ANSWER",
                            status="SENT",
                            metadata={"resolved_by": resolved_by, "confidence": intel.get("confidence")}
                        ))
                    except Exception as msg_err:
                        logger.warning(f"Failed to record Super Agent message: {msg_err}")

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
                                "resolution": answer,
                                "source": intel.get("source", "PROJECT_SHARED_MEMORY"),
                                "target_approver": target_approver
                            },
                            source="supervisor_resolver"
                        ))
                    except Exception as eb_err:
                        logger.warning(f"Failed to publish auto_resolved event: {eb_err}")

                # Automatically resume task via Claude Code runtime adapter
                if self.runtime_adapter:
                    try:
                        self.runtime_adapter.resume_task(task_id, answer)
                    except Exception as res_err:
                        logger.warning(f"Failed to trigger automatic resume for task {task_id}: {res_err}")

                return {
                    "status": "AUTO_RESOLVED",
                    "interaction_id": interaction["id"],
                    "answer": answer,
                    "target_approver": target_approver,
                    "resolved_by": resolved_by
                }

        # ── 3. Fallback Legacy Memory Keyword Match (if project intelligence missed)
        if not requires_human_approval:
            legacy_answer = self._try_auto_resolve_from_memory(project_id, question)
            if legacy_answer:
                logger.info(f"[SupervisorResolver] Question AUTO-RESOLVED from legacy memory for task {task_id}")
                interaction = self.db.create_interaction({
                    "task_id": task_id,
                    "requester_agent_id": requester_agent_id,
                    "target_approver_id": "PROJECT_SHARED_MEMORY",
                    "interaction_type": "QUESTION",
                    "title": f"Auto-Resolved: {question[:80]}",
                    "content": question,
                    "context_data": json.dumps({"context": context, "suggested_options": suggested_options or []}),
                    "status": "APPROVED",
                    "resolution_response": legacy_answer,
                    "resolved_by": "SUPERVISOR_AUTO_RESOLVE"
                })

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
                                "resolution": legacy_answer,
                                "source": "PROJECT_SHARED_MEMORY"
                            },
                            source="supervisor_resolver"
                        ))
                    except Exception as eb_err:
                        logger.warning(f"Failed to publish auto_resolved event: {eb_err}")

                if self.runtime_adapter:
                    try:
                        self.runtime_adapter.resume_task(task_id, legacy_answer)
                    except Exception as res_err:
                        logger.warning(f"Failed to trigger automatic resume for task {task_id}: {res_err}")

                return {
                    "status": "AUTO_RESOLVED",
                    "interaction_id": interaction["id"],
                    "answer": legacy_answer,
                    "target_approver": "PROJECT_SHARED_MEMORY"
                }

        # ── 4. Escalation: Route to Manager or Human Operator ───────────────────
        target_approver = "HUMAN_OPERATOR"
        try:
            agent = self.db.get_agent(requester_agent_id)
            if agent and agent.parent_id and not requires_human_approval:
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

        if highest_score >= 3 and best_memory:
            return (
                f"Auto-resolved from Project Standard [{best_memory['category']}: {best_memory['title']}]:\n"
                f"{best_memory['content']}"
            )

        return None
