"""
Internal Agent-to-Agent Messaging API router.
Supports first-class structured communication across agents with hierarchy authorization,
persistence, EventBus emission, and SSE delivery.
"""

from fastapi import APIRouter, HTTPException, Depends, status, Query
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
import uuid
import logging

from ..dependencies import (
    get_db_manager, get_event_service, DatabaseManager, EventService, EventType,
    validate_agent_communication, CommunicationAuthorizationError
)
from persistence import AgentMessage

logger = logging.getLogger(__name__)

router = APIRouter()


class SendAgentMessageRequest(BaseModel):
    from_agent_id: str = Field(..., min_length=1)
    to_agent_id: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)
    message_type: str = Field(default="QUESTION")  # QUESTION, ANSWER, REQUEST, DELEGATION, STATUS, RESULT, HANDOFF
    task_id: Optional[str] = None
    run_id: Optional[str] = None
    parent_message_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    channel_key: Optional[str] = None


class ReplyAgentMessageRequest(BaseModel):
    from_agent_id: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)
    message_type: str = Field(default="ANSWER")
    metadata: Optional[Dict[str, Any]] = None


class AgentMessageResponse(BaseModel):
    id: str
    from_agent_id: str
    to_agent_id: str
    content: str
    task_id: Optional[str] = None
    run_id: Optional[str] = None
    parent_message_id: Optional[str] = None
    channel_key: Optional[str] = None
    message_type: str
    status: str
    metadata: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None
    responded_at: Optional[str] = None


class AgentMessageDetailResponse(AgentMessageResponse):
    replies: List[AgentMessageResponse] = Field(default_factory=list)


@router.post("/", response_model=AgentMessageResponse, status_code=status.HTTP_201_CREATED)
@router.post("", response_model=AgentMessageResponse, status_code=status.HTTP_201_CREATED)
async def send_agent_message(
    req: SendAgentMessageRequest,
    db: DatabaseManager = Depends(get_db_manager),
    event_service: EventService = Depends(get_event_service)
):
    """
    Send a direct message from one agent to another.
    Validates sender and receiver existence, enforces hierarchy/communication rules,
    persists message, and emits SSE event.
    """
    sender = db.get_agent(req.from_agent_id)
    if not sender:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sender agent '{req.from_agent_id}' not found"
        )

    receiver = db.get_agent(req.to_agent_id)
    if not receiver:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Receiver agent '{req.to_agent_id}' not found"
        )

    # Validate communication permission
    try:
        validate_agent_communication(sender=sender, receiver=receiver, db_manager=db)
    except CommunicationAuthorizationError as auth_err:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(auth_err)
        )

    # Persist message
    msg_id = f"msg_{uuid.uuid4().hex[:12]}"
    now = datetime.now().isoformat()
    agent_msg = AgentMessage(
        id=msg_id,
        from_agent_id=req.from_agent_id,
        to_agent_id=req.to_agent_id,
        content=req.content,
        task_id=req.task_id,
        run_id=req.run_id,
        parent_message_id=req.parent_message_id,
        message_type=req.message_type.upper(),
        status="SENT",
        metadata=req.metadata,
        channel_key=req.channel_key,
        created_at=now
    )
    saved_msg = db.save_agent_message(agent_msg)

    # Emit canonical EventBus events for UI and observers
    try:
        event_service.emit(
            event_type=EventType.AGENT_MESSAGE_SENT,
            payload=saved_msg.to_dict(),
            agent_id=req.from_agent_id,
            task_id=req.task_id,
            source="agent_messaging"
        )
        event_service.emit(
            event_type=EventType.AGENT_MESSAGE_RECEIVED,
            payload=saved_msg.to_dict(),
            agent_id=req.to_agent_id,
            task_id=req.task_id,
            source="agent_messaging"
        )
    except Exception as eb_err:
        logger.warning(f"Failed emitting agent message event: {eb_err}")

    return AgentMessageResponse(**saved_msg.to_dict())


@router.post("/{message_id}/reply", response_model=AgentMessageResponse, status_code=status.HTTP_201_CREATED)
async def reply_agent_message(
    message_id: str,
    req: ReplyAgentMessageRequest,
    db: DatabaseManager = Depends(get_db_manager),
    event_service: EventService = Depends(get_event_service)
):
    """
    Reply to an existing agent message.
    """
    parent_msg = db.get_agent_message(message_id)
    if not parent_msg:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Message '{message_id}' not found"
        )

    sender = db.get_agent(req.from_agent_id)
    if not sender:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sender agent '{req.from_agent_id}' not found"
        )

    # Receiver of reply is original sender
    to_agent_id = parent_msg.from_agent_id
    receiver = db.get_agent(to_agent_id)
    if not receiver:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Original sender agent '{to_agent_id}' not found"
        )

    # Validate communication permission
    try:
        validate_agent_communication(sender=sender, receiver=receiver, db_manager=db)
    except CommunicationAuthorizationError as auth_err:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(auth_err)
        )

    now = datetime.now().isoformat()
    # Update parent message to ANSWERED
    db.update_agent_message(message_id, status="ANSWERED", responded_at=now)

    reply_msg_id = f"msg_{uuid.uuid4().hex[:12]}"
    reply_msg = AgentMessage(
        id=reply_msg_id,
        from_agent_id=req.from_agent_id,
        to_agent_id=to_agent_id,
        content=req.content,
        task_id=parent_msg.task_id,
        run_id=parent_msg.run_id,
        parent_message_id=message_id,
        channel_key=parent_msg.channel_key,
        message_type=req.message_type.upper(),
        status="SENT",
        metadata=req.metadata,
        created_at=now
    )
    saved_reply = db.save_agent_message(reply_msg)

    try:
        event_service.emit(
            event_type=EventType.AGENT_MESSAGE_SENT,
            payload=saved_reply.to_dict(),
            agent_id=req.from_agent_id,
            task_id=parent_msg.task_id,
            source="agent_messaging"
        )
        event_service.emit(
            event_type=EventType.AGENT_MESSAGE_RECEIVED,
            payload=saved_reply.to_dict(),
            agent_id=to_agent_id,
            task_id=parent_msg.task_id,
            source="agent_messaging"
        )
    except Exception as eb_err:
        logger.warning(f"Failed emitting reply message event: {eb_err}")

    return AgentMessageResponse(**saved_reply.to_dict())


@router.get("/", response_model=List[AgentMessageResponse])
@router.get("", response_model=List[AgentMessageResponse])
async def list_agent_messages(
    from_agent_id: Optional[str] = None,
    to_agent_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    task_id: Optional[str] = None,
    parent_message_id: Optional[str] = None,
    channel_key: Optional[str] = None,
    limit: int = Query(default=100, ge=1, le=500),
    db: DatabaseManager = Depends(get_db_manager)
):
    """List agent-to-agent messages with optional filters."""
    messages = db.list_agent_messages(
        from_agent_id=from_agent_id,
        to_agent_id=to_agent_id,
        agent_id=agent_id,
        task_id=task_id,
        parent_message_id=parent_message_id,
        channel_key=channel_key,
        limit=limit
    )
    return [AgentMessageResponse(**m.to_dict()) for m in messages]


@router.get("/{message_id}", response_model=AgentMessageDetailResponse)
async def get_agent_message_detail(
    message_id: str,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Retrieve an agent message and all replies in its thread."""
    msg = db.get_agent_message(message_id)
    if not msg:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Message '{message_id}' not found"
        )

    replies = db.list_agent_messages(parent_message_id=message_id)
    data = msg.to_dict()
    data["replies"] = [r.to_dict() for r in replies]
    return AgentMessageDetailResponse(**data)
