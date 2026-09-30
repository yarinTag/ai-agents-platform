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

        # Record AgentMessage in SQLite for traceable A2A communication
        if target_approver and target_approver != "HUMAN_OPERATOR":
            try:
                self.db.save_agent_message(AgentMessage(
                    id=f"msg_q_{datetime.now().timestamp()}",
                    from_agent_id=requester_agent_id,
                    to_agent_id=target_approver,
                    content=question,
                    task_id=task_id,
                    message_type="QUESTION",
                    status="SENT",
                    metadata={"interaction_id": interaction["id"], "context": context}
                ))
            except Exception as msg_err:
                logger.warning(f"Failed to record A2A Question message: {msg_err}")

        # Ensure task is marked as WAITING_INPUT
        self.db.update_task_run(
            task_id,
            status=TaskStatus.WAITING_INPUT,
            result=f"Waiting for {target_approver} response: {question}"
        )

        # Post incoming subordinate question into the supervisor's active conversation
        try:
            if target_approver and target_approver != "HUMAN_OPERATOR":
                sup_conv = self.db.get_or_create_conversation(target_approver, project_id=project_id)
                options_str = ""
                if suggested_options:
                    options_str = "\n\n**Suggested Options:**\n" + "\n".join(f"- {opt}" for opt in suggested_options)
                q_text = f"❓ **Question from {requester_agent_id}:**\n\n{question}{options_str}"
                sup_chat_msg = self.db.save_chat_message({
                    "conversation_id": sup_conv["id"],
                    "agent_id": target_approver,
                    "task_id": task_id,
                    "sender_type": "ASSISTANT",
                    "message_type": "CHAT",
                    "content": q_text,
                    "metadata": {
                        "interaction_id": interaction["id"],
                        "task_id": task_id,
                        "requester_agent_id": requester_agent_id,
                        "is_subordinate_question": True
                    }
                })
                if self.event_bus:
                    try:
                        from events import PlatformEvent
                        self.event_bus.publish(PlatformEvent(
                            event_id=f"evt_{datetime.now().timestamp()}",
                            event_type="chat.message",
                            agent_id=target_approver,
                            task_id=task_id,
                            payload={
                                "id": sup_chat_msg["id"],
                                "sender_type": "ASSISTANT",
                                "content": q_text,
                                "task_id": task_id,
                                "created_at": datetime.now().isoformat()
                            },
                            source="supervisor_resolver"
                        ))
                    except Exception:
                        pass
        except Exception as sup_chat_err:
            logger.warning(f"Failed to post question to supervisor chat: {sup_chat_err}")

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

        # Trigger autonomous supervisor decision if target_approver is an active agent
        if target_approver and target_approver != "HUMAN_OPERATOR" and self.runtime_adapter:
            try:
                import threading
                t = threading.Thread(
                    target=self._run_supervisor_agent_decision,
                    args=(task_id, interaction["id"], requester_agent_id, target_approver, question, suggested_options, project_id)
                )
                t.daemon = True
                t.start()
            except Exception as spawn_err:
                logger.warning(f"Failed to spawn autonomous supervisor decision: {spawn_err}")

        return {
            "status": "PENDING_INPUT",
            "interaction_id": interaction["id"],
            "target_approver": target_approver,
            "question": question
        }

    def _run_supervisor_agent_decision(
        self,
        task_id: str,
        interaction_id: str,
        requester_agent_id: str,
        target_approver_id: str,
        question: str,
        suggested_options: Optional[List[str]],
        project_id: Optional[str]
    ):
        """Background worker that runs the supervisor agent to autonomously answer a subordinate question."""
        import time
        logger.info(f"[SupervisorResolver] Starting autonomous supervisor decision by {target_approver_id} for task {task_id}")

        if not self.runtime_adapter:
            logger.warning(f"[SupervisorResolver] No runtime_adapter available to execute supervisor {target_approver_id}")
            return

        sup_agent = self.db.get_agent(target_approver_id)
        if not sup_agent:
            logger.warning(f"[SupervisorResolver] Supervisor agent {target_approver_id} not found in DB")
            return

        opt_text = ""
        if suggested_options:
            opt_text = "\nSuggested options from worker:\n" + "\n".join(f"- {o}" for o in suggested_options)

        sup_prompt = (
            f"You are {sup_agent.name} (ID: {target_approver_id}), the Engineering Manager and supervisor in charge.\n"
            f"Your subordinate worker '{requester_agent_id}' is executing task '{task_id}' and is paused waiting for your decision.\n\n"
            f"Worker Question:\n\"{question}\"\n{opt_text}\n\n"
            f"As the supervisor, make a definitive decision and reply directly with the exact string or instruction the worker must use. "
            f"Keep your response concise, direct, and authoritative so the worker can immediately resume and complete the task."
        )

        try:
            sup_run_id = self.runtime_adapter.start_task(
                agent_id=target_approver_id,
                project_id=project_id,
                prompt=sup_prompt
            )
            logger.info(f"[SupervisorResolver] Dispatched supervisor task {sup_run_id} to {target_approver_id}")

            # Wait for supervisor task to complete
            lead_answer = None
            for _ in range(60):  # Wait up to 60 seconds
                time.sleep(1.5)
                # Check if interaction was already resolved manually by human operator
                inter_curr = self.db.get_interaction(interaction_id)
                if not inter_curr or inter_curr.get("status") != "PENDING":
                    logger.info(f"[SupervisorResolver] Interaction {interaction_id} already resolved, aborting supervisor wait.")
                    return

                sup_run = self.runtime_adapter.get_run_status(sup_run_id)
                if not sup_run:
                    sup_run = self.db.get_task_run(sup_run_id)

                if sup_run and sup_run.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
                    if sup_run.status == TaskStatus.COMPLETED and sup_run.result:
                        lead_answer = sup_run.result.strip()
                    elif sup_run.status == TaskStatus.FAILED:
                        logger.warning(f"[SupervisorResolver] Supervisor task failed: {sup_run.error}")
                    break

            # Fallback if supervisor timed out or failed but suggested options are available
            if not lead_answer and suggested_options and len(suggested_options) > 0:
                lead_answer = f"Use '{suggested_options[0]}'"

            if lead_answer:
                # Check again if still pending
                inter_curr = self.db.get_interaction(interaction_id)
                if inter_curr and inter_curr.get("status") == "PENDING":
                    logger.info(f"[SupervisorResolver] Supervisor {target_approver_id} resolved question with: '{lead_answer}'")
                    self.db.resolve_interaction(
                        interaction_id=interaction_id,
                        resolution_response=lead_answer,
                        resolved_by=f"AGENT:{target_approver_id}",
                        decision="RESOLVED"
                    )

                    # Save AgentMessage
                    try:
                        self.db.save_agent_message(AgentMessage(
                            id=f"msg_sup_ans_{datetime.now().timestamp()}",
                            from_agent_id=target_approver_id,
                            to_agent_id=requester_agent_id,
                            content=lead_answer,
                            task_id=task_id,
                            message_type="ANSWER",
                            status="SENT",
                            metadata={"interaction_id": interaction_id, "resolved_by": f"AGENT:{target_approver_id}"}
                        ))
                    except Exception as m_err:
                        logger.warning(f"Failed to save supervisor AgentMessage: {m_err}")

                    # Save chat message in worker's conversation
                    try:
                        req_conv = self.db.get_or_create_conversation(requester_agent_id, project_id=project_id)
                        req_chat = self.db.save_chat_message({
                            "conversation_id": req_conv["id"],
                            "agent_id": requester_agent_id,
                            "task_id": task_id,
                            "sender_type": "USER",
                            "message_type": "CHAT",
                            "content": f"💬 **Supervisor ({sup_agent.name}) Answered:**\n\n{lead_answer}",
                            "metadata": {"interaction_id": interaction_id, "task_id": task_id}
                        })
                        if self.event_bus:
                            from events import PlatformEvent
                            self.event_bus.publish(PlatformEvent(
                                event_id=f"evt_{datetime.now().timestamp()}",
                                event_type="chat.message",
                                agent_id=requester_agent_id,
                                task_id=task_id,
                                payload={
                                    "id": req_chat["id"],
                                    "sender_type": "USER",
                                    "content": req_chat["content"],
                                    "task_id": task_id,
                                    "created_at": datetime.now().isoformat()
                                },
                                source="supervisor_resolver"
                            ))
                    except Exception as c_err:
                        logger.warning(f"Failed to save worker chat message: {c_err}")

                    # Publish approval granted event
                    if self.event_bus:
                        try:
                            from events import PlatformEvent
                            self.event_bus.publish(PlatformEvent(
                                event_id=f"evt_{datetime.now().timestamp()}",
                                event_type="approval.granted",
                                agent_id=requester_agent_id,
                                task_id=task_id,
                                payload={
                                    "interaction_id": interaction_id,
                                    "response": lead_answer,
                                    "responder": f"AGENT:{target_approver_id}"
                                },
                                source="supervisor_resolver"
                            ))
                        except Exception:
                            pass

                    # Automatically resume the subordinate task!
                    logger.info(f"[SupervisorResolver] Resuming subordinate task {task_id} with supervisor answer...")
                    self.runtime_adapter.resume_task(task_id, lead_answer)

        except Exception as e:
            logger.error(f"[SupervisorResolver] Error during autonomous supervisor decision: {e}", exc_info=True)

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
