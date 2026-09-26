"""
Approvals & Agent Interactions API endpoints.
Enables Human-In-The-Loop (HITL) and Manager-In-The-Loop approval and clarification workflows.
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


class InteractionCreate(BaseModel):
    task_id: str = Field(..., min_length=1)
    requester_agent_id: str = Field(..., min_length=1)
    target_approver_id: Optional[str] = None
    interaction_type: str = Field(default="QUESTION", pattern="^(QUESTION|PERMISSION_APPROVAL|REVIEW)$")
    title: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)
    context_data: Optional[Dict[str, Any]] = None


class InteractionResponse(BaseModel):
    interaction_id: str = Field(..., min_length=1)
    decision: str = Field(default="approve", pattern="^(approve|reject)$")
    response_text: str = Field(..., min_length=1)
    responder: str = "HUMAN_OPERATOR"


@router.get("/pending")
async def list_pending_approvals(
    agent_id: Optional[str] = None,
    target_approver_id: Optional[str] = None,
    db: DatabaseManager = Depends(get_db_manager)
):
    """List all pending questions and approval requests."""
    interactions = db.list_interactions(
        agent_id=agent_id,
        target_approver_id=target_approver_id,
        status="PENDING"
    )
    return interactions


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_approval_request(
    payload: InteractionCreate,
    db: DatabaseManager = Depends(get_db_manager),
    runtime: ClaudeCodeRuntimeAdapter = Depends(get_runtime_adapter),
    event_bus: EventBus = Depends(get_event_bus)
):
    """
    Called when an agent raises a question or requires approval.
    Automatically resolves target approver via hierarchy if not specified.
    """
    agent = db.get_agent(payload.requester_agent_id)
    target_approver = payload.target_approver_id
    if not target_approver:
        # Determine approver from hierarchy (Manager / parent_id)
        if agent and getattr(agent, "parent_id", None):
            target_approver = agent.parent_id
        else:
            target_approver = "HUMAN_OPERATOR"

    interaction = db.create_interaction({
        "task_id": payload.task_id,
        "requester_agent_id": payload.requester_agent_id,
        "target_approver_id": target_approver,
        "interaction_type": payload.interaction_type,
        "title": payload.title,
        "content": payload.content,
        "context_data": payload.context_data
    })

    # Update task run status to WAITING_INPUT or PENDING_APPROVAL
    new_status = TaskStatus.WAITING_INPUT if payload.interaction_type == "QUESTION" else TaskStatus.PENDING_APPROVAL
    db.update_task_run(payload.task_id, status=new_status)

    # Publish notification event over SSE
    event_bus.publish(PlatformEvent(
        event_id=f"evt_{datetime.now().timestamp()}",
        sequence_number=0,
        event_type=EventType.APPROVAL_REQUIRED if hasattr(EventType, 'APPROVAL_REQUIRED') else 'approval.required',
        agent_id=payload.requester_agent_id,
        task_id=payload.task_id,
        payload={
            "interaction_id": interaction["id"],
            "title": payload.title,
            "content": payload.content,
            "interaction_type": payload.interaction_type,
            "target_approver": target_approver
        },
        source="approvals_api"
    ))

    return interaction


@router.post("/respond")
async def respond_to_interaction(
    payload: InteractionResponse,
    db: DatabaseManager = Depends(get_db_manager),
    runtime: ClaudeCodeRuntimeAdapter = Depends(get_runtime_adapter),
    event_bus: EventBus = Depends(get_event_bus)
):
    """
    Answer an agent's question or approve/reject its action.
    Unblocks the task and resumes execution.
    """
    interaction = db.get_interaction(payload.interaction_id)
    if not interaction:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interaction not found")

    decision_status = "RESOLVED" if payload.decision == "approve" else "REJECTED"
    updated_interaction = db.resolve_interaction(
        interaction_id=payload.interaction_id,
        resolution_response=payload.response_text,
        resolved_by=payload.responder,
        decision=decision_status
    )

    task_id = interaction["task_id"]
    task_run = db.get_task_run(task_id)

    # If approved / answered, resume task
    if payload.decision == "approve":
        try:
            from persistence import AgentMessage
            db.save_agent_message(AgentMessage(
                id=f"msg_ans_{datetime.now().timestamp()}",
                from_agent_id=payload.responder,
                to_agent_id=interaction["requester_agent_id"],
                content=payload.response_text,
                task_id=task_id,
                message_type="ANSWER",
                status="SENT",
                metadata={"interaction_id": payload.interaction_id, "decision": payload.decision}
            ))
        except Exception as msg_err:
            import logging
            logging.getLogger(__name__).warning(f"Failed to record AgentMessage response: {msg_err}")

        # Record response in chat_messages for both supervisor and requester
        try:
            target_approver = interaction.get("target_approver_id")
            if target_approver and target_approver != "HUMAN_OPERATOR":
                sup_conv = db.get_or_create_conversation(target_approver)
                sup_msg = db.save_chat_message({
                    "conversation_id": sup_conv["id"],
                    "agent_id": target_approver,
                    "task_id": task_id,
                    "sender_type": "USER",
                    "message_type": "CHAT",
                    "content": f"💬 **Response provided to {interaction['requester_agent_id']}:**\n\n{payload.response_text}",
                    "metadata": {"interaction_id": payload.interaction_id, "task_id": task_id}
                })
                event_bus.publish(PlatformEvent(
                    event_id=f"evt_{datetime.now().timestamp()}",
                    event_type="chat.message",
                    agent_id=target_approver,
                    task_id=task_id,
                    payload={
                        "id": sup_msg["id"],
                        "sender_type": "USER",
                        "content": sup_msg["content"],
                        "task_id": task_id,
                        "created_at": datetime.now().isoformat()
                    },
                    source="approvals_api"
                ))

            requester_id = interaction.get("requester_agent_id")
            if requester_id:
                req_conv = db.get_or_create_conversation(requester_id)
                req_msg = db.save_chat_message({
                    "conversation_id": req_conv["id"],
                    "agent_id": requester_id,
                    "task_id": task_id,
                    "sender_type": "USER",
                    "message_type": "CHAT",
                    "content": f"💬 **Supervisor ({target_approver or 'Lead'}) Answer:**\n\n{payload.response_text}",
                    "metadata": {"interaction_id": payload.interaction_id, "task_id": task_id}
                })
                event_bus.publish(PlatformEvent(
                    event_id=f"evt_{datetime.now().timestamp()}",
                    event_type="chat.message",
                    agent_id=requester_id,
                    task_id=task_id,
                    payload={
                        "id": req_msg["id"],
                        "sender_type": "USER",
                        "content": req_msg["content"],
                        "task_id": task_id,
                        "created_at": datetime.now().isoformat()
                    },
                    source="approvals_api"
                ))
        except Exception as chat_err:
            import logging
            logging.getLogger(__name__).warning(f"Failed to record approval chat message: {chat_err}")

        db.update_task_run(task_id, status=TaskStatus.RUNNING)
        try:
            if hasattr(runtime, "resume_task"):
                runtime.resume_task(task_id, payload.response_text)
        except Exception as res_err:
            import logging
            logging.getLogger(__name__).warning(f"Failed to auto resume task {task_id}: {res_err}")

        event_bus.publish(PlatformEvent(
            event_id=f"evt_{datetime.now().timestamp()}",
            sequence_number=0,
            event_type=EventType.APPROVAL_GRANTED if hasattr(EventType, 'APPROVAL_GRANTED') else 'approval.granted',
            agent_id=interaction["requester_agent_id"],
            task_id=task_id,
            payload={
                "interaction_id": payload.interaction_id,
                "response": payload.response_text,
                "responder": payload.responder
            },
            source="approvals_api"
        ))
    else:
        db.update_task_run(task_id, status=TaskStatus.FAILED, error=f"Rejected: {payload.response_text}")
        event_bus.publish(PlatformEvent(
            event_id=f"evt_{datetime.now().timestamp()}",
            sequence_number=0,
            event_type=EventType.APPROVAL_DENIED if hasattr(EventType, 'APPROVAL_DENIED') else 'approval.denied',
            agent_id=interaction["requester_agent_id"],
            task_id=task_id,
            payload={
                "interaction_id": payload.interaction_id,
                "reason": payload.response_text,
                "responder": payload.responder
            },
            source="approvals_api"
        ))

    return {
        "status": "success",
        "interaction": updated_interaction,
        "task_id": task_id,
        "resumed": payload.decision == "approve"
    }
