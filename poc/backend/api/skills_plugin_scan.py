"""Skills: plugin scan ownership."""

from fastapi import HTTPException, Depends, Request, Query
from typing import List, Optional, Dict, Any
from pathlib import Path
import httpx
from ..dependencies import get_db_manager
from .skills_credentials import _find_git_token, _get_or_create_effective_org
from .skills_git_scanner import _scan_git_repo_via_api
from fastapi import APIRouter

router = APIRouter()


@router.get("/plugins/scan")
async def scan_plugins(
    request: Request,
    source_mode: Optional[str] = Query(None),
    git_repo: Optional[str] = Query(None),
    local_path: Optional[str] = Query(None),
    db_manager = Depends(get_db_manager)
):
    """Scan configured plugin repositories and local folders for available skills."""
    org = _get_or_create_effective_org(request, db_manager)

    # If query parameters are passed, persist them to the organization record
    update_kwargs = {}
    if source_mode is not None:
        sm = source_mode.lower()
        if sm in ("local", "git"):
            update_kwargs["plugins_source_mode"] = sm
    if git_repo is not None:
        update_kwargs["plugins_git_repo"] = git_repo.strip()
    if local_path is not None:
        update_kwargs["plugins_local_path"] = local_path.strip()

    if update_kwargs:
        org = db_manager.update_organization(id=org.id, **update_kwargs) or org

    effective_source_mode = org.plugins_source_mode or "local"
    effective_git_repo = (org.plugins_git_repo or "").strip()
    effective_local_path = (org.plugins_local_path or "").strip()

    if effective_source_mode == "git":
        if not effective_git_repo:
            return {
                "status": "success",
                "source_mode": "git",
                "git_repo": "",
                "local_path": effective_local_path,
                "marketplace_path": None,
                "plugins": [],
                "total_skills": 0
            }
        git_tok, _ = _find_git_token(db_manager, org.id)
        plugins_data, repo_display = await _scan_git_repo_via_api(effective_git_repo, git_tok)
        return {
            "status": "success",
            "source_mode": "git",
            "git_repo": effective_git_repo,
            "local_path": effective_local_path,
            "marketplace_path": repo_display or effective_git_repo,
            "plugins": plugins_data,
            "total_skills": sum(p["skills_count"] for p in plugins_data)
        }

    from plugins.local_scanner import scan_local_source
    return scan_local_source(effective_source_mode, effective_git_repo, effective_local_path)



@router.get("/plugins/content")
async def get_plugin_skill_content(
    path: str,
    request: Request,
    db_manager = Depends(get_db_manager)
):
    """Retrieve the full markdown instructions of a discovered skill (from memory cache, GitHub API, or local file)."""
    org = _get_or_create_effective_org(request, db_manager)

    if path.startswith("github://"):
        rem = path[len("github://"):]
        parts = rem.split("/", 2)
        if len(parts) == 3:
            owner, repo, blob_path = parts
            git_tok, _ = _find_git_token(db_manager, org.id)
            headers = {
                "Accept": "application/vnd.github.raw+json",
                "User-Agent": "AI-Agents-Platform"
            }
            if git_tok:
                headers["Authorization"] = f"Bearer {git_tok}"
            async with httpx.AsyncClient(timeout=15.0) as client:
                r = await client.get(
                    f"https://api.github.com/repos/{owner}/{repo}/contents/{blob_path}",
                    headers=headers
                )
                if r.status_code == 200:
                    return {"path": path, "content": r.text}
        raise HTTPException(status_code=404, detail="GitHub skill file not found")

    configured_root = (org.plugins_local_path or "").strip()
    if not configured_root:
        raise HTTPException(status_code=404, detail="Skill source is not configured")
    root = Path(configured_root).expanduser().resolve()
    f_path = Path(path).expanduser().resolve()
    if not f_path.is_relative_to(root):
        raise HTTPException(status_code=404, detail="Skill file not found")
    if not f_path.exists() or not f_path.is_file() or f_path.suffix.lower() != ".md":
        raise HTTPException(status_code=404, detail="Skill file not found")
    try:
        content = f_path.read_text(encoding="utf-8")
        return {"path": str(f_path), "content": content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read skill: {str(e)}")

