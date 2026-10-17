"""
Agent management API endpoints with organizational hierarchy support.
"""

from fastapi import APIRouter, HTTPException, Depends, status, Request
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
import logging

from ..dependencies import (
    get_config_manager, get_db_manager, get_event_service,
    AgentConfig, EventService, EventType,
    validate_agent_hierarchy, HierarchyValidationError,
    runtime_providers as providers
)
from ..security import get_current_org_id, get_authorized_scope

logger = logging.getLogger(__name__)

router = APIRouter()


def _check_runtime_provider(value: Optional[str]) -> Optional[str]:
    """Reject unknown provider IDs at the boundary; None means inherit the default."""
    if value is None or not value.strip():
        return None
    candidate = value.strip()
    if candidate not in providers.ALL_PROVIDER_IDS:
        raise ValueError(
            f"Unknown runtime provider '{candidate}'. "
            f"Expected one of: {', '.join(providers.ALL_PROVIDER_IDS)}."
        )
    return candidate


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
    allow_sibling_communication: bool = Field(default=True)
    allowed_peer_ids: List[str] = Field(default_factory=list)
    mcp_permissions: List[str] = Field(default_factory=list)
    # None = inherit the platform-default runtime provider
    runtime_provider: Optional[str] = None
    is_workflow_agent: bool = Field(default=False)
    workflow_id: Optional[str] = None
    organization_id: Optional[str] = None
    department_id: Optional[str] = None

    _validate_provider = field_validator('runtime_provider')(_check_runtime_provider)


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
    allow_sibling_communication: Optional[bool] = None
    allowed_peer_ids: Optional[List[str]] = None
    mcp_permissions: Optional[List[str]] = None
    runtime_provider: Optional[str] = None
    is_workflow_agent: Optional[bool] = False
    workflow_id: Optional[str] = None
    organization_id: Optional[str] = None
    department_id: Optional[str] = None

    _validate_provider = field_validator('runtime_provider')(_check_runtime_provider)


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
        "template_id": getattr(agent, "template_id", None),
        "allow_sibling_communication": getattr(agent, "allow_sibling_communication", True),
        "allowed_peer_ids": getattr(agent, "allowed_peer_ids", []) or [],
        "mcp_permissions": getattr(agent, "mcp_permissions", []) or [],
        "runtime_provider": getattr(agent, "runtime_provider", None),
        "is_workflow_agent": getattr(agent, "is_workflow_agent", False) or False,
        "workflow_id": getattr(agent, "workflow_id", None),
        "organization_id": getattr(agent, "organization_id", None),
        "department_id": getattr(agent, "department_id", None)
    }


def _check_agent_scope(agent: AgentConfig, scope: Dict[str, Any]):
    org_id = scope["org_id"]
    is_org_admin = scope["is_org_admin"]
    authorized_dept_ids = scope["department_ids"]

    if org_id and getattr(agent, "organization_id", None) and agent.organization_id != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    if not is_org_admin and getattr(agent, "department_id", None) and authorized_dept_ids and agent.department_id not in authorized_dept_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access agent in this department")


@router.get("/", response_model=List[AgentResponse])
@router.get("", response_model=List[AgentResponse])
async def list_agents(
    request: Request,
    department_id: Optional[str] = None,
    db_manager = Depends(get_db_manager)
):
    """List all registered agents from the database, strictly scoped by organization and department."""
    scope = get_authorized_scope(request, db_manager)
    org_id = scope["org_id"]
    is_org_admin = scope["is_org_admin"]
    authorized_dept_ids = scope["department_ids"]

    target_dept_ids = None
    if department_id:
        if not is_org_admin and department_id not in authorized_dept_ids:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access agents in this department")
        target_dept_ids = [department_id]
    elif not is_org_admin and org_id:
        target_dept_ids = authorized_dept_ids

    agents = db_manager.list_agents(organization_id=org_id, department_ids=target_dept_ids)
    return [agent_to_response(agent) for agent in agents]


@router.get("/hierarchy/tree", response_model=List[Dict[str, Any]])
@router.get("/hierarchy/tree/", response_model=List[Dict[str, Any]])
async def get_entire_hierarchy_tree(
    request: Request,
    department_id: Optional[str] = None,
    db_manager = Depends(get_db_manager)
):
    """Get the full organizational hierarchy tree, strictly scoped by organization and department."""
    scope = get_authorized_scope(request, db_manager)
    org_id = scope["org_id"]
    is_org_admin = scope["is_org_admin"]
    authorized_dept_ids = scope["department_ids"]

    target_dept_ids = None
    if department_id:
        if not is_org_admin and department_id not in authorized_dept_ids:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access hierarchy in this department")
        target_dept_ids = [department_id]
    elif not is_org_admin and org_id:
        target_dept_ids = authorized_dept_ids

    return db_manager.get_agent_hierarchy(organization_id=org_id, department_ids=target_dept_ids)


@router.post("/", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
@router.post("", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(
    agent_data: AgentCreate,
    request: Request,
    config_manager = Depends(get_config_manager),
    db_manager = Depends(get_db_manager),
    event_service: EventService = Depends(get_event_service)
):
    """Create a new agent with strict hierarchy and department validation."""
    scope = get_authorized_scope(request, db_manager)
    org_id = scope["org_id"]
    is_org_admin = scope["is_org_admin"]
    authorized_dept_ids = scope["department_ids"]

    agent_id = agent_data.name.lower().replace(" ", "-").replace("_", "-")

    max_agents = getattr(db_manager, "max_agents", 18)
    if len(db_manager.list_agents(organization_id=org_id)) >= max_agents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Platform agent capacity reached: maximum {max_agents} agents allowed"
        )

    existing = db_manager.get_agent(agent_id) or config_manager.get_agent(agent_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Agent with ID '{agent_id}' already exists"
        )

    # Department and Organization scoping
    dept_id = agent_data.department_id or scope["default_department_id"]
    dept_name = agent_data.department or "Engineering"
    if dept_id:
        dept = db_manager.get_department(dept_id)
        if not dept or (org_id and dept.organization_id and dept.organization_id != org_id):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Department '{dept_id}' does not belong to your organization")
        if not is_org_admin and dept_id not in authorized_dept_ids:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Not authorized to assign agent to department '{dept_id}'")
        dept_name = dept.name

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

    agent_dict = agent_data.model_dump()
    agent_dict["organization_id"] = org_id
    agent_dict["department_id"] = dept_id
    if dept_id:
        agent_dict["department"] = dept_name

    agent_config = AgentConfig(
        id=agent_id,
        **agent_dict
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
            details={"name": agent_data.name, "role_type": agent_data.role_type, "parent_id": agent_data.parent_id, "organization_id": org_id, "department_id": dept_id}
        )
    except Exception:
        pass

    return resp


@router.get("/{agent_id}", response_model=AgentResponse)
@router.get("/{agent_id}/", response_model=AgentResponse)
async def get_agent(
    agent_id: str,
    request: Request,
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
    scope = get_authorized_scope(request, db_manager)
    _check_agent_scope(agent, scope)
    return agent_to_response(agent)


@router.get("/{agent_id}/children", response_model=List[AgentResponse])
@router.get("/{agent_id}/children/", response_model=List[AgentResponse])
async def get_agent_children(
    agent_id: str,
    request: Request,
    db_manager = Depends(get_db_manager)
):
    """Get all direct children reporting to this agent."""
    agent = db_manager.get_agent(agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent not found: {agent_id}"
        )
    scope = get_authorized_scope(request, db_manager)
    _check_agent_scope(agent, scope)
    children = db_manager.get_child_agents(agent_id)
    filtered_children = []
    for c in children:
        try:
            _check_agent_scope(c, scope)
            filtered_children.append(c)
        except HTTPException:
            pass
    return [agent_to_response(c) for c in filtered_children]


@router.get("/{agent_id}/hierarchy", response_model=List[Dict[str, Any]])
@router.get("/{agent_id}/hierarchy/", response_model=List[Dict[str, Any]])
async def get_agent_subtree(
    agent_id: str,
    request: Request,
    db_manager = Depends(get_db_manager)
):
    """Get the organizational subtree rooted at this agent."""
    agent = db_manager.get_agent(agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent not found: {agent_id}"
        )
    scope = get_authorized_scope(request, db_manager)
    _check_agent_scope(agent, scope)
    return db_manager.get_agent_hierarchy(root_id=agent_id, organization_id=scope["org_id"])


@router.put("/{agent_id}", response_model=AgentResponse)
@router.put("/{agent_id}/", response_model=AgentResponse)
async def update_agent(
    agent_id: str,
    agent_data: AgentUpdate,
    request: Request,
    config_manager = Depends(get_config_manager),
    db_manager = Depends(get_db_manager),
    event_service: EventService = Depends(get_event_service)
):
    """Update an existing agent with hierarchy and department validation."""
    existing = db_manager.get_agent(agent_id) or config_manager.get_agent(agent_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent not found: {agent_id}"
        )
    scope = get_authorized_scope(request, db_manager)
    _check_agent_scope(existing, scope)

    update_data = agent_data.model_dump(exclude_unset=True)

    # If updating department_id, check authorization
    if "department_id" in update_data and update_data["department_id"]:
        new_dept_id = update_data["department_id"]
        dept = db_manager.get_department(new_dept_id)
        if not dept or (scope["org_id"] and dept.organization_id and dept.organization_id != scope["org_id"]):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Department '{new_dept_id}' does not belong to your organization")
        if not scope["is_org_admin"] and new_dept_id not in scope["department_ids"]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Not authorized to assign agent to department '{new_dept_id}'")
        update_data["department"] = dept.name

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
    request: Request,
    cascade: bool = False,
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

    scope = get_authorized_scope(request, db_manager)
    _check_agent_scope(existing, scope)

    # Check if agent has active children before deleting
    children = db_manager.get_child_agents(agent_id)
    if children and not cascade:
        child_names = [c.name for c in children]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete agent '{agent_id}' because it has subordinate child agents: {child_names}. Reassign or remove them first."
        )

    if children and cascade:
        for child in children:
            child.parent_id = None
            db_manager.save_agent(child)

    db_manager.delete_agent(agent_id)
    config_manager.delete_agent(agent_id)

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