"""Canonical discovered-plugin projection, independent of source transport."""

from .connections import enrich_skill_connections

# Compatibility name retained for existing imports.
_enrich_skill_connections = enrich_skill_connections


def summarize_plugins(plugins_map, flow_documents=None):
    _enrich_skill_connections(plugins_map, flow_documents)
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
