"""
Skill management API endpoints.
"""

from fastapi import APIRouter, HTTPException, Depends, status
from typing import List, Optional
from pydantic import BaseModel, Field

# Import from parent directory (backend)
import sys
import os
import re
from pathlib import Path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dependencies import get_config_manager, get_db_manager
from config import Skill


router = APIRouter()


# Pydantic models for request/response
class SkillBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    content: str = Field(..., min_length=1)
    project_id: Optional[str] = None  # None for global skills


class SkillCreate(SkillBase):
    pass


class SkillUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    content: Optional[str] = Field(None, min_length=1)
    project_id: Optional[str] = None


class SkillResponse(SkillBase):
    id: str
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


# Helper function to convert Skill to response dict
def skill_to_response(skill: Skill) -> dict:
    return {
        "id": skill.id,
        "name": skill.name,
        "description": skill.description,
        "content": skill.content,
        "project_id": skill.project_id,
        "created_at": "",  # Would come from DB in real implementation
        "updated_at": ""   # Would come from DB in real implementation
    }


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
    config_manager = Depends(get_config_manager),
    db_manager = Depends(get_db_manager)
):
    """Create a new skill."""
    # Generate ID from name
    skill_id = skill_data.name.lower().replace(" ", "-").replace("_", "-")

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


@router.get("/plugins/scan")
async def scan_plugins():
    """Scan local plugin repositories (such as p-skills/marketplace and Projects/test) for available skills."""
    potential_roots = [
        os.path.expanduser(r"C:\Users\taguo\OneDrive\Desktop\Projects\p-skills\skills-marketplace\plugins"),
        os.path.expanduser(r"C:\Users\taguo\OneDrive\Desktop\Projects\test"),
        os.path.expanduser(r"C:\Users\taguo\Desktop\ai-agents-platform\poc\skills"),
    ]

    plugins_data = []

    for root_path in potential_roots:
        if not os.path.exists(root_path):
            continue

        p_root = Path(root_path)
        # If this is the plugins directory, iterate over each plugin folder
        if p_root.name == "plugins":
            for plugin_dir in p_root.iterdir():
                if plugin_dir.is_dir() and not plugin_dir.name.startswith("."):
                    plugin_skills = []
                    # Search specifically for SKILL.md files
                    for file_path in plugin_dir.rglob("*"):
                        if file_path.is_file() and file_path.name.lower() == "skill.md":
                            desc = ""
                            skill_id = file_path.parent.name
                            skill_name = skill_id.replace("-", " ").replace("_", " ").title()
                            try:
                                with open(file_path, "r", encoding="utf-8") as f:
                                    content = f.read(4096)
                                    m_name = re.search(r"^name:\s*[\"']?([^\"'\n\r]+)[\"']?", content, re.MULTILINE)
                                    if m_name:
                                        skill_name = m_name.group(1).strip().replace("-", " ").replace("_", " ").title()
                                    m_desc = re.search(r"^description:\s*[\"']?([^\"'\n\r]+)[\"']?", content, re.MULTILINE)
                                    if m_desc:
                                        desc = m_desc.group(1).strip()
                                    else:
                                        lines = [l.strip() for l in content.splitlines()[:10]]
                                        desc = " ".join([l for l in lines if l and not l.startswith(("#", "---"))])[:120]
                            except Exception:
                                pass
                            plugin_skills.append({
                                "id": f"{plugin_dir.name}-{skill_id}",
                                "name": skill_name,
                                "filename": file_path.name,
                                "path": str(file_path),
                                "description": desc or f"Skill provided by {plugin_dir.name} plugin",
                                "plugin": plugin_dir.name
                            })
                    plugins_data.append({
                        "name": plugin_dir.name,
                        "path": str(plugin_dir),
                        "skills_count": len(plugin_skills),
                        "skills": plugin_skills
                    })
        elif p_root.is_dir():
            # Project root with skills
            project_skills = []
            for file_path in p_root.rglob("*"):
                if file_path.is_file() and file_path.name.lower() == "skill.md":
                    desc = ""
                    skill_id = file_path.parent.name
                    skill_name = skill_id.replace("-", " ").replace("_", " ").title()
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            content = f.read(4096)
                            m_name = re.search(r"^name:\s*[\"']?([^\"'\n\r]+)[\"']?", content, re.MULTILINE)
                            if m_name:
                                skill_name = m_name.group(1).strip().replace("-", " ").replace("_", " ").title()
                            m_desc = re.search(r"^description:\s*[\"']?([^\"'\n\r]+)[\"']?", content, re.MULTILINE)
                            if m_desc:
                                desc = m_desc.group(1).strip()
                    except Exception:
                        pass
                    project_skills.append({
                        "id": f"{p_root.name}-{skill_id}",
                        "name": skill_name,
                        "filename": file_path.name,
                        "path": str(file_path),
                        "description": desc or f"Skill asset found in {p_root.name}",
                        "plugin": p_root.name
                    })
            if project_skills:
                plugins_data.append({
                    "name": p_root.name,
                    "path": str(p_root),
                    "skills_count": len(project_skills),
                    "skills": project_skills
                })

    return {
        "status": "success",
        "plugins": plugins_data,
        "total_skills": sum(p["skills_count"] for p in plugins_data)
    }