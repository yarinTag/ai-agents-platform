"""Supervisor inference and subordinate continuation background use case."""
import logging
from datetime import datetime
from typing import List, Optional
from storage.records import AgentMessage
from runtime.models import TaskStatus
from .ports import SupervisorStore
from .decision_envelopes import DecisionAnswerEnvelope

logger = logging.getLogger(__name__)


def _run_supervisor_agent_decision(
    db: SupervisorStore, event_bus, runtime_adapter,
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

    if not runtime_adapter:
        logger.warning(f"[SupervisorResolver] No runtime_adapter available to execute supervisor {target_approver_id}")
        return

    sup_agent = db.get_agent(target_approver_id)
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
        sup_run_id = runtime_adapter.start_task(
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
            inter_curr = db.get_interaction(interaction_id)
            if not inter_curr or inter_curr.get("status") != "PENDING":
                logger.info(f"[SupervisorResolver] Interaction {interaction_id} already resolved, aborting supervisor wait.")
                return

            sup_run = runtime_adapter.get_run_status(sup_run_id)
            if not sup_run:
                sup_run = db.get_task_run(sup_run_id)

            if sup_run and sup_run.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
                if sup_run.status == TaskStatus.COMPLETED and sup_run.result:
                    lead_answer = sup_run.result.strip()
                elif sup_run.status == TaskStatus.FAILED:
                    logger.warning(f"[SupervisorResolver] Supervisor task failed: {sup_run.error}")
                break

        # Unavailable inference is not authority to choose a worker's first option.
        if not lead_answer:
            pending = db.get_interaction(interaction_id)
            if pending and pending.get("status") == "PENDING":
                db.retarget_interaction(interaction_id, "HUMAN_OPERATOR")
                db.update_task_run(task_id, status=TaskStatus.WAITING_INPUT,
                                   result="Supervisor unavailable; awaiting human response: " + question)
            return

        if lead_answer:
            # Check again if still pending
            inter_curr = db.get_interaction(interaction_id)
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

                db.resolve_interaction(
                    interaction_id=interaction_id,
                    resolution_response=lead_answer,
                    resolved_by=f"AGENT:{target_approver_id}",
                    decision="RESOLVED"
                )

                # Save AgentMessage with channel_key
                try:
                    db.save_agent_message(AgentMessage(
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
                    chan_conv = db.get_or_create_channel(target_approver_id, requester_agent_id, task_id, project_id=project_id)
                    req_chat = db.save_chat_message({
                        "conversation_id": chan_conv["id"],
                        "agent_id": requester_agent_id,
                        "task_id": task_id,
                        "sender_type": "USER",
                        "message_type": "CHAT",
                        "content": f"💬 **Supervisor ({sup_agent.name}) Answered:**\n\n{lead_answer}",
                        "metadata": {"interaction_id": interaction_id, "task_id": task_id, "channel_key": channel_key}
                    })
                    if event_bus:
                        from events import PlatformEvent
                        event_bus.publish(PlatformEvent(
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
                if event_bus:
                    try:
                        from events import PlatformEvent
                        event_bus.publish(PlatformEvent(
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
                runtime_adapter.resume_task(task_id, lead_answer)

    except Exception as e:
        logger.error(f"[SupervisorResolver] Error during autonomous supervisor decision: {e}", exc_info=True)

