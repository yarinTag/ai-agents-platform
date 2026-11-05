"""Canonical discovered-plugin projection, independent of source transport."""

import re
from typing import Dict, List, Any


_PREFIXES = ("product-", "meta-", "tech-", "business-", "shared-")


def _strip_prefix(skill_id: str) -> str:
    for p in _PREFIXES:
        if skill_id.startswith(p) and len(skill_id) > len(p):
            return skill_id[len(p):]
    return skill_id


def _enrich_skill_connections(plugins_map: Dict[str, Dict[str, Any]]) -> None:
    """Resolve skill-to-skill references across discovered skills from SKILL.md content."""
    alias_to_id: Dict[str, str] = {}
    all_skills: List[Dict[str, Any]] = []

    for info in plugins_map.values():
        for sk in info.get("skills", []):
            sid = sk.get("id", "")
            if not sid:
                continue
            all_skills.append(sk)
            alias_to_id[sid.lower()] = sid
            short = _strip_prefix(sid.lower())
            if short and len(short) >= 5 and short not in alias_to_id:
                alias_to_id[short] = sid

    for sk in all_skills:
        sid = sk.get("id", "")
        raw = sk.pop("_raw_content", None) or sk.get("content_preview") or ""
        raw_lower = raw.lower()
        connected: List[str] = []

        for alias, target_id in alias_to_id.items():
            if target_id == sid:
                continue
            if re.search(rf"(?<![a-z0-9_-]){re.escape(alias)}(?![a-z0-9_-])", raw_lower):
                if target_id not in connected:
                    connected.append(target_id)

        sk["connected_skills"] = connected


def summarize_plugins(plugins_map):
    _enrich_skill_connections(plugins_map)
    return [{
        "name": name,
        "display_name": info.get("display_name", name),
        "version": info.get("version", "1.0.0"),
        "description": info.get("description", ""),
        "domain": info.get("domain", ""),
        "path": info["path"],
        "skills_count": len(info["skills"]),
        "skills": info["skills"],
    } for name, info in plugins_map.items() if info["skills"]]
