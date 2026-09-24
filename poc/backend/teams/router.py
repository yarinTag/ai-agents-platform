"""
Agent Teams API Router.
Supports creation, management, dispatching, and executive synthesis of temporary agent teams.
"""

from fastapi import APIRouter, HTTPException, Depends, status, Query
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
import logging

from ..dependencies import (
    get_db_manager, get_event_service, get_team_coordinator,
    DatabaseManager, EventService, TeamCoordinator
)
from persistence import AgentTeam

logger = logging.getLogger(__name__)

router = APIRouter()


class CreateTeamRequest(BaseModel):
    name: str = Field(..., min_length=1)
    manager_agent_id: str = Field(..., min_length=1)
    member_agent_ids: List[str] = Field(..., min_length=1)
    project_id: Optional[str] = None
    description: Optional[str] = None


class DispatchTeamRequest(BaseModel):
    shared_goal: str = Field(..., min_length=1)
    member_prompts: Optional[Dict[str, str]] = None
    parent_task_id: Optional[str] = None


class SynthesizeTeamRequest(BaseModel):
    task_ids: List[str] = Field(..., min_length=1)



class TeamMemberResponse(BaseModel):
    agent_id: str
    role_in_team: str = "REVIEWER"


class TeamResponse(BaseModel):
    id: str
    name: str
    manager_agent_id: str
    project_id: Optional[str] = None
    description: Optional[str] = None
    status: str
    members: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@router.post("", response_model=TeamResponse, status_code=status.HTTP_201_CREATED)
async def create_team(
    request: CreateTeamRequest,
    db: DatabaseManager = Depends(get_db_manager),
    coordinator: TeamCoordinator = Depends(get_team_coordinator)
):
    """Create a new temporary agent team."""
    # Validate manager agent exists
    manager = db.get_agent(request.manager_agent_id)
    if not manager:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Manager agent '{request.manager_agent_id}' not found"
        )

    # Validate members exist
    for aid in request.member_agent_ids:
        agent = db.get_agent(aid)
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Member agent '{aid}' not found"
            )

    try:
        team = coordinator.create_team(
            name=request.name,
            manager_agent_id=request.manager_agent_id,
            member_agent_ids=request.member_agent_ids,
            project_id=request.project_id,
            description=request.description
        )
        return TeamResponse(**team.to_dict())
    except Exception as e:
        logger.error(f"Failed to create team: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("", response_model=List[TeamResponse])
async def list_teams(
    project_id: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    db: DatabaseManager = Depends(get_db_manager)
):
    """List agent teams with optional filters."""
    teams = db.list_agent_teams(project_id=project_id, status=status_filter)
    return [TeamResponse(**t.to_dict()) for t in teams]


@router.get("/{team_id}", response_model=TeamResponse)
async def get_team(
    team_id: str,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Get details of a specific agent team."""
    team = db.get_agent_team(team_id)
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Team '{team_id}' not found"
        )
    return TeamResponse(**team.to_dict())


@router.post("/{team_id}/dispatch", status_code=status.HTTP_200_OK)
async def dispatch_team(
    team_id: str,
    request: DispatchTeamRequest,
    coordinator: TeamCoordinator = Depends(get_team_coordinator)
):
    """Dispatch parallel tasks to all members of the team."""
    try:
        result = coordinator.dispatch_team_task(
            team_id=team_id,
            shared_goal=request.shared_goal,
            member_prompts=request.member_prompts,
            parent_task_id=request.parent_task_id
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to dispatch team task: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/{team_id}/synthesize", status_code=status.HTTP_200_OK)
async def synthesize_team(
    team_id: str,
    request: SynthesizeTeamRequest,
    coordinator: TeamCoordinator = Depends(get_team_coordinator)
):
    """Synthesize results from completed team subtasks into an executive summary."""
    try:
        result = coordinator.synthesize_team_results(
            team_id=team_id,
            task_ids=request.task_ids
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to synthesize team results: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
