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

            # Check if fine-grained token returns only public repos, and try gh cli token if so
            if (
                token 
                and token.startswith("github_pat_") 
                and raw_repos 
                and not any(r.get("private") for r in raw_repos)
            ):
                import subprocess
                gh_res = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, timeout=3)
                if gh_res.returncode == 0 and gh_res.stdout.strip():
                    gh_token = gh_res.stdout.strip()
                    # Verify login matches
                    user_resp = httpx.get(
                        "https://api.github.com/user",
                        headers={
                            "Authorization": f"Bearer {token}",
                            "Accept": "application/vnd.github+json",
                            "User-Agent": "AI-Agents-Platform"
                        },
                        timeout=5.0
                    )
                    gh_user_resp = httpx.get(
                        "https://api.github.com/user",
                        headers={
                            "Authorization": f"Bearer {gh_token}",
                            "Accept": "application/vnd.github+json",
                            "User-Agent": "AI-Agents-Platform"
                        },
                        timeout=5.0
                    )
                    if user_resp.status_code == 200 and gh_user_resp.status_code == 200:
                        login1 = user_resp.json().get("login")
                        login2 = gh_user_resp.json().get("login")
                        if login1 and login2 and login1.lower() == login2.lower():
                            # Fetch with gh_token
                            gh_repos_resp = httpx.get(
                                "https://api.github.com/user/repos?per_page=100&sort=updated&affiliation=owner,collaborator,organization_member",
                                headers={
                                    "Authorization": f"Bearer {gh_token}",
                                    "Accept": "application/vnd.github+json",
                                    "User-Agent": "AI-Agents-Platform"
                                },
                                timeout=15.0
                            )
                            if gh_repos_resp.status_code == 200:
                                raw_repos = gh_repos_resp.json()

                if not any(r.get("private") for r in raw_repos):
                    token_warning = "Fine-Grained token (github_pat_...) has 'Public Repositories only' set on GitHub. Enable 'All repositories' + 'Metadata/Contents: Read' on GitHub for direct private repo access."

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
        default_channels = [
            {"id": "#general", "name": "#general", "description": "General announcements & team feed"},
            {"id": "#dev-team", "name": "#dev-team", "description": "Engineering team channel"},
            {"id": "#alerts", "name": "#alerts", "description": "System alerts & automated agent notifications"},
            {"id": "#pr-review", "name": "#pr-review", "description": "Code review & pull request gates"},
            {"id": "#workflows-feed", "name": "#workflows-feed", "description": "Autonomous workflow execution logs"},
            {"id": "#deployments", "name": "#deployments", "description": "Release & CI/CD pipeline events"},
        ]
        configured_channels = []
        cfgs = []
        if req.configuration and isinstance(req.configuration, dict):
            cfgs.append(req.configuration)
        try:
            conns = db.list_mcp_connectors()
            for conn in conns:
                if conn.provider.lower() == "slack" and conn.configuration and isinstance(conn.configuration, dict):
                    cfgs.append(conn.configuration)
        except Exception:
            pass

        for cfg in cfgs:
            allowed = cfg.get("allowed_channels", [])
            if isinstance(allowed, str):
                allowed = [allowed]
            legacy = cfg.get("default_channel")
            candidates = list(allowed)
            if legacy and legacy not in candidates:
                candidates.append(legacy)
            for item in candidates:
                if isinstance(item, dict):
                    cid = str(item.get("id") or item.get("name") or "").strip()
                    cname = str(item.get("name") or cid).strip()
                    cdesc = item.get("description") or "Configured Slack channel"
                else:
                    cid = str(item).strip()
                    cname = cid
                    cdesc = f"Configured channel ({cid})"
                if cid:
                    configured_channels.append({"id": cid, "name": cname, "description": cdesc})

        seen_ids = set()
        channels = []
        for ch in configured_channels + default_channels:
            cid = ch.get("id")
            if cid and cid not in seen_ids:
                seen_ids.add(cid)
                channels.append(ch)

        return {"provider": "slack", "channels": channels}

    elif provider == "telegram":
        default_chats = [
            {"id": "@agents_office_alerts", "name": "Agents Office Alerts", "description": "Real-time critical platform notifications"},
            {"id": "@workflow_dev_channel", "name": "Dev Workflows Channel", "description": "Engineering pipeline trigger channel"},
            {"id": "@pr_review_bot", "name": "PR Review Bot", "description": "Interactive pull request gate approvals"},
        ]
        configured_chats = []
        cfgs = []
        if req.configuration and isinstance(req.configuration, dict):
            cfgs.append(req.configuration)
        try:
            conns = db.list_mcp_connectors()
            for conn in conns:
                if conn.provider.lower() == "telegram" and conn.configuration and isinstance(conn.configuration, dict):
                    cfgs.append(conn.configuration)
        except Exception:
            pass

        for cfg in cfgs:
            allowed = cfg.get("allowed_channels", [])
            if isinstance(allowed, str):
                allowed = [allowed]
            legacy = cfg.get("chat_id")
            candidates = list(allowed)
            if legacy and legacy not in candidates:
                candidates.append(legacy)
            for item in candidates:
                if isinstance(item, dict):
                    cid = str(item.get("id") or item.get("name") or "").strip()
                    cname = str(item.get("name") or cid).strip()
                    cdesc = item.get("description") or "Configured Telegram chat/channel"
                else:
                    cid = str(item).strip()
                    cname = cid
                    cdesc = f"Configured chat ({cid})"
                if cid:
                    configured_chats.append({"id": cid, "name": cname, "description": cdesc})

        seen_ids = set()
        chats = []
        for ch in configured_chats + default_chats:
            cid = ch.get("id")
            if cid and cid not in seen_ids:
                seen_ids.add(cid)
                chats.append(ch)

        return {"provider": "telegram", "chats": chats}

    return {"provider": provider, "items": []}

