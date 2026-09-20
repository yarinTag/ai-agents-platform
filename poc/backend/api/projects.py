"""
Project management API endpoints.
"""

from fastapi import APIRouter, HTTPException, Depends, status
from typing import List, Optional
from pydantic import BaseModel, Field

# All PoC imports go through the centralized dependencies module
from ..dependencies import get_config_manager, get_db_manager, ProjectConfig


router = APIRouter()


# Pydantic models for request/response
class ProjectBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    working_directory: str = Field(..., min_length=1)
    instructions: Optional[str] = None
    skills: List[str] = Field(default_factory=list)
    allowed_tools: List[str] = Field(default=["read", "grep", "glob"])


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    working_directory: Optional[str] = Field(None, min_length=1)
    instructions: Optional[str] = None
    skills: Optional[List[str]] = None
    allowed_tools: Optional[List[str]] = None


class ProjectResponse(ProjectBase):
    id: str
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


# Helper function to convert ProjectConfig to response dict
def project_to_response(project: ProjectConfig) -> dict:
    return {
        "id": project.id,
        "name": project.name,
        "description": project.description,
        "working_directory": project.working_directory,
        "instructions": project.instructions,
        "skills": project.skills,
        "allowed_tools": project.allowed_tools,
        "created_at": "",  # Would come from DB in real implementation
        "updated_at": ""   # Would come from DB in real implementation
    }


@router.get("/", response_model=List[ProjectResponse])
async def list_projects(config_manager = Depends(get_config_manager)):
    """List all registered projects."""
    projects = config_manager.list_projects()
    return [project_to_response(project) for project in projects]


@router.post("/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_data: ProjectCreate,
    config_manager = Depends(get_config_manager),
    db_manager = Depends(get_db_manager)
):
    """Create a new project."""
    # Generate ID from name
    project_id = project_data.name.lower().replace(" ", "-").replace("_", "-")

    # Check if already exists
    existing = config_manager.get_project(project_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Project with ID '{project_id}' already exists"
        )

    # Create project config
    project_config = ProjectConfig(
        id=project_id,
        **project_data.model_dump()
    )

    # Register in both config manager and database
    config_manager.register_project(project_config)
    db_manager.save_project(project_config)

    return project_to_response(project_config)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    config_manager = Depends(get_config_manager)
):
    """Get a specific project by ID."""
    project = config_manager.get_project(project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project not found: {project_id}"
        )
    return project_to_response(project)


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    project_data: ProjectUpdate,
    config_manager = Depends(get_config_manager),
    db_manager = Depends(get_db_manager)
):
    """Update an existing project."""
    # Get existing project
    existing = config_manager.get_project(project_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project not found: {project_id}"
        )

    # Update fields that were provided
    update_data = project_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(existing, field, value)

    # Save updates
    config_manager.register_project(existing)  # This will update since same ID
    db_manager.save_project(existing)

    return project_to_response(existing)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: str,
    config_manager = Depends(get_config_manager),
    db_manager = Depends(get_db_manager)
):
    """Delete a project."""
    # Check if exists
    existing = config_manager.get_project(project_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project not found: {project_id}"
        )

    # Delete from both stores
    config_manager.projects.pop(project_id, None)
    config_manager.save_projects()
    db_manager.delete_project(project_id)

    return None