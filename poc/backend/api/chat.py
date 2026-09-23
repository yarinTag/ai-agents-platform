"""
Interactive Agent Chat API endpoints.
Provides real-time bidirectional communication between the operator and AI agents.
"""

from fastapi import APIRouter, HTTPException, Depends, status
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

from ..dependencies import get_db_manager, get_runtime_adapter, get_event_bus
from persistence import DatabaseManager
from runtime_adapter import ClaudeCodeRuntimeAdapter, TaskStatus
from events import EventBus, PlatformEvent, EventType

router = APIRouter()


class SendMessageRequest(BaseModel):
    content: str = Field(..., min_length=1)
    project_id: Optional[str] = None


@router.get("/{agent_id}/messages")
async def get_messages(
    agent_id: str,
    limit: int = 100,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Retrieve chat history, thoughts, and tool execution logs for an agent."""
    agent = db.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Agent '{agent_id}' not found")

    conv = db.get_or_create_conversation(agent_id)
    history = db.get_chat_history(agent_id, limit=limit)
    return {
        "conversation": conv,
        "messages": history
    }


@router.post("/{agent_id}/messages")
async def send_message(
    agent_id: str,
    payload: SendMessageRequest,
    db: DatabaseManager = Depends(get_db_manager),
    runtime: ClaudeCodeRuntimeAdapter = Depends(get_runtime_adapter),
    event_bus: EventBus = Depends(get_event_bus)
):
    """
    Send an interactive prompt or message directly to an agent.
    If the agent has a pending question/approval, automatically resolves it and resumes execution.
    Otherwise, launches or resumes an agent task.
    """
    agent = db.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Agent '{agent_id}' not found")

    conv = db.get_or_create_conversation(agent_id, project_id=payload.project_id)
    now_iso = datetime.now().isoformat()

    # 1. Record USER message in chat_messages
    user_msg = db.save_chat_message({
        "conversation_id": conv["id"],
        "agent_id": agent_id,
        "sender_type": "USER",
        "message_type": "CHAT",
        "content": payload.content
    })

    # Emit chat.message event to SSE stream
    event_bus.publish(PlatformEvent(
        event_id=f"evt_{datetime.now().timestamp()}",
        event_type="chat.message",
        agent_id=agent_id,
        payload={
            "id": user_msg["id"],
            "sender_type": "USER",
            "content": payload.content,
            "created_at": now_iso
        },
        source="chat_api"
    ))

    # 2. Check if agent is blocked on an interaction (WAITING_INPUT or PENDING_APPROVAL)
    pending_interactions = db.list_interactions(agent_id=agent_id, status="PENDING")
    if pending_interactions:
        interaction = pending_interactions[0]
        # Resolve interaction with this user message
        db.resolve_interaction(
            interaction_id=interaction["id"],
            resolution_response=payload.content,
            resolved_by="HUMAN_OPERATOR",
            decision="RESOLVED"
        )
        task_id = interaction["task_id"]
        db.update_task_run(task_id, status=TaskStatus.RUNNING)

        # Notify via SSE
        event_bus.publish(PlatformEvent(
            event_id=f"evt_{datetime.now().timestamp()}",
            event_type="approval.granted",
            agent_id=agent_id,
            task_id=task_id,
            payload={
                "interaction_id": interaction["id"],
                "response": payload.content,
                "responder": "HUMAN_OPERATOR"
            },
            source="chat_api"
        ))

        return {
            "status": "resolved_interaction",
            "interaction_id": interaction["id"],
            "task_id": task_id,
            "user_message": user_msg
        }

    # 3. Otherwise, start a fresh task or continue the existing session
    import inspect
    task_res = runtime.start_task(
        prompt=payload.content,
        agent_id=agent_id,
        project_id=payload.project_id
    )
    if inspect.isawaitable(task_res):
        task_res = await task_res
    task_run_id = getattr(task_res, "run_id", str(task_res))

    return {
        "status": "dispatched",
        "task_id": task_run_id,
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
