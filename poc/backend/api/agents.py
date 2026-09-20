"""
Agent management API endpoints.
"""

from fastapi import APIRouter, HTTPException, Depends, status
from typing import List, Optional
from pydantic import BaseModel, Field

# Import from parent directory (backend)
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dependencies import get_config_manager, get_db_manager
from config import AgentConfig


router = APIRouter()


# Pydantic models for request/response
class AgentBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    system_prompt: str = Field(..., min_length=1)
    skills: List[str] = Field(default_factory=list)
    model: str = Field(default="default")
    effort: str = Field(default="medium")
    max_tokens: int = Field(default=4000, gt=0)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    repo_path: Optional[str] = None
    github_url: Optional[str] = None
    department: Optional[str] = "Engineering"
    avatar: Optional[str] = None


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


class AgentResponse(AgentBase):
    id: str
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


# Helper function to convert AgentConfig to response dict
def agent_to_response(agent: AgentConfig) -> dict:
    return {
        "id": agent.id,
        "name": agent.name,
        "description": agent.description,
        "system_prompt": agent.system_prompt,
        "skills": agent.skills,
        "model": agent.model,
        "effort": agent.effort,
        "max_tokens": agent.max_tokens,
        "temperature": agent.temperature,
        "repo_path": getattr(agent, "repo_path", None),
        "github_url": getattr(agent, "github_url", None),
        "department": getattr(agent, "department", "Engineering"),
        "avatar": getattr(agent, "avatar", None),
        "created_at": "",  # Would come from DB in real implementation
        "updated_at": ""   # Would come from DB in real implementation
    }


@router.get("/", response_model=List[AgentResponse])
@router.get("", response_model=List[AgentResponse])
async def list_agents(
    config_manager = Depends(get_config_manager),
    db_manager = Depends(get_db_manager)
):
    """List all registered agents from both config and database."""
    agents_map = {}
    for a in db_manager.list_agents():
        agents_map[a.id] = a
    for a in config_manager.list_agents():
        agents_map[a.id] = a
    return [agent_to_response(agent) for agent in agents_map.values()]


@router.post("/", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
@router.post("", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(
    agent_data: AgentCreate,
    config_manager = Depends(get_config_manager),
    db_manager = Depends(get_db_manager)
):
    """Create a new agent."""
    agent_id = agent_data.name.lower().replace(" ", "-").replace("_", "-")

    existing = config_manager.get_agent(agent_id) or db_manager.get_agent(agent_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Agent with ID '{agent_id}' already exists"
        )

    agent_config = AgentConfig(
        id=agent_id,
        **agent_data.model_dump()
    )

    config_manager.register_agent(agent_config)
    db_manager.save_agent(agent_config)

    return agent_to_response(agent_config)


@router.get("/{agent_id}", response_model=AgentResponse)
@router.get("/{agent_id}/", response_model=AgentResponse)
async def get_agent(
    agent_id: str,
    config_manager = Depends(get_config_manager),
    db_manager = Depends(get_db_manager)
):
    """Get a specific agent by ID."""
    agent = config_manager.get_agent(agent_id) or db_manager.get_agent(agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent not found: {agent_id}"
        )
    return agent_to_response(agent)


@router.put("/{agent_id}", response_model=AgentResponse)
@router.put("/{agent_id}/", response_model=AgentResponse)
async def update_agent(
    agent_id: str,
    agent_data: AgentUpdate,
    config_manager = Depends(get_config_manager),
    db_manager = Depends(get_db_manager)
):
    """Update an existing agent."""
    existing = config_manager.get_agent(agent_id) or db_manager.get_agent(agent_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent not found: {agent_id}"
        )

    update_data = agent_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(existing, field, value)

    config_manager.register_agent(existing)
    db_manager.save_agent(existing)

    return agent_to_response(existing)


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
@router.delete("/{agent_id}/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: str,
    config_manager = Depends(get_config_manager),
    db_manager = Depends(get_db_manager)
):
    """Delete an agent."""
    existing = config_manager.get_agent(agent_id) or db_manager.get_agent(agent_id)
    if not existing:
        for a in config_manager.list_agents():
            if a.id.lower() == agent_id.lower():
                existing = a
                agent_id = a.id
                break
    if not existing:
        for a in db_manager.list_agents():
            if a.id.lower() == agent_id.lower():
                existing = a
                agent_id = a.id
                break

    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent not found: {agent_id}"
        )

    config_manager.delete_agent(agent_id)
    try:
        db_manager.delete_agent(agent_id)
    except Exception as e:
        print(f"Warning deleting agent from DB: {e}")

    return None