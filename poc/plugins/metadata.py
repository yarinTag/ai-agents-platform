"""Skills: metadata ownership."""

import re
from pathlib import Path


def extract_skill_meta_from_text(
    content: str,
    virtual_path: str,
    filename: str,
    parent_name: str,
    default_plugin: str,
    default_domain: str = "",
    default_version: str = "1.0.0"
) -> dict:
    from skills_service import _SKILL_CACHE

    stem = filename[:-3] if filename.lower().endswith(".md") else filename
    skill_id = parent_name if filename.lower() == "skill.md" else stem
    skill_name = skill_id.replace("-", " ").replace("_", " ").title()
    desc = ""
    plugin_name = default_plugin
    domain = default_domain
    version = default_version

    try:
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
            domain = m_domain.strip() if isinstance(m_domain, str) else m_domain.group(1).strip()

        m_ver = re.search(r"version:\s*[\"']?([^\s\"'\n\r]+)[\"']?", content)
        if m_ver:
            version = m_ver.group(1).strip()

        m_role = re.search(r"role:\s*[\"']?([^\s\"'\n\r]+)[\"']?", content)
        role = m_role.group(1).strip() if m_role else ""
    except Exception:
        role = ""

    final_desc = desc or f"Skill provided by {plugin_name}"
    cache_entry = {
        "id": skill_id,
        "name": skill_name,
        "description": final_desc,
        "content": content,
        "source": virtual_path
    }
    _SKILL_CACHE[skill_id] = cache_entry
    _SKILL_CACHE[virtual_path] = cache_entry

    return {
        "id": skill_id,
        "name": skill_name,
        "filename": filename,
        "path": virtual_path,
        "description": final_desc,
        "plugin": plugin_name,
        "domain": domain,
        "version": version,
        "role": role,
        "content_preview": content[:1500] if content else "",
        "_raw_content": content or "",
    }



def extract_skill_meta(file_path: Path, default_plugin: str, default_domain: str = "", default_version: str = "1.0.0") -> dict:
    content = ""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read(16384)
    except Exception:
        pass
    return extract_skill_meta_from_text(
        content=content,
        virtual_path=str(file_path),
        filename=file_path.name,
        parent_name=file_path.parent.name,
        default_plugin=default_plugin,
        default_domain=default_domain,
        default_version=default_version
    )




