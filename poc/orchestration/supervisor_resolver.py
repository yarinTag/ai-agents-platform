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

from dataclasses import dataclass, asdict
from persistence import DatabaseManager, AgentMessage
from runtime_adapter import TaskStatus
from .project_intelligence import ProjectIntelligence

logger = logging.getLogger(__name__)


@dataclass
class DecisionQuestionEnvelope:
    """Lean, sanitized decision request envelope preventing context bloat."""
    task_id: str
    requester_agent_id: str
    target_approver_id: str
    question: str
    context_summary: Optional[str] = None
    suggested_options: Optional[List[str]] = None
    urgency: str = "normal"
    channel_key: Optional[str] = None

    @classmethod
    def create(
        cls,
        task_id: str,
        requester_agent_id: str,
        target_approver_id: str,
        question: str,
        context: Optional[str] = None,
        suggested_options: Optional[List[str]] = None,
        urgency: str = "normal"
    ) -> 'DecisionQuestionEnvelope':
        clean_context = None
        if context:
            # Strip ANSI escape sequences and terminal noise
            stripped = re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', str(context))
            stripped = ' '.join(stripped.split())
            clean_context = stripped[:500] + ("..." if len(stripped) > 500 else "")

        channel_key = f"channel:{target_approver_id}:{requester_agent_id}:{task_id}"
        return cls(
            task_id=task_id,
            requester_agent_id=requester_agent_id,
            target_approver_id=target_approver_id,
            question=question.strip() if question else "",
            context_summary=clean_context,
            suggested_options=suggested_options or [],
            urgency=urgency,
            channel_key=channel_key
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DecisionAnswerEnvelope:
    """Concise decision response envelope directly unblocking the worker."""
    task_id: str
    decision: str
    rationale: Optional[str] = None
    source: str = "FAST_PATH_MEMORY"  # FAST_PATH_MEMORY, FAST_PATH_SUPER_AGENT, SLOW_PATH_MANAGER, SLOW_PATH_HUMAN
    channel_key: Optional[str] = None
    unblock: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


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
            intel = self.project_intelligence.synthesize_answer(project_id, question, requester_agent_id, context) if project_id else None
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
        """Background worker that runs the supervisor agent to autonomously answer a subordinate question using Lean Decision Envelopes."""
        import time
        logger.info(f"[SupervisorResolver] Starting autonomous supervisor decision by {target_approver_id} on channel {channel_key} for task {task_id}")

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
            f"Isolated Channel: {channel_key or 'default'}\n"
            f"Your subordinate worker '{requester_agent_id}' is executing task '{task_id}' and is paused waiting for your decision.\n\n"
            f"[LEAN DECISION ENVELOPE]\n"
            f"Worker Question: \"{question}\"\n"
            f"Context Summary: {context or 'None provided'}\n"
            f"{opt_text}\n\n"
            f"As supervisor, reply concisely with the exact decision or instruction to unblock the worker."
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
                    logger.info(f"[SupervisorResolver] Supervisor {target_approver_id} resolved question on channel {channel_key} with: '{lead_answer}'")
                    ans_env = DecisionAnswerEnvelope(
                        task_id=task_id,
                        decision=lead_answer,
                        rationale=f"Decided autonomously by {sup_agent.name}",
                        source="SLOW_PATH_MANAGER",
                        channel_key=channel_key,
                        unblock=True
                    )

                    self.db.resolve_interaction(
                        interaction_id=interaction_id,
                        resolution_response=lead_answer,
                        resolved_by=f"AGENT:{target_approver_id}",
                        decision="RESOLVED"
                    )

                    # Save AgentMessage with channel_key
                    try:
                        self.db.save_agent_message(AgentMessage(
                            id=f"msg_sup_ans_{datetime.now().timestamp()}",
                            from_agent_id=target_approver_id,
                            to_agent_id=requester_agent_id,
                            content=lead_answer,
                            task_id=task_id,
                            channel_key=channel_key,
                            message_type="ANSWER",
                            status="SENT",
                            metadata={"interaction_id": interaction_id, "envelope": ans_env.to_dict(), "resolved_by": f"AGENT:{target_approver_id}"}
                        ))
                    except Exception as m_err:
                        logger.warning(f"Failed to save supervisor AgentMessage: {m_err}")

                    # Save chat message in worker's channel conversation
                    try:
                        chan_conv = self.db.get_or_create_channel(target_approver_id, requester_agent_id, task_id, project_id=project_id)
                        req_chat = self.db.save_chat_message({
                            "conversation_id": chan_conv["id"],
                            "agent_id": requester_agent_id,
                            "task_id": task_id,
                            "sender_type": "USER",
                            "message_type": "CHAT",
                            "content": f"💬 **Supervisor ({sup_agent.name}) Answered:**\n\n{lead_answer}",
                            "metadata": {"interaction_id": interaction_id, "task_id": task_id, "channel_key": channel_key}
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
        with self.db._get_connection() as conn:
            conn.execute(
                "UPDATE agent_interactions SET target_approver_id = ?, updated_at = ? WHERE id = ?",
                (next_approver, datetime.now().isoformat(), interaction_id)
            )
            conn.commit()

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

