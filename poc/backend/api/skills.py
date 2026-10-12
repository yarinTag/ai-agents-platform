"""
Skill management API endpoints.
"""

from fastapi import APIRouter, HTTPException, Depends, status
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

import os
import re
import json
from pathlib import Path

# All PoC imports go through the centralized dependencies module
from ..dependencies import get_config_manager, get_db_manager, Skill


router = APIRouter()


# Pydantic models for request/response
class SkillBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    content: str = Field(..., min_length=1)
    project_id: Optional[str] = None  # None for global skills
    source: Optional[str] = "custom"  # "builtin", "local", "git", "custom"
    location: Optional[str] = None    # Repository URL or filesystem path


class SkillCreate(SkillBase):
    pass


class SkillUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    content: Optional[str] = Field(None, min_length=1)
    project_id: Optional[str] = None
    source: Optional[str] = None
    location: Optional[str] = None


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
        "source": getattr(skill, "source", "custom") or "custom",
        "location": getattr(skill, "location", None),
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



from skills_service import get_skills_search_roots

@router.get("/plugins/scan")
async def scan_plugins():
    """Scan configured plugin repositories and local folders for available skills."""
    potential_roots = get_skills_search_roots()

    plugins_map: Dict[str, Dict[str, Any]] = {}
    primary_marketplace_root: Optional[str] = None

    def extract_skill_meta(file_path: Path, default_plugin: str, default_domain: str = "", default_version: str = "1.0.0") -> dict:
        skill_id = file_path.parent.name if file_path.name.lower() == "skill.md" else file_path.stem
        skill_name = skill_id.replace("-", " ").replace("_", " ").title()
        desc = ""
        plugin_name = default_plugin
        domain = default_domain
        version = default_version
        content = ""

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read(8192)

                m_h1 = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
                if m_h1:
                    skill_name = m_h1.group(1).strip()

                m_name = re.search(r"^name:\s*[\"']?([^\"'\n\r]+)[\"']?", content, re.MULTILINE)
                if m_name and not m_h1:
                    skill_name = m_name.group(1).strip().replace("-", " ").title()

                m_plugin = re.search(r"^plugin:\s*[\"']?([^\"'\n\r]+)[\"']?", content, re.MULTILINE)
                if m_plugin:
                    plugin_name = m_plugin.group(1).strip()

                m_desc = re.search(r"^description:\s*[\"']?([^\"'\n\r]+)[\"']?", content, re.MULTILINE)
                if m_desc:
                    desc = m_desc.group(1).strip()
                else:
                    lines = [l.strip() for l in content.splitlines()[:15]]
                    desc = " ".join([l for l in lines if l and not l.startswith(("#", "---"))])[:160]

                m_domain = re.search(r"domain:\s*[\"']?([^\s\"'\n\r]+)[\"']?", content)
                if m_domain:
                    domain = m_domain.group(1).strip()

                m_ver = re.search(r"version:\s*[\"']?([^\s\"'\n\r]+)[\"']?", content)
                if m_ver:
                    version = m_ver.group(1).strip()
        except Exception:
            pass

        return {
            "id": skill_id,
            "name": skill_name,
            "filename": file_path.name,
            "path": str(file_path),
            "description": desc or f"Skill provided by {plugin_name}",
            "plugin": plugin_name,
            "domain": domain,
            "version": version,
            "content_preview": content[:1500] if content else "",
        }

    # Iterate potential roots and discover plugins
    for p_root in potential_roots:
        if not p_root.exists():
            continue

        mp_file = p_root / "marketplace.json"
        if mp_file.exists():
            if not primary_marketplace_root:
                primary_marketplace_root = str(p_root)
            try:
                with open(mp_file, "r", encoding="utf-8") as f:
                    mp_data = json.load(f)
                for p_meta in mp_data.get("plugins", []):
                    p_id = p_meta.get("id")
                    if not p_id:
                        continue
                    p_dir = p_root / p_meta.get("path", f"plugins/{p_id}")
                    if not p_dir.exists():
                        continue

                    if p_id not in plugins_map:
                        plugins_map[p_id] = {
                            "name": p_id,
                            "display_name": p_id.replace("-", " ").replace("_", " ").title(),
                            "version": p_meta.get("version", "1.0.0"),
                            "description": p_meta.get("description", ""),
                            "domain": p_meta.get("domain", ""),
                            "path": str(p_dir),
                            "skills": []
                        }

                    # Scan for SKILL.md in this plugin
                    for f_path in sorted(p_dir.rglob("*.md")):
                        # Ignore references, assets, examples, changelogs
                        parts_lower = [part.lower() for part in f_path.parts]
                        if any(ignored in parts_lower for ignored in ["references", "assets", "examples", "docs"]):
                            continue
                        if f_path.name.lower() in ["changelog.md", "versioning.md", "claude.md", "taxonomy.md", "readme.md"]:
                            continue
                        if f_path.name.lower() != "skill.md" and f_path.parent.name not in ["skills", p_id]:
                            continue

                        meta = extract_skill_meta(
                            f_path,
                            default_plugin=p_id,
                            default_domain=p_meta.get("domain", ""),
                            default_version=p_meta.get("version", "1.0.0")
                        )
                        if not any(s["id"] == meta["id"] for s in plugins_map[p_id]["skills"]):
                            plugins_map[p_id]["skills"].append(meta)
                continue
            except Exception as e:
                print(f"Error parsing marketplace manifest {mp_file}: {e}")

        # Standard plugin directory (e.g. poc/plugins)
        if p_root.name == "plugins":
            for plugin_dir in p_root.iterdir():
                if plugin_dir.is_dir() and not plugin_dir.name.startswith("."):
                    p_name = plugin_dir.name
                    if p_name not in plugins_map:
                        plugins_map[p_name] = {
                            "name": p_name,
                            "display_name": p_name.replace("-", " ").replace("_", " ").title(),
                            "version": "1.0.0",
                            "description": f"Plugin package {p_name}",
                            "domain": "general",
                            "path": str(plugin_dir),
                            "skills": []
                        }
                    for f in plugin_dir.rglob("*.md"):
                        parts_lower = [part.lower() for part in f.parts]
                        if any(ignored in parts_lower for ignored in ["references", "assets", "examples"]):
                            continue
                        if f.name.lower() in ["changelog.md", "versioning.md", "claude.md", "readme.md"]:
                            continue
                        meta = extract_skill_meta(f, default_plugin=p_name)
                        if not any(s["id"] == meta["id"] for s in plugins_map[p_name]["skills"]):
                            plugins_map[p_name]["skills"].append(meta)
        else:
            # Standalone skills directory (e.g. config/skills)
            group_name = p_root.parent.name if p_root.name == "skills" else p_root.name
            if group_name not in plugins_map:
                plugins_map[group_name] = {
                    "name": group_name,
                    "display_name": group_name.replace("-", " ").replace("_", " ").title(),
                    "version": "1.0.0",
                    "description": f"Skills library from {group_name}",
                    "domain": "general",
                    "path": str(p_root),
                    "skills": []
                }
            for f in p_root.rglob("*.md"):
                if f.name.lower() in ["readme.md", "changelog.md"]:
                    continue
                meta = extract_skill_meta(f, default_plugin=group_name)
                if not any(s["id"] == meta["id"] for s in plugins_map[group_name]["skills"]):
                    plugins_map[group_name]["skills"].append(meta)

    plugins_data = []
    for p_name, p_info in plugins_map.items():
        if p_info["skills"]:
            plugins_data.append({
                "name": p_name,
                "display_name": p_info.get("display_name", p_name),
                "version": p_info.get("version", "1.0.0"),
                "description": p_info.get("description", ""),
                "domain": p_info.get("domain", ""),
                "path": p_info["path"],
                "skills_count": len(p_info["skills"]),
                "skills": p_info["skills"]
            })

    return {
        "status": "success",
        "marketplace_path": primary_marketplace_root or str(potential_roots[0]) if potential_roots else None,
        "plugins": plugins_data,
        "total_skills": sum(p["skills_count"] for p in plugins_data)
    }


@router.get("/plugins/content")
async def get_plugin_skill_content(path: str):
    """Retrieve the full markdown instructions of a discovered skill."""
    f_path = Path(path)
    if not f_path.exists() or not f_path.is_file() or f_path.suffix.lower() != ".md":
        raise HTTPException(status_code=404, detail="Skill file not found")
    try:
        content = f_path.read_text(encoding="utf-8")
        return {"path": str(f_path), "content": content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read skill: {str(e)}")