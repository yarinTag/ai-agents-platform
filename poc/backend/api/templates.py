"""
Agent template management and instantiation API endpoints.
"""

from fastapi import APIRouter, HTTPException, Depends, status, Query
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime
import logging

from ..dependencies import (
    get_db_manager, get_config_manager, get_event_service,
    AgentTemplate, AgentConfig, EventService, EventType,
    validate_agent_hierarchy, HierarchyValidationError
)
from .agents import agent_to_response, AgentResponse

logger = logging.getLogger(__name__)

router = APIRouter()


class TemplateBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str
    role: str = Field(default="WORKER")
    system_prompt: str = Field(..., min_length=1)
    model: str = Field(default="default")
    skills: List[str] = Field(default_factory=list)
    tools: List[str] = Field(default_factory=list)
    suggested_children: List[str] = Field(default_factory=list)
    category: str = Field(default="Engineering")


class TemplateCreate(TemplateBase):
    id: Optional[str] = None


class TemplateResponse(TemplateBase):
    id: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True


class TemplateInstantiateRequest(BaseModel):
    model_config = {"protected_namespaces": ()}
    name: str = Field(..., min_length=1, max_length=100)
    parent_id: Optional[str] = None
    department: Optional[str] = None
    repo_path: Optional[str] = None
    github_url: Optional[str] = None
    system_prompt_override: Optional[str] = None
    model_override: Optional[str] = None
    avatar: Optional[str] = None


def template_to_response(template: AgentTemplate) -> dict:
    now_iso = datetime.now().isoformat()
    return {
        "id": template.id,
        "name": template.name,
        "description": template.description,
        "role": template.role,
        "system_prompt": template.system_prompt,
        "model": template.model,
        "skills": template.skills or [],
        "tools": template.tools or [],
        "suggested_children": template.suggested_children or [],
        "category": template.category or "Engineering",
        "created_at": template.created_at or now_iso,
        "updated_at": template.updated_at or now_iso
    }


@router.get("/", response_model=List[TemplateResponse])
@router.get("", response_model=List[TemplateResponse])
async def list_templates(
    category: Optional[str] = Query(None, description="Filter templates by category"),
    db_manager = Depends(get_db_manager)
):
    """List all agent templates, optionally filtered by category."""
    templates = db_manager.list_templates(category=category)
    return [template_to_response(t) for t in templates]


@router.get("/{template_id}", response_model=TemplateResponse)
@router.get("/{template_id}/", response_model=TemplateResponse)
async def get_template(
    template_id: str,
    db_manager = Depends(get_db_manager)
):
    """Get a specific template by ID."""
    template = db_manager.get_template(template_id)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template not found: {template_id}"
        )
    return template_to_response(template)


@router.post("/", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
@router.post("", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    data: TemplateCreate,
    db_manager = Depends(get_db_manager)
):
    """Create a new reusable agent template."""
    template_id = data.id or data.name.lower().replace(" ", "-").replace("_", "-")
    existing = db_manager.get_template(template_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Template with ID '{template_id}' already exists"
        )

    template = AgentTemplate(
        id=template_id,
        name=data.name,
        description=data.description,
        role=data.role.upper(),
        system_prompt=data.system_prompt,
        model=data.model,
        skills=data.skills,
        tools=data.tools,
        suggested_children=data.suggested_children,
        category=data.category
    )
    saved = db_manager.save_template(template)
    return template_to_response(saved)


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
@router.delete("/{template_id}/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: str,
    db_manager = Depends(get_db_manager)
):
    """Delete an agent template."""
    deleted = db_manager.delete_template(template_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template not found: {template_id}"
        )
    return None


@router.post("/{template_id}/instantiate", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
@router.post("/{template_id}/instantiate/", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def instantiate_agent_from_template(
    template_id: str,
    request: TemplateInstantiateRequest,
    db_manager = Depends(get_db_manager),
    config_manager = Depends(get_config_manager),
    event_service: EventService = Depends(get_event_service)
):
    """Instantiate a new live agent from a template with full hierarchy validation."""
    template = db_manager.get_template(template_id)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template not found: {template_id}"
        )

    agent_id = request.name.lower().replace(" ", "-").replace("_", "-")

    max_agents = getattr(db_manager, "max_agents", 18)
    if len(db_manager.list_agents()) >= max_agents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Platform agent capacity reached: maximum {max_agents} agents allowed"
        )

    existing = db_manager.get_agent(agent_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Agent with ID '{agent_id}' already exists"
        )

    role_type = template.role.upper()
    try:
        validate_agent_hierarchy(
            agent_id=agent_id,
            role_type=role_type,
            parent_id=request.parent_id,
            db_manager=db_manager
        )
    except HierarchyValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    agent_config = AgentConfig(
        id=agent_id,
        name=request.name,
        description=template.description,
        system_prompt=request.system_prompt_override or template.system_prompt,
        skills=list(template.skills or []),
        model=request.model_override or template.model,
        effort="medium",
        max_tokens=8000,
        temperature=0.7,
        repo_path=request.repo_path,
        github_url=request.github_url,
        department=request.department or template.category or "Engineering",
        avatar=request.avatar,
        parent_id=request.parent_id,
        role_type=role_type,
        max_concurrent_children=3,
        delegation_strategy="hierarchical",
        allowed_child_ids=list(template.suggested_children or []),
        allowed_tools=list(template.tools or []),
        template_id=template.id
    )

    db_manager.save_agent(agent_config)
    config_manager.agents[agent_id] = agent_config

    saved = db_manager.get_agent(agent_id) or agent_config
    resp = agent_to_response(saved)

    event_service.emit(
        event_type=EventType.AGENT_CREATED,
        payload=resp,
        agent_id=agent_id,
        source="templates_api"
    )

    return resp
