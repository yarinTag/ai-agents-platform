"""
Automated Supervisor Question Resolver & Escalation Engine.
Implements a multi-tier resolution hierarchy:
Tier 1: Scans Deep Project Intelligence (ADRs, Conventions, Lessons, Docs, Active Context).
Tier 2: Super Agent / Authorized Manager Decision Authority.
Tier 3: Escalates to HUMAN_OPERATOR with visual and interactive notifications.
"""

import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List

from storage.records import AgentMessage
from runtime.models import TaskStatus
from .ports import SupervisorStore
from .decision_envelopes import DecisionQuestionEnvelope, DecisionAnswerEnvelope
from .supervisor_decision import _run_supervisor_agent_decision
from .memory_resolution import resolve_from_memory

logger = logging.getLogger(__name__)


class SupervisorResolver:
    """Multi-tier clarification and question resolution coordinator."""

    def __init__(self, db_manager: SupervisorStore, event_bus: Optional[Any] = None, runtime_adapter: Optional[Any] = None, project_intelligence=None, load_default_intelligence=True):
        self.db = db_manager
        self.event_bus = event_bus
        self.runtime_adapter = runtime_adapter
        if project_intelligence is None and load_default_intelligence:
            try:
                from .project_intelligence import ProjectIntelligence
                project_intelligence = ProjectIntelligence(db_manager)
            except Exception:
                logger.warning("Optional project intelligence unavailable")
        self.project_intelligence = project_intelligence

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
        Attempt to resolve the question using Dual-Track resolution:
        - Track 1 (FAST PATH): Project Intelligence, ADR memory, or Super Agent (<1s, zero process wait).
        - Track 2 (SLOW PATH): Manager autonomous decision or Human Operator (suspends to WAITING_INPUT).
        Uses scoped pairwise channels (manager:worker:task_id) and lean decision envelopes.
        """
        logger.info(f"[SupervisorResolver] Evaluating question from {requester_agent_id} on task {task_id}: '{question}'")

        # ── Determine Target Approver ───────────────────────────────────────────
        target_approver = "HUMAN_OPERATOR"
        try:
            agent = self.db.get_agent(requester_agent_id)
            if agent and agent.parent_id:
                target_approver = agent.parent_id
        except Exception as e:
            logger.warning(f"Error checking agent parent_id: {e}")

        # Build lean decision envelope
        q_env = DecisionQuestionEnvelope.create(
            task_id=task_id,
            requester_agent_id=requester_agent_id,
            target_approver_id=target_approver,
            question=question,
            context=context,
            suggested_options=suggested_options
        )
        channel_key = q_env.channel_key

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

        # ── 2. TRACK 1: FAST PATH (Deep Project Intelligence & Memory) ───────────
        if not requires_human_approval:
            intel = None
            if project_id and self.project_intelligence:
                try:
                    intel = self.project_intelligence.synthesize_answer(project_id, question, requester_agent_id, context)
                except Exception:
                    logger.warning("Project intelligence lookup unavailable; using remaining clarification tiers")
            if intel and intel.get("requires_human_approval"):
                requires_human_approval = True

            if intel and not requires_human_approval:
                answer = intel["answer"]
                source_desc = super_cfg.agent_id if (super_cfg and super_cfg.can_answer_questions) else "PROJECT_SHARED_MEMORY"
                resolved_by = f"SUPER_AGENT:{super_cfg.agent_id}" if (super_cfg and super_cfg.can_answer_questions) else "SUPERVISOR_AUTO_RESOLVE"

                logger.info(f"[SupervisorResolver][FAST_PATH] Question AUTO-RESOLVED by {source_desc} for task {task_id}")

                ans_env = DecisionAnswerEnvelope(
                    task_id=task_id,
                    decision=answer,
                    rationale=f"Auto-resolved from Project Intelligence ({intel.get('source', 'Memory')})",
                    source="FAST_PATH_SUPER_AGENT" if "SUPER_AGENT" in resolved_by else "FAST_PATH_MEMORY",
                    channel_key=channel_key,
                    unblock=True
                )

                interaction = self.db.create_interaction({
                    "task_id": task_id,
                    "requester_agent_id": requester_agent_id,
                    "target_approver_id": source_desc,
                    "interaction_type": "QUESTION",
                    "title": f"Resolved: {question[:80]}",
                    "content": question,
                    "context_data": json.dumps({
                        "envelope": q_env.to_dict(),
                        "answer_envelope": ans_env.to_dict(),
                        "confidence": intel.get("confidence")
                    }),
                    "status": "APPROVED",
                    "resolution_response": answer,
                    "resolved_by": resolved_by
                })

                # Record scoped AgentMessage
                try:
                    self.db.save_agent_message(AgentMessage(
                        id=f"msg_fp_{datetime.now().timestamp()}",
                        from_agent_id=source_desc,
                        to_agent_id=requester_agent_id,
                        content=answer,
                        task_id=task_id,
                        channel_key=channel_key,
                        message_type="ANSWER",
                        status="SENT",
                        metadata={"envelope": ans_env.to_dict(), "resolved_by": resolved_by}
                    ))
                except Exception as msg_err:
                    logger.warning(f"Failed to record Fast Path message: {msg_err}")

                # Save into isolated channel conversation
                try:
                    chan = self.db.get_or_create_channel(target_approver, requester_agent_id, task_id, project_id=project_id)
                    self.db.save_chat_message({
                        "conversation_id": chan["id"],
                        "agent_id": requester_agent_id,
                        "task_id": task_id,
                        "sender_type": "ASSISTANT",
                        "message_type": "CHAT",
                        "content": f"⚡ **Fast-Path Decision ({ans_env.source}):**\n\n{answer}",
                        "metadata": {"interaction_id": interaction["id"], "channel_key": channel_key}
                    })
                except Exception as chan_err:
                    logger.warning(f"Failed to post to channel conversation: {chan_err}")

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
                                "path": "FAST_PATH",
                                "channel_key": channel_key,
                                "source": intel.get("source", "PROJECT_SHARED_MEMORY"),
                                "target_approver": source_desc
                            },
                            source="supervisor_resolver"
                        ))
                    except Exception as eb_err:
                        logger.warning(f"Failed to publish auto_resolved event: {eb_err}")

                # Automatically resume task if runtime adapter available
                if self.runtime_adapter:
                    try:
                        self.runtime_adapter.resume_task(task_id, answer)
                    except Exception as res_err:
                        logger.warning(f"Failed to trigger automatic resume for task {task_id}: {res_err}")

                return {
                    "status": "AUTO_RESOLVED",
                    "path": "FAST_PATH",
                    "interaction_id": interaction["id"],
                    "answer": answer,
                    "channel_key": channel_key,
                    "envelope": ans_env.to_dict(),
                    "target_approver": source_desc,
                    "resolved_by": resolved_by
                }

            # ── 3. Fallback Legacy Memory Keyword Match (Fast Path) ──────────────
            legacy_answer = self._try_auto_resolve_from_memory(project_id, question)
            if legacy_answer:
                logger.info(f"[SupervisorResolver][FAST_PATH] Question AUTO-RESOLVED from legacy memory for task {task_id}")
                ans_env = DecisionAnswerEnvelope(
                    task_id=task_id,
                    decision=legacy_answer,
                    rationale="Auto-resolved from Project Shared Memory",
                    source="FAST_PATH_MEMORY",
                    channel_key=channel_key,
                    unblock=True
                )

                interaction = self.db.create_interaction({
                    "task_id": task_id,
                    "requester_agent_id": requester_agent_id,
                    "target_approver_id": "PROJECT_SHARED_MEMORY",
                    "interaction_type": "QUESTION",
                    "title": f"Auto-Resolved: {question[:80]}",
                    "content": question,
                    "context_data": json.dumps({"envelope": q_env.to_dict(), "answer_envelope": ans_env.to_dict()}),
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
                                "path": "FAST_PATH",
                                "channel_key": channel_key,
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
                    "path": "FAST_PATH",
                    "interaction_id": interaction["id"],
                    "answer": legacy_answer,
                    "channel_key": channel_key,
                    "envelope": ans_env.to_dict(),
                    "target_approver": "PROJECT_SHARED_MEMORY"
                }

        # ── 4. TRACK 2: SLOW PATH (Escalation to Manager or Human Operator) ───────
        if requires_human_approval:
            target_approver = "HUMAN_OPERATOR"

        logger.info(f"[SupervisorResolver][SLOW_PATH] Escalating question to {target_approver} on channel {channel_key} for task {task_id}")

        interaction = self.db.create_interaction({
            "task_id": task_id,
            "requester_agent_id": requester_agent_id,
            "target_approver_id": target_approver,
            "interaction_type": "QUESTION",
            "title": f"Question from {requester_agent_id}",
            "content": question,
            "context_data": json.dumps({"envelope": q_env.to_dict()}),
            "status": "PENDING"
        })

        # Record AgentMessage in SQLite with channel_key
        if target_approver and target_approver != "HUMAN_OPERATOR":
            try:
                self.db.save_agent_message(AgentMessage(
                    id=f"msg_q_{datetime.now().timestamp()}",
                    from_agent_id=requester_agent_id,
                    to_agent_id=target_approver,
                    content=question,
                    task_id=task_id,
                    channel_key=channel_key,
                    message_type="QUESTION",
                    status="SENT",
                    metadata={"interaction_id": interaction["id"], "envelope": q_env.to_dict()}
                ))
            except Exception as msg_err:
                logger.warning(f"Failed to record A2A Question message: {msg_err}")

        # Ensure task is marked as WAITING_INPUT
        self.db.update_task_run(
            task_id,
            status=TaskStatus.WAITING_INPUT,
            result=f"Waiting for {target_approver} response on channel {channel_key}: {question}"
        )

        # Post incoming subordinate question into the isolated pairwise channel
        try:
            if target_approver and target_approver != "HUMAN_OPERATOR":
                chan_conv = self.db.get_or_create_channel(target_approver, requester_agent_id, task_id, project_id=project_id)
                options_str = ""
                if suggested_options:
                    options_str = "\n\n**Suggested Options:**\n" + "\n".join(f"- {opt}" for opt in suggested_options)
                q_text = f"❓ **Question from {requester_agent_id}:**\n\n{question}{options_str}"
                sup_chat_msg = self.db.save_chat_message({
                    "conversation_id": chan_conv["id"],
                    "agent_id": target_approver,
                    "task_id": task_id,
                    "sender_type": "ASSISTANT",
                    "message_type": "CHAT",
                    "content": q_text,
                    "metadata": {
                        "interaction_id": interaction["id"],
                        "task_id": task_id,
                        "requester_agent_id": requester_agent_id,
                        "channel_key": channel_key,
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
                                "channel_key": channel_key,
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
                        "target_approver": target_approver,
                        "path": "SLOW_PATH",
                        "channel_key": channel_key
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
                    args=(task_id, interaction["id"], requester_agent_id, target_approver, question, suggested_options, project_id, channel_key, q_env.context_summary)
                )
                t.daemon = True
                t.start()
            except Exception as spawn_err:
                logger.warning(f"Failed to spawn autonomous supervisor decision: {spawn_err}")

        return {
            "status": "PENDING_INPUT",
            "path": "SLOW_PATH",
            "interaction_id": interaction["id"],
            "target_approver": target_approver,
            "channel_key": channel_key,
            "envelope": q_env.to_dict(),
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
        project_id: Optional[str],
        channel_key: Optional[str] = None,
        context: Optional[str] = None
    ):
        return _run_supervisor_agent_decision(self.db, self.event_bus, self.runtime_adapter,
            task_id, interaction_id, requester_agent_id, target_approver_id, question, suggested_options, project_id, channel_key, context
        )

    def _try_auto_resolve_from_memory(self, project_id: Optional[str], question: str) -> Optional[str]:
        return resolve_from_memory(self.db,
            project_id, question
        )

    def escalate_question(
        self,
        interaction_id: str,
        escalating_agent_id: str,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Escalate an interaction from the current approver up to the next tier in hierarchy.
        Worker -> Direct Manager -> CEO -> Human Operator.
        """
        interaction = self.db.get_interaction(interaction_id)
        if not interaction:
            raise ValueError(f"Interaction {interaction_id} not found")

        agent = self.db.get_agent(escalating_agent_id)
        next_approver = "HUMAN_OPERATOR"
        if agent and agent.parent_id:
            next_approver = agent.parent_id

        # Update interaction approver
        self.db.retarget_interaction(interaction_id, next_approver)

        # Update task status / result
        self.db.update_task_run(
            interaction["task_id"],
            status=TaskStatus.WAITING_INPUT,
            result=f"Question escalated by {escalating_agent_id} to {next_approver}: {interaction['content']}"
        )

        # Trigger decision if next approver is an active manager agent
        if next_approver and next_approver != "HUMAN_OPERATOR" and self.runtime_adapter:
            try:
                import threading
                esc_channel = f"channel:{next_approver}:{escalating_agent_id}:{interaction['task_id']}"
                t = threading.Thread(
                    target=self._run_supervisor_agent_decision,
                    args=(interaction["task_id"], interaction["id"], escalating_agent_id, next_approver, interaction["content"], None, None, esc_channel, None)
                )
                t.daemon = True
                t.start()
            except Exception as spawn_err:
                logger.warning(f"Failed to spawn supervisor decision on escalation: {spawn_err}")

        return {
            "interaction_id": interaction_id,
            "escalated_from": escalating_agent_id,
            "target_approver": next_approver,
            "status": "ESCALATED"
        }

