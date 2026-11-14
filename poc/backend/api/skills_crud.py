"""Organization-scoped custom skill CRUD."""
import sqlite3
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status

from ..dependencies import get_db_manager, Skill
from ..security.catalog_ownership import tenant_identifier
from ..security.resource_access import Resources
from .skills_models import SkillCreate, SkillResponse, SkillUpdate
from .skills_metadata import skill_to_response

router = APIRouter()


def _actor(request):
    actor = request.state.access_actor
    if not actor.organization_id:
        raise HTTPException(403, "An organization scope is required.")
    return actor


def _editable_skill(request, skill_id):
    actor = _actor(request)
    actor.require(level=4)
    skill = Resources(actor).require("skill", skill_id)
    if skill.is_system:
        raise HTTPException(403, "System skills are read-only.")
    return skill


@router.get("/", response_model=List[SkillResponse])
async def list_skills(request: Request, project_id: Optional[str] = None, db_manager=Depends(get_db_manager)):
    actor = _actor(request)
    resources = Resources(actor)
    if project_id:
        resources.require("project", project_id)
    return [skill_to_response(skill) for skill in
            db_manager.list_skills(project_id=project_id, organization_id=actor.organization_id)
            if resources.allows("skill", skill.id)]


@router.post("/", response_model=SkillResponse, status_code=status.HTTP_201_CREATED)
async def create_skill(skill_data: SkillCreate, request: Request, db_manager=Depends(get_db_manager)):
    actor = _actor(request)
    if skill_data.project_id:
        Resources(actor).require("project", skill_data.project_id, level=4)
    skill = Skill(id=tenant_identifier(actor, skill_data.name), organization_id=actor.organization_id,
                  **skill_data.model_dump())
    try:
        db_manager.save_skill(skill, create_only=True)
    except sqlite3.IntegrityError as exc:
        raise HTTPException(409, "The skill could not be created in this scope.") from exc
    return skill_to_response(skill)


@router.get("/{skill_id}", response_model=SkillResponse)
async def get_skill(skill_id: str, request: Request):
    return skill_to_response(Resources(_actor(request)).require("skill", skill_id))


@router.put("/{skill_id}", response_model=SkillResponse)
async def update_skill(skill_id: str, skill_data: SkillUpdate, request: Request, db_manager=Depends(get_db_manager)):
    skill = _editable_skill(request, skill_id)
    values = skill_data.model_dump(exclude_unset=True)
    if values.get("project_id"):
        Resources(_actor(request)).require("project", values["project_id"], level=4)
    if any(field in values and values[field] is None for field in ("name", "content")):
        raise HTTPException(422, "Skill name and content must have values.")
    for field, value in values.items():
        setattr(skill, field, value)
    if not db_manager.update_skill(skill):
        raise HTTPException(404, "Skill not found in the authorized scope.")
    return skill_to_response(skill)


@router.delete("/{skill_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_skill(skill_id: str, request: Request, db_manager=Depends(get_db_manager)):
    skill = _editable_skill(request, skill_id)
    if not db_manager.delete_skill(skill_id, organization_id=skill.organization_id):
        raise HTTPException(404, "Skill not found in the authorized scope.")
