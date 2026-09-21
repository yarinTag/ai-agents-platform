"""
Agent management API endpoints with organizational hierarchy support.
"""

from fastapi import APIRouter, HTTPException, Depends, status
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field
from datetime import datetime
import logging

from ..dependencies import (
    get_config_manager, get_db_manager, get_event_service,
    AgentConfig, EventService, EventType,
    validate_agent_hierarchy, HierarchyValidationError
)

logger = logging.getLogger(__name__)

router = APIRouter()


# Pydantic models for request/response
class AgentBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    system_prompt: str = Field(..., min_length=1)
    skills: List[str] = Field(default_factory=list)
    model: str = Field(default="default")
    effort: str = Field(default="medium")
    max_tokens: int = Field(default=8000, gt=0)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    repo_path: Optional[str] = None
    github_url: Optional[str] = None
    department: Optional[str] = "Engineering"
    avatar: Optional[str] = None

    # Organizational hierarchy fields
    parent_id: Optional[str] = None
    role_type: str = Field(default="WORKER")
    max_concurrent_children: int = Field(default=3, ge=1, le=20)
    delegation_strategy: str = Field(default="hierarchical")
    allowed_child_ids: List[str] = Field(default_factory=list)
    allowed_tools: List[str] = Field(default_factory=list)
    template_id: Optional[str] = None


class AgentCreate(AgentBase):
    pass


class AgentUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    system_prompt: Optional[str] = Field(None, min_length=1)
    skills: Optional[List[str]] = None
    model: Optional[str] = None
    effort: Optional[str] = None
    max_tokens: Optional[int] = Field(None, gt=0)
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    repo_path: Optional[str] = None
    github_url: Optional[str] = None
    department: Optional[str] = None
    avatar: Optional[str] = None

    # Organizational hierarchy fields
    parent_id: Optional[str] = None
    role_type: Optional[str] = None
    max_concurrent_children: Optional[int] = Field(None, ge=1, le=20)
    delegation_strategy: Optional[str] = None
    allowed_child_ids: Optional[List[str]] = None
    allowed_tools: Optional[List[str]] = None
    template_id: Optional[str] = None


class AgentResponse(AgentBase):
    id: str
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


# Helper function to convert AgentConfig to response dict
def agent_to_response(agent: AgentConfig) -> dict:
    now_iso = datetime.now().isoformat()
    return {
        "id": agent.id,
        "name": agent.name,
        "description": agent.description,
        "system_prompt": agent.system_prompt,
        "skills": agent.skills or [],
        "model": agent.model,
        "effort": agent.effort,
        "max_tokens": agent.max_tokens,
        "temperature": agent.temperature,
        "repo_path": getattr(agent, "repo_path", None),
        "github_url": getattr(agent, "github_url", None),
        "department": getattr(agent, "department", "Engineering"),
        "avatar": getattr(agent, "avatar", None),
        "created_at": getattr(agent, "created_at", None) or now_iso,
        "updated_at": getattr(agent, "updated_at", None) or now_iso,
        "parent_id": getattr(agent, "parent_id", None),
        "role_type": getattr(agent, "role_type", "WORKER"),
        "max_concurrent_children": getattr(agent, "max_concurrent_children", 3),
        "delegation_strategy": getattr(agent, "delegation_strategy", "hierarchical"),
        "allowed_child_ids": getattr(agent, "allowed_child_ids", []) or [],
        "allowed_tools": getattr(agent, "allowed_tools", []) or [],
        "template_id": getattr(agent, "template_id", None)
    }


@router.get("/", response_model=List[AgentResponse])
@router.get("", response_model=List[AgentResponse])
async def list_agents(
    db_manager = Depends(get_db_manager)
):
    """List all registered agents from the database (single source of truth)."""
    agents = db_manager.list_agents()
    return [agent_to_response(agent) for agent in agents]


@router.get("/hierarchy/tree", response_model=List[Dict[str, Any]])
@router.get("/hierarchy/tree/", response_model=List[Dict[str, Any]])
async def get_entire_hierarchy_tree(
    db_manager = Depends(get_db_manager)
):
    """Get the full organizational hierarchy tree from root orchestrators downward."""
    return db_manager.get_agent_hierarchy()


@router.post("/", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
@router.post("", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(
    agent_data: AgentCreate,
    config_manager = Depends(get_config_manager),
    db_manager = Depends(get_db_manager),
    event_service: EventService = Depends(get_event_service)
):
    """Create a new agent with hierarchy validation."""
    agent_id = agent_data.name.lower().replace(" ", "-").replace("_", "-")

    existing = db_manager.get_agent(agent_id) or config_manager.get_agent(agent_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Agent with ID '{agent_id}' already exists"
        )

    # Validate hierarchy constraints
    try:
        validate_agent_hierarchy(
            agent_id=agent_id,
            role_type=agent_data.role_type,
            parent_id=agent_data.parent_id,
            db_manager=db_manager
        )
    except HierarchyValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    agent_config = AgentConfig(
        id=agent_id,
        **agent_data.model_dump()
    )

    db_manager.save_agent(agent_config)
    config_manager.agents[agent_id] = agent_config

    saved = db_manager.get_agent(agent_id) or agent_config
    resp = agent_to_response(saved)
    event_service.emit(
        event_type=EventType.AGENT_CREATED,
        payload=resp,
        agent_id=agent_id,
        source="agents_api"
    )

    try:
        db_manager.log_audit(
            action="AGENT_CREATE",
            actor="api_client",
            entity_type="agent",
            entity_id=agent_id,
            details={"name": agent_data.name, "role_type": role_type, "parent_id": parent_id}
        )
    except Exception:
        pass

    return resp


@router.get("/{agent_id}", response_model=AgentResponse)
@router.get("/{agent_id}/", response_model=AgentResponse)
async def get_agent(
    agent_id: str,
    db_manager = Depends(get_db_manager)
):
    """Get a specific agent by ID."""
    agent = db_manager.get_agent(agent_id)
    if not agent:
        for a in db_manager.list_agents():
            if a.id.lower() == agent_id.lower():
                agent = a
                break
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent not found: {agent_id}"
        )
    return agent_to_response(agent)


@router.get("/{agent_id}/children", response_model=List[AgentResponse])
@router.get("/{agent_id}/children/", response_model=List[AgentResponse])
async def get_agent_children(
    agent_id: str,
    db_manager = Depends(get_db_manager)
):
    """Get all direct children reporting to this agent."""
    agent = db_manager.get_agent(agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent not found: {agent_id}"
        )
    children = db_manager.get_child_agents(agent_id)
    return [agent_to_response(c) for c in children]


@router.get("/{agent_id}/hierarchy", response_model=List[Dict[str, Any]])
@router.get("/{agent_id}/hierarchy/", response_model=List[Dict[str, Any]])
async def get_agent_subtree(
    agent_id: str,
    db_manager = Depends(get_db_manager)
):
    """Get the organizational subtree rooted at this agent."""
    agent = db_manager.get_agent(agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent not found: {agent_id}"
        )
    return db_manager.get_agent_hierarchy(root_id=agent_id)


@router.put("/{agent_id}", response_model=AgentResponse)
@router.put("/{agent_id}/", response_model=AgentResponse)
async def update_agent(
    agent_id: str,
    agent_data: AgentUpdate,
    config_manager = Depends(get_config_manager),
    db_manager = Depends(get_db_manager),
    event_service: EventService = Depends(get_event_service)
):
    """Update an existing agent with hierarchy validation."""
    existing = db_manager.get_agent(agent_id) or config_manager.get_agent(agent_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent not found: {agent_id}"
        )

    update_data = agent_data.model_dump(exclude_unset=True)

    # If role_type or parent_id changed, validate hierarchy
    target_role = update_data.get("role_type", existing.role_type)
    target_parent = update_data.get("parent_id", existing.parent_id)

    if "role_type" in update_data or "parent_id" in update_data:
        try:
            validate_agent_hierarchy(
                agent_id=agent_id,
                role_type=target_role,
                parent_id=target_parent,
                db_manager=db_manager
            )
        except HierarchyValidationError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )

    for field, value in update_data.items():
        setattr(existing, field, value)

    db_manager.save_agent(existing)
    config_manager.agents[agent_id] = existing

    updated = db_manager.get_agent(agent_id) or existing
    resp = agent_to_response(updated)
    event_service.emit(
        event_type=EventType.AGENT_UPDATED,
        payload=resp,
        agent_id=agent_id,
        source="agents_api"
    )

    try:
        db_manager.log_audit(
            action="AGENT_UPDATE",
            actor="api_client",
            entity_type="agent",
            entity_id=agent_id,
            details=update_data
        )
    except Exception:
        pass

    return resp


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
@router.delete("/{agent_id}/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: str,
    config_manager = Depends(get_config_manager),
    db_manager = Depends(get_db_manager),
    event_service: EventService = Depends(get_event_service)
):
    """Delete an agent."""
    existing = db_manager.get_agent(agent_id)
    if not existing:
        for a in db_manager.list_agents():
            if a.id.lower() == agent_id.lower():
                existing = a
                agent_id = a.id
                break
    if not existing:
        existing = config_manager.get_agent(agent_id)

    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent not found: {agent_id}"
        )

    # Check if agent has active children before deleting
    children = db_manager.get_child_agents(agent_id)
    if children:
        child_names = [c.name for c in children]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete agent '{agent_id}' because it has subordinate child agents: {child_names}. Reassign or remove them first."
        )

    db_manager.delete_agent(agent_id)
    if agent_id in config_manager.agents:
        del config_manager.agents[agent_id]

    event_service.emit(
        event_type=EventType.AGENT_DELETED,
        payload={"id": agent_id, "deleted": True},
        agent_id=agent_id,
        source="agents_api"
    )

    try:
        db_manager.log_audit(
            action="AGENT_DELETE",
            actor="api_client",
            entity_type="agent",
            entity_id=agent_id,
            details={"name": existing.name}
        )
    except Exception:
        pass

    return None