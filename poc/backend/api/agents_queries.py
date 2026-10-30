"""Agents: queries ownership."""

from fastapi import HTTPException, Depends, status, Request
from typing import List, Optional, Any, Dict
from ..dependencies import get_db_manager
from ..security import get_authorized_scope
from .agents_models import AgentResponse
from .agents_mapping import _check_agent_scope, agent_to_response
from fastapi import APIRouter

router = APIRouter()


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

