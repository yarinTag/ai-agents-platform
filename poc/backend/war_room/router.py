"""
Multi-Agent War Room & Deliberation API endpoints.
Enables cross-agent debate, consensus building, and collaborative planning before execution.
"""

from fastapi import APIRouter, HTTPException, Depends, status
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

from ..dependencies import get_db_manager, get_event_bus
from persistence import DatabaseManager
from events import EventBus, PlatformEvent

router = APIRouter()


class WarRoomCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=150)
    topic: str = Field(..., min_length=1)
    project_id: Optional[str] = None
    moderator_agent_id: str = Field(..., min_length=1)
    participant_agent_ids: List[str] = Field(..., min_length=1)


class WarRoomMessageCreate(BaseModel):
    agent_id: str = Field(..., min_length=1)
    round_number: int = Field(default=1, ge=1)
    message_type: str = Field(default="PROPOSAL", pattern="^(PROPOSAL|CRITIQUE|CONSENSUS_VOTE|SUMMARY)$")
    content: str = Field(..., min_length=1)


class SynthesizePlanRequest(BaseModel):
    synthesized_plan: str = Field(..., min_length=1)


@router.get("/")
async def list_war_room_sessions(
    project_id: Optional[str] = None,
    db: DatabaseManager = Depends(get_db_manager)
):
    """List all war room sessions."""
    sessions = db.list_war_room_sessions(project_id=project_id)
    return sessions


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_session(
    payload: WarRoomCreate,
    db: DatabaseManager = Depends(get_db_manager),
    event_bus: EventBus = Depends(get_event_bus)
):
    """Initiate a new multi-agent war room session."""
    session = db.create_war_room_session({
        "title": payload.title,
        "topic": payload.topic,
        "project_id": payload.project_id,
        "moderator_agent_id": payload.moderator_agent_id,
        "participant_agent_ids": payload.participant_agent_ids,
        "status": "DEBATING"
    })

    # Broadcast war room started event
    event_bus.publish(PlatformEvent(
        event_id=f"evt_{datetime.now().timestamp()}",
        event_type="war_room.started",
        project_id=payload.project_id,
        agent_id=payload.moderator_agent_id,
        payload={
            "session_id": session["id"],
            "title": session["title"],
            "topic": session["topic"],
            "participants": payload.participant_agent_ids
        },
        source="war_room_api"
    ))

    return session


@router.get("/{session_id}")
async def get_session(
    session_id: str,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Retrieve details and all dialogue messages of a war room session."""
    session = db.get_war_room_session(session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="War room session not found")

    messages = db.get_war_room_messages(session_id)
    return {
        "session": session,
        "messages": messages
    }


@router.post("/{session_id}/messages")
async def add_message(
    session_id: str,
    payload: WarRoomMessageCreate,
    db: DatabaseManager = Depends(get_db_manager),
    event_bus: EventBus = Depends(get_event_bus)
):
    """Add an argument, critique, or proposal to the deliberation round."""
    session = db.get_war_room_session(session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="War room session not found")

    msg = db.add_war_room_message({
        "session_id": session_id,
        "agent_id": payload.agent_id,
        "round_number": payload.round_number,
        "message_type": payload.message_type,
        "content": payload.content
    })

    # Broadcast speech event
    event_bus.publish(PlatformEvent(
        event_id=f"evt_{datetime.now().timestamp()}",
        event_type="war_room.message",
        agent_id=payload.agent_id,
        payload={
            "session_id": session_id,
            "agent_id": payload.agent_id,
            "round_number": payload.round_number,
            "message_type": payload.message_type,
            "content": payload.content
        },
        source="war_room_api"
    ))

    return msg


@router.post("/{session_id}/synthesize")
async def synthesize_plan(
    session_id: str,
    payload: SynthesizePlanRequest,
    db: DatabaseManager = Depends(get_db_manager),
    event_bus: EventBus = Depends(get_event_bus)
):
    """Finalize the deliberation with an agreed synthesized execution plan."""
    session = db.get_war_room_session(session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="War room session not found")

    updated = db.update_war_room_session(session_id, {
        "status": "CONSENSUS_REACHED",
        "synthesized_plan": payload.synthesized_plan
    })

    event_bus.publish(PlatformEvent(
        event_id=f"evt_{datetime.now().timestamp()}",
        event_type="war_room.consensus_reached",
        payload={
            "session_id": session_id,
            "synthesized_plan": payload.synthesized_plan
        },
        source="war_room_api"
    ))

    return updated
