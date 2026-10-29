"""Agents: commands ownership."""

from fastapi import HTTPException, Depends, status, Request
from ..dependencies import get_config_manager, get_db_manager, get_event_service, AgentConfig, EventService, EventType, validate_agent_hierarchy, HierarchyValidationError
from ..security import get_authorized_scope
from .agents_models import AgentCreate, AgentResponse, AgentUpdate
from .agents_mapping import _check_agent_scope, agent_to_response
from fastapi import APIRouter

router = APIRouter()


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
