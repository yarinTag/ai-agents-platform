"""
Project Shared Memory & Knowledge Base API endpoints.
Enables agents to persist and share architectural decisions, conventions, and learnings.
"""

from fastapi import APIRouter, HTTPException, Depends, status
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

from ..dependencies import get_db_manager, get_event_bus
from persistence import DatabaseManager
from events import EventBus, PlatformEvent

router = APIRouter()


class MemoryCreate(BaseModel):
    category: str = Field(default="INSIGHT", pattern="^(ADR|CONVENTION|INSIGHT|LESSON)$")
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)
    tags: Optional[List[str]] = None
    author_agent_id: Optional[str] = None


@router.get("/{project_id}/memories")
async def list_memories(
    project_id: str,
    category: Optional[str] = None,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Retrieve shared knowledge memories for a project."""
    memories = db.list_project_memories(project_id=project_id, category=category)
    return memories


@router.post("/{project_id}/memories", status_code=status.HTTP_201_CREATED)
async def create_memory(
    project_id: str,
    payload: MemoryCreate,
    db: DatabaseManager = Depends(get_db_manager),
    event_bus: EventBus = Depends(get_event_bus)
):
    """Save a new knowledge memory, ADR, or convention to the project pool."""
    mem = db.create_project_memory({
        "project_id": project_id,
        "category": payload.category,
        "title": payload.title,
        "content": payload.content,
        "tags": payload.tags or [],
        "author_agent_id": payload.author_agent_id
    })

    # Broadcast memory created event
    event_bus.publish(PlatformEvent(
        event_id=f"evt_{datetime.now().timestamp()}",
        event_type="memory.created",
        project_id=project_id,
        agent_id=payload.author_agent_id,
        payload={
            "id": mem["id"],
            "title": mem["title"],
            "category": mem["category"]
        },
        source="memory_api"
    ))

    return mem


@router.delete("/{project_id}/memories/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory(
    project_id: str,
    memory_id: str,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Delete a memory item."""
    success = db.delete_project_memory(memory_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory item not found")
    return None


@router.get("/{project_id}/context-prompt")
async def get_context_prompt(
    project_id: str,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Generate Markdown prompt containing all shared knowledge and ADRs for LLM prompt injection."""
    memories = db.list_project_memories(project_id=project_id)
    if not memories:
        return {"context_prompt": "", "memories_count": 0}

    lines = ["# 🧠 PROJECT SHARED KNOWLEDGE & ACTIVE CONVENTIONS", ""]
    for m in memories:
        lines.append(f"### [{m['category']}] {m['title']}")
        lines.append(m['content'])
        if m.get('tags'):
            lines.append(f"*Tags: {', '.join(m['tags'])}*")
        lines.append("")

    return {
        "context_prompt": "\n".join(lines),
        "memories_count": len(memories)
    }
