"""
Interactive Agent Chat API endpoints.
Provides real-time bidirectional communication between the operator and AI agents.
Supports multi-session management, supervisor session linking, and duplicate-free execution messaging.
"""

from fastapi import APIRouter, HTTPException, Depends, status
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
import inspect
import uuid
import logging

from ..dependencies import get_db_manager, get_runtime_adapter, get_event_bus
from persistence import DatabaseManager, AgentMessage
from runtime.protocol import RuntimeAdapter
from runtime_adapter import TaskStatus
from events import EventBus, PlatformEvent, EventType

logger = logging.getLogger(__name__)

router = APIRouter()


class SendMessageRequest(BaseModel):
    content: str = Field(..., min_length=1)
    project_id: Optional[str] = None
    conversation_id: Optional[str] = None


class CreateSessionRequest(BaseModel):
    title: Optional[str] = None
    project_id: Optional[str] = None
    task_id: Optional[str] = None


@router.get("/{agent_id}/sessions")
async def list_sessions(
    agent_id: str,
    db: DatabaseManager = Depends(get_db_manager)
):
    """List all sessions for an agent, ordered newest first."""
    agent = db.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Agent '{agent_id}' not found")
    sessions = db.list_agent_sessions(agent_id)
    if not sessions:
        init_sess = db.create_agent_session(agent_id, title="Session 1", close_existing=False)
        sessions = [init_sess]
    return {"sessions": sessions}


@router.post("/{agent_id}/sessions")
async def create_session(
    agent_id: str,
    payload: CreateSessionRequest = CreateSessionRequest(),
    db: DatabaseManager = Depends(get_db_manager)
):
    """
    Close the current active session for this agent and open a fresh new session.
    Links the supervisor's active session for seamless escalation and conversation context.
    """
    agent = db.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Agent '{agent_id}' not found")
    new_sess = db.create_agent_session(
        agent_id=agent_id,
        project_id=payload.project_id,
        title=payload.title,
        close_existing=True,
        task_id=payload.task_id
    )
    return {"session": new_sess}


@router.post("/{agent_id}/sessions/{conversation_id}/activate")
async def activate_session(
    agent_id: str,
    conversation_id: str,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Switch the agent's active session to an existing one."""
    sess = db.activate_agent_session(agent_id, conversation_id)
    if not sess:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Session '{conversation_id}' not found")
    return {"session": sess}


@router.get("/{agent_id}/messages")
async def get_messages(
    agent_id: str,
    conversation_id: Optional[str] = None,
    limit: int = 100,
    db: DatabaseManager = Depends(get_db_manager),
    runtime: RuntimeAdapter = Depends(get_runtime_adapter)
):
    """
    Retrieve chat history, thoughts, and task execution responses for an agent and session.
    Synchronizes runtime outputs idempotently without duplicate prompt or response messages.
    """
    agent = db.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Agent '{agent_id}' not found")

    if conversation_id:
        conv = db.get_conversation(conversation_id)
        if not conv:
            conv = db.get_or_create_conversation(agent_id)
    else:
        conv = db.get_or_create_conversation(agent_id)

    # 1. Fetch recent tasks for this agent
    recent_tasks = db.list_task_runs(agent_id=agent_id, limit=20)
    seen_run_ids = {t.run_id for t in recent_tasks}
    if hasattr(runtime, 'list_runs'):
        for r in runtime.list_runs():
            if str(r.agent_id) == str(agent_id) and r.run_id not in seen_run_ids:
                recent_tasks.append(r)
                seen_run_ids.add(r.run_id)

    # 2. Synchronize any completed, failed, or waiting tasks into chat_messages idempotently
    for task_run in recent_tasks:
        status_val = task_run.status.value if hasattr(task_run.status, "value") else str(task_run.status)
        has_result = bool(task_run.result or task_run.error or status_val in ("completed", "failed", "waiting_input"))

        db_task_id = task_run.run_id
        try:
            db.save_task_run(task_run)
        except Exception:
            pass

        # Save user task prompt ONLY if not already recorded anywhere in this agent's chat history
        if task_run.prompt and not db.has_chat_message_for_task(agent_id, task_run.run_id, "USER", content=task_run.prompt):
            try:
                db.save_chat_message({
                    "conversation_id": conv["id"],
                    "agent_id": agent_id,
                    "task_id": db_task_id,
                    "sender_type": "USER",
                    "message_type": "CHAT",
                    "content": task_run.prompt,
                    "metadata": {"task_id": task_run.run_id},
                    "created_at": task_run.created_at.isoformat() if task_run.created_at else None
                })
            except Exception as e:
                logger.warning(f"Error saving task prompt to chat: {e}")

        # Save agent's completed or waiting response ONLY ONCE
        if has_result:
            content_text = task_run.result if (status_val in ("completed", "waiting_input") and task_run.result) else (task_run.error or "Task completed.")
            if not db.has_chat_message_for_task(agent_id, task_run.run_id, "ASSISTANT", content=content_text):
                try:
                    db.save_chat_message({
                        "conversation_id": conv["id"],
                        "agent_id": agent_id,
                        "task_id": db_task_id,
                        "sender_type": "ASSISTANT",
                        "message_type": "CHAT",
                        "content": content_text,
                        "metadata": {
                            "task_id": task_run.run_id,
                            "status": status_val,
                            "exit_code": getattr(task_run, "exit_code", None),
                            "started_at": task_run.started_at.isoformat() if getattr(task_run, "started_at", None) else None,
                            "ended_at": task_run.ended_at.isoformat() if getattr(task_run, "ended_at", None) else None
                        },
                        "created_at": task_run.ended_at.isoformat() if getattr(task_run, "ended_at", None) else (datetime.now().isoformat())
                    })
                except Exception as e:
                    logger.warning(f"Error saving assistant response to chat: {e}")

    # 3. Retrieve latest chat history for this specific conversation session
    history = db.get_chat_history(agent_id, limit=limit, conversation_id=conv["id"])

    return {
        "conversation": conv,
        "messages": history,
        "tasks": [
            {
                "id": t.run_id,
                "run_id": t.run_id,
                "agent_id": t.agent_id,
                "prompt": t.prompt,
                "status": t.status.value if hasattr(t.status, "value") else str(t.status),
                "result": t.result,
                "error": t.error,
                "created_at": t.created_at.isoformat() if t.created_at else None,
                "ended_at": t.ended_at.isoformat() if getattr(t, "ended_at", None) else None
            }
            for t in recent_tasks
        ]
    }


@router.post("/{agent_id}/messages")
async def send_message(
    agent_id: str,
    payload: SendMessageRequest,
    db: DatabaseManager = Depends(get_db_manager),
    runtime: RuntimeAdapter = Depends(get_runtime_adapter),
    event_bus: EventBus = Depends(get_event_bus)
):
    """
    Send an interactive prompt or message directly to an agent.
    If the agent has a pending question/approval or waiting task, automatically resolves it and resumes execution.
    Otherwise, launches a fresh agent task linked synchronously to the user message.
    """
    agent = db.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Agent '{agent_id}' not found")

    if payload.conversation_id:
        conv = db.get_conversation(payload.conversation_id)
        if not conv:
            conv = db.get_or_create_conversation(agent_id, project_id=payload.project_id)
    else:
        conv = db.get_or_create_conversation(agent_id, project_id=payload.project_id)

    now_iso = datetime.now().isoformat()

    # Find if there is an active or waiting task for this agent
    session_task_id = conv.get("task_id") if conv else None
    pending_interactions = db.list_interactions(agent_id=agent_id, status="PENDING")
    waiting_task_id = None
    if pending_interactions:
        matched = next((pi for pi in pending_interactions if pi.get("task_id") == session_task_id), None)
        if matched:
            waiting_task_id = session_task_id
            pending_interactions = [matched]
        else:
            waiting_task_id = pending_interactions[0]["task_id"]
    elif session_task_id:
        if hasattr(runtime, 'get_run_status'):
            s_run = runtime.get_run_status(session_task_id)
            if s_run:
                status_val = s_run.status.value if hasattr(s_run.status, "value") else str(s_run.status)
                if status_val in ("waiting_input", "pending_approval"):
                    waiting_task_id = session_task_id
        if not waiting_task_id:
            s_db_run = db.get_task_run(session_task_id)
            if s_db_run:
                status_val = s_db_run.status.value if hasattr(s_db_run.status, "value") else str(s_db_run.status)
                if status_val in ("waiting_input", "pending_approval"):
                    waiting_task_id = session_task_id

    # CASE A: Resuming an existing waiting task / approval
    if waiting_task_id:
        user_msg = db.save_chat_message({
            "conversation_id": conv["id"],
            "agent_id": agent_id,
            "task_id": waiting_task_id,
            "sender_type": "USER",
            "message_type": "CHAT",
            "content": payload.content,
            "metadata": {"task_id": waiting_task_id}
        })

        event_bus.publish(PlatformEvent(
            event_id=f"evt_{datetime.now().timestamp()}",
            event_type="chat.message",
            agent_id=agent_id,
            task_id=waiting_task_id,
            payload={
                "id": user_msg["id"],
                "sender_type": "USER",
                "content": payload.content,
                "task_id": waiting_task_id,
                "created_at": now_iso
            },
            source="chat_api"
        ))

        if pending_interactions:
            for inter in pending_interactions:
                db.resolve_interaction(
                    interaction_id=inter["id"],
                    resolution_response=payload.content,
                    resolved_by="HUMAN_OPERATOR",
                    decision="RESOLVED"
                )
                try:
                    db.save_agent_message(AgentMessage(
                        id=f"msg_a2a_{uuid.uuid4().hex[:12]}",
                        from_agent_id="HUMAN_OPERATOR",
                        to_agent_id=inter.get("requester_agent_id") or agent_id,
                        content=payload.content,
                        task_id=waiting_task_id,
                        run_id=waiting_task_id,
                        message_type="ANSWER",
                        status="DELIVERED",
                        metadata={"interaction_id": inter["id"]}
                    ))
                except Exception:
                    pass

                # If the question was asked by a subordinate, also notify subordinate's chat
                req_id = inter.get("requester_agent_id")
                if req_id and req_id != agent_id:
                    try:
                        req_conv = db.get_or_create_conversation(req_id)
                        sub_msg = db.save_chat_message({
                            "conversation_id": req_conv["id"],
                            "agent_id": req_id,
                            "task_id": waiting_task_id,
                            "sender_type": "USER",
                            "message_type": "CHAT",
                            "content": f"💬 **Supervisor ({agent_id}) Answer:**\n\n{payload.content}",
                            "metadata": {"interaction_id": inter["id"], "task_id": waiting_task_id}
                        })
                        event_bus.publish(PlatformEvent(
                            event_id=f"evt_{datetime.now().timestamp()}",
                            event_type="chat.message",
                            agent_id=req_id,
                            task_id=waiting_task_id,
                            payload={
                                "id": sub_msg["id"],
                                "sender_type": "USER",
                                "content": sub_msg["content"],
                                "task_id": waiting_task_id,
                                "created_at": datetime.now().isoformat()
                            },
                            source="chat_api"
                        ))
                    except Exception as sub_err:
                        logger.warning(f"Failed to record answer in subordinate chat: {sub_err}")

        db.update_task_run(waiting_task_id, status=TaskStatus.RUNNING)

        event_bus.publish(PlatformEvent(
            event_id=f"evt_{datetime.now().timestamp()}",
            event_type="approval.granted",
            agent_id=agent_id,
            task_id=waiting_task_id,
            payload={
                "task_id": waiting_task_id,
                "response": payload.content,
                "responder": "HUMAN_OPERATOR"
            },
            source="chat_api"
        ))

        if hasattr(runtime, "resume_task"):
            try:
                runtime.resume_task(waiting_task_id, payload.content)
            except Exception as res_err:
                logger.warning(f"Failed to resume task {waiting_task_id}: {res_err}")

        return {
            "status": "resolved_interaction" if pending_interactions else "resumed_task",
            "interaction_id": pending_interactions[0]["id"] if pending_interactions else None,
            "task_id": waiting_task_id,
            "run_id": waiting_task_id,
            "user_message": user_msg
        }

    # CASE B: Continuous task run for this session (1 Tab == 1 Session == 1 Task)
    target_task_id = conv.get("task_id") if conv else None
    if not target_task_id:
        target_task_id = f"task_{conv['id'].replace('conv_', '')}" if conv else f"task_{uuid.uuid4().hex[:12]}"
        if conv:
            db.update_conversation_session(
                conv["id"],
                claude_session_id=conv.get("claude_session_id") or "",
                task_id=target_task_id
            )
            conv["task_id"] = target_task_id

    # Look for existing session to resume within this conversation
    session_id_to_resume = None
    if conv and conv.get("claude_session_id"):
        candidate_sid = conv["claude_session_id"]
        # Only resume real Claude session IDs (not dummy sess_... placeholder)
        if candidate_sid and not candidate_sid.startswith("sess_") and not candidate_sid.startswith("pending_"):
            session_id_to_resume = candidate_sid

    # If conv has a previous task_id, also check that task run's session_id
    if not session_id_to_resume and target_task_id:
        try:
            prev_run = db.get_task_run(target_task_id)
            if prev_run and getattr(prev_run, "session_id", None):
                session_id_to_resume = prev_run.session_id
        except Exception:
            pass

    task_res = runtime.start_task(
        prompt=payload.content,
        agent_id=agent_id,
        project_id=payload.project_id,
        session_id=session_id_to_resume,
        task_id=target_task_id
    )
    if inspect.isawaitable(task_res):
        task_res = await task_res
    task_run_id = getattr(task_res, "run_id", str(task_res))

    user_msg = db.save_chat_message({
        "conversation_id": conv["id"],
        "agent_id": agent_id,
        "task_id": task_run_id,
        "sender_type": "USER",
        "message_type": "CHAT",
        "content": payload.content,
        "metadata": {"task_id": task_run_id}
    })

    # Associate this task with the conversation session
    try:
        db.update_conversation_session(
            conv["id"],
            claude_session_id=session_id_to_resume or conv.get("claude_session_id") or f"sess_{agent_id}_{uuid.uuid4().hex[:8]}",
            task_id=task_run_id
        )
    except Exception as e:
        logger.warning(f"Could not update conversation session: {e}")

    event_bus.publish(PlatformEvent(
        event_id=f"evt_{datetime.now().timestamp()}",
        event_type="chat.message",
        agent_id=agent_id,
        task_id=task_run_id,
        payload={
            "id": user_msg["id"],
            "sender_type": "USER",
            "content": payload.content,
            "task_id": task_run_id,
            "created_at": now_iso
        },
        source="chat_api"
    ))

    return {
        "status": "dispatched",
        "task_id": task_run_id,
        "run_id": task_run_id,
        "user_message": user_msg
    }


@router.post("/{agent_id}/clear")
async def clear_messages(
    agent_id: str,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Clear chat history for this agent."""
    db.clear_chat_history(agent_id)
    return {"status": "cleared", "agent_id": agent_id}
