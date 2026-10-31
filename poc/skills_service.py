"""
Skills Service: Resolves skill definitions from database, p-skills marketplace,
and filesystem, providing unified content resolution and prompt generation for agent runtimes.
"""

import os
import re
import logging
from pathlib import Path
from typing import List, Dict, Optional, Any

logger = logging.getLogger(__name__)

# Cache for resolved skills: skill_id -> {id, name, description, content, source}
_SKILL_CACHE: Dict[str, Dict[str, str]] = {}


def get_skills_search_roots() -> List[Path]:
    """
    Get all potential root directories where skills and plugin marketplaces may reside.
    Discovers p-skills marketplace, env variable overrides, and workspace paths.
    """
    roots: List[Path] = []

    # 1. Environment variable overrides
    for env_var in ["SKILLS_REPO_PATH", "MARKETPLACE_PATH"]:
        val = os.environ.get(env_var, "").strip()
        if val:
            p = Path(val)
            if p.exists() and p.resolve() not in roots:
                roots.append(p.resolve())

    scan_env = os.environ.get("SKILLS_SCAN_PATHS", "")
    if scan_env:
        for p_str in scan_env.split(";"):
            p_clean = p_str.strip()
            if p_clean:
                p = Path(p_clean)
                if p.exists() and p.resolve() not in roots:
                    roots.append(p.resolve())

    # 2. Check organization plugins_local_path configured in Database
    try:
        from persistence import db_manager
        for org in db_manager.list_organizations():
            local_p = getattr(org, "plugins_local_path", None)
            if local_p:
                lp = Path(local_p)
                if lp.exists():
                    if lp.resolve() not in roots:
                        roots.append(lp.resolve())
                    sub_mp = lp / "skills-marketplace"
                    if sub_mp.exists() and sub_mp.resolve() not in roots:
                        roots.append(sub_mp.resolve())
    except Exception:
        pass

    # 3. Dynamic discovery in user home directory (Desktop/Projects, Projects, etc.)
    home = Path.home()
    for cand in [
        home / "Desktop" / "Projects" / "t-skills" / "skills-marketplace",
        home / "Desktop" / "Projects" / "t-skills",
        home / "Desktop" / "Projects" / "p-skills" / "skills-marketplace",
        home / "Desktop" / "Projects" / "p-skills",
        home / "Projects" / "t-skills" / "skills-marketplace",
        home / "Projects" / "t-skills",
        home / "Projects" / "p-skills" / "skills-marketplace",
        home / "Projects" / "p-skills",
        home / "t-skills" / "skills-marketplace",
        home / "p-skills" / "skills-marketplace",
    ]:
        if cand.exists() and cand.resolve() not in roots:
            roots.append(cand.resolve())

    # Dynamically discover any skills-marketplace in Desktop/Projects or Projects
    for parent_dir in [home / "Desktop" / "Projects", home / "Projects"]:
        if parent_dir.exists() and parent_dir.is_dir():
            try:
                for child in parent_dir.iterdir():
                    if child.is_dir():
                        for sub_name in ["skills-marketplace", "plugins", "skills"]:
                            sub = child / sub_name
                            if sub.exists() and sub.resolve() not in roots:
                                roots.append(sub.resolve())
            except Exception:
                pass

    # 4. Workspace and relative locations
    poc_dir = Path(__file__).resolve().parent
    workspace_dir = poc_dir.parent

    for candidate in [
        workspace_dir.parent / "t-skills" / "skills-marketplace",
        workspace_dir.parent / "p-skills" / "skills-marketplace",
        poc_dir / "plugins",
        poc_dir / "config" / "skills",
        poc_dir / "skills",
        workspace_dir / "plugins",
        workspace_dir / "skills",
    ]:
        if candidate.exists() and candidate.resolve() not in roots:
            roots.append(candidate.resolve())

    return roots


def _parse_skill_file(file_path: Path) -> Dict[str, str]:
    """Extract metadata and full content from a SKILL.md file."""
    skill_id = file_path.parent.name if file_path.name.lower() == "skill.md" else file_path.stem
    content = ""
    skill_name = skill_id.replace("-", " ").replace("_", " ").title()
    desc = ""

    try:
        content = file_path.read_text(encoding="utf-8")
        # Try finding markdown title
        m_h1 = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        if m_h1:
            skill_name = m_h1.group(1).strip()

        # Try finding YAML frontmatter name
        m_name = re.search(r"^name:\s*[\"']?([^\"'\n\r]+)[\"']?", content, re.MULTILINE)
        if m_name and not m_h1:
            skill_name = m_name.group(1).strip().replace("-", " ").title()

        m_desc = re.search(r"^description:\s*[\"']?([^\"'\n\r]+)[\"']?", content, re.MULTILINE)
        if m_desc:
            desc = m_desc.group(1).strip()
    except Exception as e:
        logger.warning(f"Error reading skill file {file_path}: {e}")

    return {
        "id": skill_id,
        "name": skill_name,
        "description": desc,
        "content": content,
        "source": str(file_path)
    }


_UNSAFE_SKILL_CHARS = set("*?[]{}\\\0")


def _is_safe_skill_name(name: str) -> bool:
    """A glob-safe relative skill name such as 'review' or 'plugin/review'."""
    if not name or name.startswith(("/", "~")) or any(c in _UNSAFE_SKILL_CHARS for c in name):
        return False
    return all(part not in ("", ".", "..") for part in name.split("/"))


def _is_skill_file_in_roots(path: Path, roots: List[Path]) -> bool:
    """True when path resolves to an existing Markdown file inside one of roots."""
    try:
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError):
        return False
    if not resolved.is_file() or resolved.suffix.lower() != ".md":
        return False
    return any(resolved.is_relative_to(root.resolve()) for root in roots)


def resolve_skill(skill_id_or_path: str, use_cache: bool = True) -> Optional[Dict[str, str]]:
    """
    Resolve a skill by ID or file path from DB, p-skills marketplace, or filesystem.

    Returns:
        Dict with keys: id, name, description, content, source
        or None if not found.
    """
    if not skill_id_or_path:
        return None

    clean_id = skill_id_or_path.strip()

    if use_cache and clean_id in _SKILL_CACHE:
        return _SKILL_CACHE[clean_id]

    # 1. Direct file path check: only Markdown files inside a configured skill
    # root. A skill ID must never become an arbitrary host-file read.
    roots = get_skills_search_roots()
    direct_path = Path(clean_id)
    if direct_path.is_absolute() and _is_skill_file_in_roots(direct_path, roots):
        parsed = _parse_skill_file(direct_path.resolve())
        if parsed["content"]:
            _SKILL_CACHE[clean_id] = parsed
            return parsed

    # 2. Check Database custom skills
    try:
        from persistence import db_manager
        db_skill = db_manager.get_skill(clean_id)
        if db_skill and db_skill.content:
            res = {
                "id": db_skill.id,
                "name": db_skill.name,
                "description": db_skill.description or "",
                "content": db_skill.content,
                "source": "database"
            }
            _SKILL_CACHE[clean_id] = res
            return res
    except Exception as e:
        logger.debug(f"DB check for skill '{clean_id}' returned: {e}")

    # 3. Search marketplace roots. The ID is interpolated into a glob, so it
    # must be a plain relative name: no traversal, no absolute path, no wildcards.
    if not _is_safe_skill_name(clean_id):
        logger.warning("Rejected unsafe skill identifier")
        return None
    for root in roots:
        # Check standard skill directory: **/skills/{clean_id}/SKILL.md
        cand_files = list(root.glob(f"**/skills/{clean_id}/SKILL.md"))
        if not cand_files:
            cand_files = list(root.glob(f"**/{clean_id}/SKILL.md"))
        if not cand_files:
            cand_files = list(root.glob(f"**/{clean_id}.md"))

        for file_match in cand_files:
            # Re-check after symlink resolution so a link cannot escape the root.
            if file_match.is_file() and _is_skill_file_in_roots(file_match, [root]):
                parsed = _parse_skill_file(file_match.resolve())
                if parsed["content"]:
                    _SKILL_CACHE[clean_id] = parsed
                    return parsed

    logger.warning(f"Skill '{clean_id}' could not be resolved from DB or marketplace roots")
    return None


def build_skills_system_prompt(skill_ids: List[str]) -> str:
    """
    Build a comprehensive markdown prompt section containing the full instructions
    and methodologies for all equipped skills.
    """
    if not skill_ids:
        return ""

    resolved_skills = []
    for sid in skill_ids:
        resolved = resolve_skill(sid)
        if resolved:
            resolved_skills.append(resolved)

    if not resolved_skills:
        return ""

    parts = [
        "[EQUIPPED SKILLS & DOMAIN METHODOLOGIES]",
        "You are equipped with specialized domain skills and methodologies.",
        "You MUST strictly adhere to the guidelines, architectural patterns, and validation rules specified below:\n"
    ]

    for s in resolved_skills:
        parts.append("---")
        parts.append(f"### SKILL: {s['name']} (ID: {s['id']})")
        if s.get("description"):
            parts.append(f"> {s['description']}\n")
        parts.append(s["content"].strip())
        parts.append("\n")

    return "\n".join(parts)


def clear_skills_cache():
    """Clear in-memory resolved skills cache."""
    global _SKILL_CACHE
    _SKILL_CACHE.clear()
