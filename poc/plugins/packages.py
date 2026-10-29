"""Canonical discovered-plugin projection, independent of source transport."""


def summarize_plugins(plugins_map):
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
