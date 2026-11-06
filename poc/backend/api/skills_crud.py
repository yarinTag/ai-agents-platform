"""Skills: crud ownership."""

from fastapi import HTTPException, Depends, status, Request
from typing import List, Optional
from ..dependencies import get_config_manager, get_db_manager, Skill
from .skills_models import SkillCreate, SkillResponse, SkillUpdate
from .skills_metadata import skill_to_response
from fastapi import APIRouter

router = APIRouter()


@router.get("/", response_model=List[SkillResponse])
async def list_skills(
    project_id: Optional[str] = None,
    config_manager = Depends(get_config_manager),
    db_manager = Depends(get_db_manager)
):
    """List skills, optionally filtered by project."""
    skills = db_manager.list_skills(project_id=project_id)
    return [skill_to_response(skill) for skill in skills]



@router.post("/", response_model=SkillResponse, status_code=status.HTTP_201_CREATED)
async def create_skill(
    skill_data: SkillCreate,
    request: Request,
    config_manager = Depends(get_config_manager),
    db_manager = Depends(get_db_manager)
):
    """Create a new skill."""
    # Generate ID from name
    from ..security.catalog_ownership import tenant_identifier, register_owner
    actor = request.state.access_actor
    skill_id = tenant_identifier(actor, skill_data.name)
    register_owner(db_manager, actor, "skill", skill_id)

    # Check if already exists (global or in project)
    existing = db_manager.get_skill(skill_id)
    if existing:
        # Check if it's the same project context
        if (existing.project_id == skill_data.project_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Skill with ID '{skill_id}' already exists in this context"
            )

    # Create skill
    skill = Skill(
        id=skill_id,
        **skill_data.model_dump()
    )

    # Save to both config manager (as file) and database
    config_manager.save_skill(skill)
    db_manager.save_skill(skill)

    return skill_to_response(skill)



@router.get("/{skill_id}", response_model=SkillResponse)
async def get_skill(
    skill_id: str,
    db_manager = Depends(get_db_manager)
):
    """Get a specific skill by ID."""
    skill = db_manager.get_skill(skill_id)
    if not skill:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Skill not found: {skill_id}"
        )
    return skill_to_response(skill)



@router.put("/{skill_id}", response_model=SkillResponse)
async def update_skill(
    skill_id: str,
    skill_data: SkillUpdate,
    config_manager = Depends(get_config_manager),
    db_manager = Depends(get_db_manager)
):
    """Update an existing skill."""
    # Get existing skill
    existing = db_manager.get_skill(skill_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Skill not found: {skill_id}"
        )

    # Update fields that were provided
    update_data = skill_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(existing, field, value)

    # Save updates
    config_manager.save_skill(existing)  # Updates the file
    db_manager.save_skill(existing)      # Updates the DB

    return skill_to_response(existing)



@router.delete("/{skill_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_skill(
    skill_id: str,
    config_manager = Depends(get_config_manager),
    db_manager = Depends(get_db_manager)
):
    """Delete a skill."""
    # Check if exists
    existing = db_manager.get_skill(skill_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Skill not found: {skill_id}"
        )

    # Delete from both stores
    skill_file = config_manager.skills_dir / f"{skill_id}.md"
    if skill_file.exists():
        skill_file.unlink()
    db_manager.delete_skill(skill_id)

    return None
