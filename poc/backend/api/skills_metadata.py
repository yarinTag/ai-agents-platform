"""Compatibility imports and API response mapping for skill metadata."""
from config import Skill
from plugins.metadata import extract_skill_meta, extract_skill_meta_from_text

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

