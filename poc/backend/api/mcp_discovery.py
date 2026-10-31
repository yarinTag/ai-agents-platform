"""Mcp: discovery ownership."""

from fastapi import HTTPException, Depends, Request
import httpx
from ..dependencies import get_db_manager, DatabaseManager
from ..security import get_current_org_id
from .mcp_models import ResourceDiscoveryRequest
from fastapi import APIRouter

router = APIRouter()


@router.post("/discover-resources")
def discover_resources(
    req: ResourceDiscoveryRequest,
    request: Request,
    db: DatabaseManager = Depends(get_db_manager)
):
    """
    Discover selectable resources for an integration:
    - GitHub: Repositories (real token-authenticated API query)
    - GitLab: Projects (real token-authenticated API query)
    - Local Git: Repositories from local folders
    - Slack: Channels
    - Telegram: Channels & Chats
    """
    provider = req.provider.lower()
    token = req.token
    if not token and req.configuration and isinstance(req.configuration, dict):
        token = req.configuration.get("token") or req.configuration.get("personal_access_token") or req.configuration.get("api_key")

    if token and ("..." in token or "****" in token):
        token = None

    org_id = get_current_org_id(request)
    if not token and org_id and provider in ("github", "gitlab", "git"):
        connectors = db.list_mcp_connectors(organization_id=org_id)
        for conn in connectors:
            c_prov = conn.provider.lower()
            if c_prov == provider or (provider in ("github", "git") and c_prov in ("github", "git")):
                cfg = conn.configuration or {}
                cand = cfg.get("token") or cfg.get("personal_access_token") or cfg.get("api_key")
                if cand and "..." not in cand and "****" not in cand:
                    token = cand
                    break

    # 1. GitHub (token provided or requested provider is github/git with token)
    is_github_token = bool(token and (token.startswith("ghp_") or token.startswith("github_pat_") or token.startswith("gho_")))
    if (provider in ("github", "git") and token) or is_github_token:
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "AI-Agents-Platform"
        }
        token_warning = None
        try:
            resp = httpx.get(
                "https://api.github.com/user/repos?per_page=100&sort=updated&affiliation=owner,collaborator,organization_member",
                headers=headers,
                timeout=15.0
            )
            if resp.status_code in (401, 403):
                raise HTTPException(
                    status_code=401,
                    detail="Invalid or unauthorized GitHub token. Could not fetch repositories."
                )
            resp.raise_for_status()
            raw_repos = resp.json()

            # For Fine-Grained PATs (github_pat_...), GitHub's /user/repos always includes all public
            # repositories alongside the explicitly selected repositories. Filter to explicitly scoped
            # repositories (private repos returned to the token, or public repos with granted permissions)
            # when present, and never override the user's token with host `gh auth token`.
            if token and token.startswith("github_pat_") and raw_repos:
                scoped_repos = [
                    r for r in raw_repos
                    if r.get("private") or any((r.get("permissions") or {}).get(p) for p in ("push", "maintain", "admin", "triage"))
                ]
                if scoped_repos:
                    raw_repos = scoped_repos
                else:
                    token_warning = (
                        "Fine-Grained token (github_pat_...) returned only read-only public repositories. "
                        "GitHub always exposes public repositories to fine-grained tokens; grant 'Contents: Read and write' "
                        "or include private repositories on GitHub to scope discovery strictly to selected repositories."
                    )

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=502,
                detail=f"Failed to communicate with GitHub API: {str(e)}"
            )

        repos = [
            {
                "id": str(repo.get("id") or repo.get("full_name")),
                "name": repo.get("name"),
                "full_name": repo.get("full_name"),
                "path": repo.get("html_url") or repo.get("clone_url"),
                "clone_url": repo.get("clone_url"),
                "private": bool(repo.get("private", False)),
                "default_branch": repo.get("default_branch", "main"),
                "owner": (repo.get("owner") or {}).get("login"),
                "permissions": repo.get("permissions") or {},
                "source": "github"
            }
            for repo in raw_repos
        ]
        result = {"provider": "github", "repositories": repos}
        if token_warning:
            result["token_warning"] = token_warning
        return result

    # 2. GitLab (token provided or requested provider is gitlab with token)
    is_gitlab_token = bool(token and token.startswith("glpat-"))
    if (provider == "gitlab" and token) or is_gitlab_token:
        headers = {
            "PRIVATE-TOKEN": token,
            "User-Agent": "AI-Agents-Platform"
        }
        try:
            resp = httpx.get(
                "https://gitlab.com/api/v4/projects?membership=true&per_page=100&order_by=updated_at",
                headers=headers,
                timeout=15.0
            )
            if resp.status_code == 401:
                raise HTTPException(
                    status_code=401,
                    detail="Invalid or unauthorized GitLab token."
                )
            resp.raise_for_status()
            raw_projects = resp.json()
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=502,
                detail=f"Failed to communicate with GitLab API: {str(e)}"
            )

        projects = [
            {
                "id": str(p.get("id") or p.get("path_with_namespace")),
                "name": p.get("name"),
                "full_name": p.get("path_with_namespace"),
                "path": p.get("web_url"),
                "clone_url": p.get("http_url_to_repo"),
                "private": p.get("visibility") == "private",
                "default_branch": p.get("default_branch", "main"),
                "source": "gitlab"
            }
            for p in raw_projects
        ]
        return {"provider": "gitlab", "repositories": projects}

    # 3. Provider is github or gitlab (or git without local mode) but NO token was provided
    if provider in ("github", "gitlab") or (provider == "git" and (req.configuration or {}).get("mode") != "local"):
        return {
            "provider": req.provider,
            "repositories": [],
            "requires_token": True,
            "message": "Please enter a valid Personal Access Token to view accessible repositories."
        }

    # 4. Local Git: provider == "local_git" or provider == "git" with mode == "local"
    if provider == "local_git" or (provider == "git" and (req.configuration or {}).get("mode") == "local"):
        repos = []
        projects_dir = "/Users/yarintag/Desktop/Projects"
        import os
        if os.path.exists(projects_dir):
            try:
                for entry in os.listdir(projects_dir):
                    full_p = os.path.join(projects_dir, entry)
                    if os.path.isdir(full_p) and os.path.exists(os.path.join(full_p, ".git")):
                        repos.append({
                            "id": f"local_{entry}",
                            "name": entry,
                            "full_name": f"local/{entry}",
                            "path": full_p,
                            "clone_url": full_p,
                            "private": True,
                            "default_branch": "main",
                            "is_local": True,
                            "source": "local"
                        })
            except Exception:
                pass
        return {"provider": "local_git", "repositories": repos}

    elif provider == "slack":
        from integrations.tool_definitions import resource_values, valid_channel
        claims = getattr(request.state, 'user', None) or {}
        user = db.get_user(claims.get('sub')) if claims else None
        if not user or user.status != 'ACTIVE' or user.role != 'ORG_ADMIN' or user.organization_id != org_id:
            raise HTTPException(403, 'An active organization administrator must inspect configured Slack channel IDs.')
        cfgs = [req.configuration] if isinstance(req.configuration, dict) else []
        connectors = db.list_mcp_connectors(organization_id=org_id)
        if req.connector_id:
            connector = next((c for c in connectors if c.id == req.connector_id and c.provider == 'slack'), None)
            if not connector:
                raise HTTPException(404, 'Slack connector not found in this organization.')
            cfgs.append(connector.configuration or {})
        else:
            cfgs.extend(c.configuration or {} for c in connectors if c.provider == 'slack' and c.organization_id == org_id)
        identifiers = sorted({v for cfg in cfgs for v in resource_values(cfg, 'channels') if valid_channel('slack', v)})
        return {'provider': 'slack', 'channels': [{'id': v, 'name': v, 'description': 'Configured channel ID; not live-discovered.'} for v in identifiers]}

    elif provider == "telegram":
        from .mcp_telegram_discovery import discover_telegram
        return discover_telegram(req, request, db)

    return {"provider": provider, "items": []}

