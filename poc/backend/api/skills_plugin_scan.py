"""Skills: plugin scan ownership."""

from fastapi import HTTPException, Depends, Request, Query
from typing import Optional
from pathlib import Path
import httpx
from ..dependencies import get_db_manager
from .skills_credentials import _get_or_create_effective_org
from .skills_git_scanner import _scan_git_repo_via_api
from fastapi import APIRouter
from plugins.source import resolve_source
from plugins.workflow_skills import github_token
from plugins.git_scanner import _parse_github_owner_repo
from urllib.parse import quote
from runtime.tenant_workspace import tenant_workspace

router = APIRouter()


@router.get("/plugins/scan")
async def scan_plugins(
    request: Request,
    refresh: bool = Query(False),
    department_id: Optional[str] = None,
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

    if department_id and update_kwargs:
        raise HTTPException(422, "Save department sources using PUT /plugins/settings before scanning.")
    if update_kwargs:
        org = db_manager.update_organization(id=org.id, **update_kwargs) or org

    source = resolve_source(db_manager, org.id, department_id)
    effective_source_mode = source.source_mode
    effective_git_repo = source.git_repo.strip()
    effective_local_path = source.local_path.strip()

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
        git_tok = github_token(db_manager, org.id)
        plugins_data, repo_display = await _scan_git_repo_via_api(effective_git_repo, git_tok, force_refresh=refresh)
        return {
            "status": "success",
            "source_mode": "git",
            "git_repo": effective_git_repo,
            "local_path": effective_local_path,
            "marketplace_path": repo_display or effective_git_repo,
            "plugins": plugins_data,
            "total_skills": sum(p["skills_count"] for p in plugins_data)
        }

    if effective_local_path:
        try:
            tenant_workspace(org.id, candidate=effective_local_path, shared=True)
        except ValueError as exc:
            raise HTTPException(403, "The local plugin source is outside tenant storage.") from exc
    from plugins.local_scanner import scan_local_source
    return scan_local_source(effective_source_mode, effective_git_repo, effective_local_path)



@router.get("/plugins/content")
async def get_plugin_skill_content(
    path: str,
    request: Request,
    department_id: Optional[str] = None,
    db_manager = Depends(get_db_manager)
):
    """Retrieve the full markdown instructions of a discovered skill (from memory cache, GitHub API, or local file)."""
    org = _get_or_create_effective_org(request, db_manager)

    source = resolve_source(db_manager, org.id, department_id)
    if path.startswith("github://"):
        parsed = _parse_github_owner_repo(source.git_repo)
        if (source.source_mode != "git" or not parsed
                or not path.startswith(f"github://{parsed[0]}/{parsed[1]}/")
                or any(part in (".", "..") for part in path.split("/"))):
            raise HTTPException(404, "Skill is outside the configured plugin source.")
        rem = path[len("github://"):]
        parts = rem.split("/", 2)
        if len(parts) == 3:
            owner, repo, blob_path = parts
            encoded_path = quote(blob_path, safe="/")
            git_tok = github_token(db_manager, org.id)
            headers = {
                "Accept": "application/vnd.github.raw+json",
                "User-Agent": "AI-Agents-Platform"
            }
            if git_tok:
                headers["Authorization"] = f"Bearer {git_tok}"
            async with httpx.AsyncClient(timeout=15.0) as client:
                r = await client.get(
                    f"https://api.github.com/repos/{owner}/{repo}/contents/{encoded_path}",
                    headers=headers
                )
                if r.status_code == 200:
                    return {"path": path, "content": r.text}
        raise HTTPException(status_code=404, detail="GitHub skill file not found")

    configured_root = source.local_path.strip() if source.source_mode == "local" else ""
    if not configured_root:
        raise HTTPException(status_code=404, detail="Skill source is not configured")
    try:
        tenant_workspace(org.id, candidate=configured_root, shared=True)
    except ValueError as exc:
        raise HTTPException(404, "Skill is outside tenant storage.") from exc
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

