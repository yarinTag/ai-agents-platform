"""Skills: plugin settings ownership."""

from fastapi import Depends, Request, Query
from typing import Optional, Dict, Any
import subprocess
import httpx
from ..dependencies import get_db_manager
from .skills_models import PluginsConfigRequest
from .skills_credentials import _find_git_token, _get_or_create_effective_org
from fastapi import APIRouter

router = APIRouter()


@router.get("/plugins/config")
async def get_plugins_config(
    request: Request,
    db_manager = Depends(get_db_manager)
):
    """Get plugins configuration for the current organization."""
    org = _get_or_create_effective_org(request, db_manager)
    return {
        "source_mode": org.plugins_source_mode or "local",
        "git_repo": org.plugins_git_repo,
        "local_path": org.plugins_local_path
    }



@router.put("/plugins/config")
async def update_plugins_config(
    cfg: PluginsConfigRequest,
    request: Request,
    db_manager = Depends(get_db_manager)
):
    """Update plugins configuration for the current organization."""
    org = _get_or_create_effective_org(request, db_manager)
    raw = cfg.model_dump(exclude_unset=True)
    mode = (cfg.source_mode or org.plugins_source_mode or "local").lower()
    if mode not in ("local", "git"):
        mode = "local"

    update_kwargs: Dict[str, Any] = {"plugins_source_mode": mode}
    if "git_repo" in raw:
        update_kwargs["plugins_git_repo"] = (cfg.git_repo or "").strip()
    if "local_path" in raw:
        update_kwargs["plugins_local_path"] = (cfg.local_path or "").strip()

    updated_org = db_manager.update_organization(
        id=org.id,
        **update_kwargs
    ) or org

    return {
        "source_mode": updated_org.plugins_source_mode or "local",
        "git_repo": updated_org.plugins_git_repo or "",
        "local_path": updated_org.plugins_local_path or ""
    }



@router.get("/plugins/git-repos")
async def get_plugin_git_repos(
    request: Request,
    token: Optional[str] = Query(None),
    db_manager = Depends(get_db_manager)
):
    """Retrieve list of Git repositories accessible for plugin marketplace syncing."""
    org = _get_or_create_effective_org(request, db_manager)
    provider = "github"
    effective_token = token

    # Check database MCP connectors if token not provided
    if not effective_token:
        found_token, found_provider = _find_git_token(db_manager, org.id)
        if found_token:
            effective_token = found_token
            provider = found_provider
    elif effective_token.startswith("glpat-"):
        provider = "gitlab"

    if not effective_token:
        return {"repositories": [], "has_token": False, "provider": provider}

    if effective_token.startswith("glpat-") or provider == "gitlab":
        provider = "gitlab"
        headers = {"PRIVATE-TOKEN": effective_token, "User-Agent": "AI-Agents-Platform"}
        url = "https://gitlab.com/api/v4/projects?membership=true&per_page=100&order_by=updated_at"
    else:
        provider = "github"
        headers = {
            "Authorization": f"Bearer {effective_token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "AI-Agents-Platform"
        }
        url = "https://api.github.com/user/repos?per_page=100&sort=updated&affiliation=owner,collaborator,organization_member"

    import httpx
    token_warning = None
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code in (401, 403):
                return {"repositories": [], "has_token": True, "provider": provider, "error": "Invalid or unauthorized token"}
            resp.raise_for_status()
            data = resp.json()

        if provider == "github" and effective_token and effective_token.startswith("github_pat_") and data and not any(r.get("private") for r in data):
            import subprocess
            try:
                gh_res = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, timeout=3)
                if gh_res.returncode == 0 and gh_res.stdout.strip():
                    gh_token = gh_res.stdout.strip()
                    # Verify login matches
                    async with httpx.AsyncClient(timeout=5.0) as verify_client:
                        user_resp = await verify_client.get(
                            "https://api.github.com/user",
                            headers={
                                "Authorization": f"Bearer {effective_token}",
                                "Accept": "application/vnd.github+json",
                                "User-Agent": "AI-Agents-Platform"
                            }
                        )
                        gh_user_resp = await verify_client.get(
                            "https://api.github.com/user",
                            headers={
                                "Authorization": f"Bearer {gh_token}",
                                "Accept": "application/vnd.github+json",
                                "User-Agent": "AI-Agents-Platform"
                            }
                        )
                        if user_resp.status_code == 200 and gh_user_resp.status_code == 200:
                            login1 = user_resp.json().get("login")
                            login2 = gh_user_resp.json().get("login")
                            if login1 and login2 and login1.lower() == login2.lower():
                                async with httpx.AsyncClient(timeout=12.0) as gh_client:
                                    gh_repos_resp = await gh_client.get(
                                        url,
                                        headers={
                                            "Authorization": f"Bearer {gh_token}",
                                            "Accept": "application/vnd.github+json",
                                            "User-Agent": "AI-Agents-Platform"
                                        }
                                    )
                                    if gh_repos_resp.status_code == 200:
                                        data = gh_repos_resp.json()
            except Exception:
                pass

            if not any(r.get("private") for r in data):
                token_warning = "Fine-Grained token (github_pat_...) has 'Public Repositories only' set on GitHub. Enable 'All repositories' + 'Metadata/Contents: Read' on GitHub for direct private repo access."

        repos = []
        if provider == "gitlab":
            for p in data:
                repos.append({
                    "id": str(p.get("id") or p.get("path_with_namespace")),
                    "name": p.get("name"),
                    "full_name": p.get("path_with_namespace"),
                    "path": p.get("web_url"),
                    "clone_url": p.get("http_url_to_repo"),
                    "private": p.get("visibility") == "private",
                    "default_branch": p.get("default_branch", "main"),
                    "source": "gitlab"
                })
        else:
            for r in data:
                repos.append({
                    "id": str(r.get("id") or r.get("full_name")),
                    "name": r.get("name"),
                    "full_name": r.get("full_name"),
                    "path": r.get("html_url") or r.get("clone_url"),
                    "clone_url": r.get("clone_url"),
                    "private": bool(r.get("private", False)),
                    "default_branch": r.get("default_branch", "main"),
                    "source": "github"
                })

        res = {"repositories": repos, "has_token": True, "provider": provider}
        if token_warning:
            res["token_warning"] = token_warning
        return res
    except Exception as e:
        return {"repositories": [], "has_token": True, "provider": provider, "error": str(e)}

