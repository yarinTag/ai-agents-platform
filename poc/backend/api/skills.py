"""
Skill management API endpoints.
"""

from fastapi import APIRouter, HTTPException, Depends, status, Request, Query
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

import os
import re
import json
import subprocess
from pathlib import Path
import httpx

# All PoC imports go through the centralized dependencies module
from ..dependencies import get_config_manager, get_db_manager, Skill
from ..security import get_authorized_scope
from skills_service import get_skills_search_roots


router = APIRouter()


class PluginsConfigRequest(BaseModel):
    source_mode: Optional[str] = "local"
    git_repo: Optional[str] = None
    local_path: Optional[str] = None


# Pydantic models for request/response
class SkillBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    content: str = Field(..., min_length=1)
    project_id: Optional[str] = None  # None for global skills
    source: Optional[str] = "custom"  # "builtin", "local", "git", "custom"
    location: Optional[str] = None    # Repository URL or filesystem path


class SkillCreate(SkillBase):
    pass


class SkillUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    content: Optional[str] = Field(None, min_length=1)
    project_id: Optional[str] = None
    source: Optional[str] = None
    location: Optional[str] = None


class SkillResponse(SkillBase):
    id: str
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


# Helper function to convert Skill to response dict
def skill_to_response(skill: Skill) -> dict:
    return {
        "id": skill.id,
        "name": skill.name,
        "description": skill.description,
        "content": skill.content,
        "project_id": skill.project_id,
        "source": getattr(skill, "source", "custom") or "custom",
        "location": getattr(skill, "location", None),
        "created_at": "",  # Would come from DB in real implementation
        "updated_at": ""   # Would come from DB in real implementation
    }


@router.get("/", response_model=List[SkillResponse])
async def list_skills(
    project_id: Optional[str] = None,
    config_manager = Depends(get_config_manager),
    db_manager = Depends(get_db_manager)
):
    """List skills, optionally filtered by project."""
    skills = db_manager.list_skills(project_id=project_id)
    return [skill_to_response(skill) for skill in skills]


@router.post("/", response_model=SkillResponse, status_code=status.HTTP_201_CREATED)
async def create_skill(
    skill_data: SkillCreate,
    config_manager = Depends(get_config_manager),
    db_manager = Depends(get_db_manager)
):
    """Create a new skill."""
    # Generate ID from name
    skill_id = skill_data.name.lower().replace(" ", "-").replace("_", "-")

    # Check if already exists (global or in project)
    existing = db_manager.get_skill(skill_id)
    if existing:
        # Check if it's the same project context
        if (existing.project_id == skill_data.project_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Skill with ID '{skill_id}' already exists in this context"
            )

    # Create skill
    skill = Skill(
        id=skill_id,
        **skill_data.model_dump()
    )

    # Save to both config manager (as file) and database
    config_manager.save_skill(skill)
    db_manager.save_skill(skill)

    return skill_to_response(skill)


def _get_or_create_effective_org(request: Request, db_manager) -> Any:
    """Resolve current organization, falling back to existing org or creating default org."""
    scope = get_authorized_scope(request, db_manager)
    org_id = scope.get("org_id")
    org = db_manager.get_organization(org_id) if org_id else None

    if not org:
        all_orgs = db_manager.list_organizations()
        if all_orgs:
            org = all_orgs[0]
        else:
            org = db_manager.create_organization(
                id="org_default",
                name="Default Organization",
                slug="default-org",
                domain=None,
                settings_json="{}",
                plugins_source_mode="local"
            )
    return org


def _find_git_token(db_manager, org_id: Optional[str] = None) -> tuple[Optional[str], str]:
    """Search for a GitHub or GitLab token in installed MCP connectors, with gh cli fallback for GitHub."""
    connector_token = None
    connector_provider = "github"
    connectors = []
    if org_id:
        connectors = db_manager.list_mcp_connectors(organization_id=org_id)
    if not connectors:
        connectors = db_manager.list_mcp_connectors()

    for conn in connectors:
        prov = conn.provider.lower()
        if prov in ("github", "gitlab", "git"):
            cfg = conn.configuration or {}
            for k in ("token", "personal_access_token", "GITHUB_PERSONAL_ACCESS_TOKEN", "api_key", "password"):
                val = cfg.get(k)
                if val and isinstance(val, str) and len(val.strip()) > 5:
                    connector_token = val.strip()
                    connector_provider = "gitlab" if (prov == "gitlab" or connector_token.startswith("glpat-")) else "github"
                    break
            if connector_token:
                break

    # Check gh CLI auth token
    gh_token = None
    try:
        import subprocess
        import httpx
        gh_res = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, timeout=3)
        if gh_res.returncode == 0 and gh_res.stdout.strip():
            gh_token = gh_res.stdout.strip()
    except Exception:
        pass

    if gh_token:
        if not connector_token or connector_provider == "gitlab":
            return gh_token, "github"
        
        # If we have a connector token (e.g. github_pat_), check if it matches gh_token owner
        if connector_token.startswith("github_pat_") or connector_token.startswith("ghp_"):
            try:
                import httpx
                # We can check login via synchronous request or just use gh_token if both are valid and belong to same user
                # To be robust, let's verify logins match
                r1 = httpx.get("https://api.github.com/user", headers={"Authorization": f"Bearer {connector_token}", "Accept": "application/vnd.github+json", "User-Agent": "AI-Agents-Platform"}, timeout=3.0)
                r2 = httpx.get("https://api.github.com/user", headers={"Authorization": f"Bearer {gh_token}", "Accept": "application/vnd.github+json", "User-Agent": "AI-Agents-Platform"}, timeout=3.0)
                if r1.status_code == 200 and r2.status_code == 200:
                    l1 = r1.json().get("login")
                    l2 = r2.json().get("login")
                    if l1 and l2 and l1.lower() == l2.lower():
                        return gh_token, "github"
            except Exception:
                pass

    if connector_token:
        return connector_token, connector_provider

    return None, "github"


def _format_authenticated_git_url(raw_url: str, token: Optional[str] = None) -> str:
    """Format git repository URL, expanding shorthand and injecting token for authentication."""
    repo_url = raw_url.strip()
    # Check shorthand owner/repo e.g. "octocat/Hello-World"
    if re.match(r'^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$', repo_url):
        repo_url = f"https://github.com/{repo_url}.git"

    if not token:
        return repo_url

    # For GitHub URLs
    if "github.com" in repo_url:
        if "@github.com" not in repo_url:
            repo_url = re.sub(r'^https?://github\.com/', f'https://x-access-token:{token}@github.com/', repo_url)
    # For GitLab URLs
    elif "gitlab.com" in repo_url:
        if "@gitlab.com" not in repo_url:
            repo_url = re.sub(r'^https?://gitlab\.com/', f'https://oauth2:{token}@gitlab.com/', repo_url)

    return repo_url


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
    except Exception:
        pass

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
        "content_preview": content[:1500] if content else "",
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


_GIT_TREE_SCAN_CACHE: Dict[tuple, List[Dict[str, Any]]] = {}


def _parse_github_owner_repo(raw_url: str) -> Optional[tuple[str, str]]:
    clean = raw_url.strip().rstrip("/")
    m = re.search(r"github\.com[:/]([^/]+)/([^/]+?)(?:\.git)?$", clean)
    if m:
        return m.group(1), m.group(2)
    m_short = re.match(r"^([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_.-]+?)(?:\.git)?$", clean)
    if m_short:
        return m_short.group(1), m_short.group(2)
    return None


async def _scan_git_repo_via_api(repo_url: str, token: Optional[str], force_refresh: bool = False) -> tuple[List[Dict[str, Any]], Optional[str]]:
    """Scan a GitHub repository directly via REST API in-memory without cloning to disk."""
    import asyncio

    parsed = _parse_github_owner_repo(repo_url)
    if not parsed:
        return [], None
    owner, repo = parsed

    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "AI-Agents-Platform"
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    async with httpx.AsyncClient(timeout=20.0) as client:
        tree_resp = await client.get(
            f"https://api.github.com/repos/{owner}/{repo}/git/trees/HEAD?recursive=1",
            headers=headers
        )
        if tree_resp.status_code != 200:
            return [], f"github://{owner}/{repo}"

        tree_json = tree_resp.json()
        tree_sha = tree_json.get("sha") or "HEAD"
        cache_key = (owner.lower(), repo.lower(), tree_sha)
        if not force_refresh and cache_key in _GIT_TREE_SCAN_CACHE:
            return _GIT_TREE_SCAN_CACHE[cache_key], f"https://github.com/{owner}/{repo}"

        blobs = [
            item["path"]
            for item in tree_json.get("tree", [])
            if item.get("type") == "blob" and isinstance(item.get("path"), str)
        ]
        blob_set = set(blobs)

        sem = asyncio.Semaphore(15)
        raw_headers = dict(headers)
        raw_headers["Accept"] = "application/vnd.github.raw+json"

        async def fetch_raw(blob_path: str) -> str:
            async with sem:
                try:
                    r = await client.get(
                        f"https://api.github.com/repos/{owner}/{repo}/contents/{blob_path}",
                        headers=raw_headers
                    )
                    if r.status_code == 200:
                        return r.text
                except Exception:
                    pass
                return ""

        plugins_map: Dict[str, Dict[str, Any]] = {}

        mp_path = None
        mp_prefix = ""
        if "skills-marketplace/marketplace.json" in blob_set:
            mp_path = "skills-marketplace/marketplace.json"
            mp_prefix = "skills-marketplace/"
        elif "marketplace.json" in blob_set:
            mp_path = "marketplace.json"
            mp_prefix = ""

        if mp_path:
            mp_raw = await fetch_raw(mp_path)
            try:
                mp_data = json.loads(mp_raw)
            except Exception:
                mp_data = {}

            tasks_to_fetch = []
            for p_meta in mp_data.get("plugins", []):
                p_id = p_meta.get("id")
                if not p_id:
                    continue
                rel_p_dir = p_meta.get("path", f"plugins/{p_id}").strip("/")
                full_p_dir = f"{mp_prefix}{rel_p_dir}".strip("/")
                if p_id not in plugins_map:
                    plugins_map[p_id] = {
                        "name": p_id,
                        "display_name": p_id.replace("-", " ").replace("_", " ").title(),
                        "version": p_meta.get("version", "1.0.0"),
                        "description": p_meta.get("description", ""),
                        "domain": p_meta.get("domain", ""),
                        "path": f"github://{owner}/{repo}/{full_p_dir}",
                        "skills": []
                    }

                prefix_with_slash = f"{full_p_dir}/"
                for b_path in sorted(blobs):
                    if not b_path.startswith(prefix_with_slash) or not b_path.lower().endswith(".md"):
                        continue
                    parts = b_path.split("/")
                    parts_lower = [pt.lower() for pt in parts]
                    if any(ign in parts_lower for ign in ("references", "assets", "examples", "docs")):
                        continue
                    fname = parts[-1]
                    if fname.lower() in ("changelog.md", "versioning.md", "claude.md", "taxonomy.md", "readme.md", "agents.md"):
                        continue
                    parent_folder = parts[-2] if len(parts) >= 2 else p_id
                    if fname.lower() != "skill.md" and parent_folder not in ("skills", p_id):
                        continue
                    tasks_to_fetch.append((p_id, p_meta, b_path, fname, parent_folder))

            contents = await asyncio.gather(*(fetch_raw(t[2]) for t in tasks_to_fetch))
            for (p_id, p_meta, b_path, fname, parent_folder), text in zip(tasks_to_fetch, contents):
                if not text:
                    continue
                v_path = f"github://{owner}/{repo}/{b_path}"
                meta = extract_skill_meta_from_text(
                    content=text,
                    virtual_path=v_path,
                    filename=fname,
                    parent_name=parent_folder,
                    default_plugin=p_id,
                    default_domain=p_meta.get("domain", ""),
                    default_version=p_meta.get("version", "1.0.0")
                )
                if not any(s["id"] == meta["id"] for s in plugins_map[p_id]["skills"]):
                    plugins_map[p_id]["skills"].append(meta)
        else:
            # Non-manifest Git repository: scan .md skill files
            md_blobs = []
            for b_path in sorted(blobs):
                if not b_path.lower().endswith(".md"):
                    continue
                parts = b_path.split("/")
                parts_lower = [pt.lower() for pt in parts]
                if any(ign in parts_lower for ign in ("references", "assets", "examples", "docs")):
                    continue
                fname = parts[-1]
                if fname.lower() in ("readme.md", "changelog.md", "versioning.md", "claude.md", "taxonomy.md", "agents.md"):
                    continue
                p_name = parts[0] if len(parts) > 1 else repo
                parent_folder = parts[-2] if len(parts) >= 2 else repo
                md_blobs.append((p_name, b_path, fname, parent_folder))

            contents = await asyncio.gather(*(fetch_raw(t[1]) for t in md_blobs))
            for (p_name, b_path, fname, parent_folder), text in zip(md_blobs, contents):
                if not text:
                    continue
                if p_name not in plugins_map:
                    plugins_map[p_name] = {
                        "name": p_name,
                        "display_name": p_name.replace("-", " ").replace("_", " ").title(),
                        "version": "1.0.0",
                        "description": f"Plugin package {p_name}",
                        "domain": "general",
                        "path": f"github://{owner}/{repo}/{p_name}",
                        "skills": []
                    }
                v_path = f"github://{owner}/{repo}/{b_path}"
                meta = extract_skill_meta_from_text(
                    content=text,
                    virtual_path=v_path,
                    filename=fname,
                    parent_name=parent_folder,
                    default_plugin=p_name
                )
                if not any(s["id"] == meta["id"] for s in plugins_map[p_name]["skills"]):
                    plugins_map[p_name]["skills"].append(meta)

        plugins_data = []
        for p_name, p_info in plugins_map.items():
            if p_info["skills"]:
                plugins_data.append({
                    "name": p_name,
                    "display_name": p_info.get("display_name", p_name),
                    "version": p_info.get("version", "1.0.0"),
                    "description": p_info.get("description", ""),
                    "domain": p_info.get("domain", ""),
                    "path": p_info["path"],
                    "skills_count": len(p_info["skills"]),
                    "skills": p_info["skills"]
                })

        _GIT_TREE_SCAN_CACHE[cache_key] = plugins_data
        return plugins_data, f"https://github.com/{owner}/{repo}"


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


@router.get("/plugins/scan")
async def scan_plugins(
    request: Request,
    source_mode: Optional[str] = Query(None),
    git_repo: Optional[str] = Query(None),
    local_path: Optional[str] = Query(None),
    refresh: bool = Query(False),
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

    potential_roots: List[Path] = []
    if effective_source_mode == "local" and effective_local_path:
        lp = Path(effective_local_path).expanduser().resolve()
        if lp.exists():
            if (lp / "skills-marketplace" / "marketplace.json").exists():
                potential_roots.append(lp / "skills-marketplace")
            else:
                potential_roots.append(lp)

    plugins_map: Dict[str, Dict[str, Any]] = {}
    primary_marketplace_root: Optional[str] = None

    # Iterate potential roots and discover plugins
    for p_root in potential_roots:
        if not p_root.exists():
            continue

        mp_file = p_root / "marketplace.json"
        if mp_file.exists():
            if not primary_marketplace_root:
                primary_marketplace_root = str(p_root)
            try:
                with open(mp_file, "r", encoding="utf-8") as f:
                    mp_data = json.load(f)
                for p_meta in mp_data.get("plugins", []):
                    p_id = p_meta.get("id")
                    if not p_id:
                        continue
                    p_dir = p_root / p_meta.get("path", f"plugins/{p_id}")
                    if not p_dir.exists():
                        continue

                    if p_id not in plugins_map:
                        plugins_map[p_id] = {
                            "name": p_id,
                            "display_name": p_id.replace("-", " ").replace("_", " ").title(),
                            "version": p_meta.get("version", "1.0.0"),
                            "description": p_meta.get("description", ""),
                            "domain": p_meta.get("domain", ""),
                            "path": str(p_dir),
                            "skills": []
                        }

                    # Scan for SKILL.md in this plugin
                    for f_path in sorted(p_dir.rglob("*.md")):
                        parts_lower = [part.lower() for part in f_path.parts]
                        if any(ignored in parts_lower for ignored in ["references", "assets", "examples", "docs"]):
                            continue
                        if f_path.name.lower() in ["changelog.md", "versioning.md", "claude.md", "taxonomy.md", "readme.md"]:
                            continue
                        if f_path.name.lower() != "skill.md" and f_path.parent.name not in ["skills", p_id]:
                            continue

                        meta = extract_skill_meta(
                            f_path,
                            default_plugin=p_id,
                            default_domain=p_meta.get("domain", ""),
                            default_version=p_meta.get("version", "1.0.0")
                        )
                        if not any(s["id"] == meta["id"] for s in plugins_map[p_id]["skills"]):
                            plugins_map[p_id]["skills"].append(meta)
                continue
            except Exception as e:
                print(f"Error parsing marketplace manifest {mp_file}: {e}")

        # Non-manifest directory:
        # Group each child folder containing .md files as its own plugin package,
        # and top-level .md files under p_root.name
        top_mds = [
            f for f in sorted(p_root.glob("*.md"))
            if f.is_file() and f.name.lower() not in ["readme.md", "changelog.md", "versioning.md", "claude.md", "taxonomy.md"]
        ]
        if top_mds:
            root_pkg = p_root.name
            if root_pkg not in plugins_map:
                plugins_map[root_pkg] = {
                    "name": root_pkg,
                    "display_name": root_pkg.replace("-", " ").replace("_", " ").title(),
                    "version": "1.0.0",
                    "description": f"Skills library from {root_pkg}",
                    "domain": "general",
                    "path": str(p_root),
                    "skills": []
                }
            for f in top_mds:
                meta = extract_skill_meta(f, default_plugin=root_pkg)
                if not any(s["id"] == meta["id"] for s in plugins_map[root_pkg]["skills"]):
                    plugins_map[root_pkg]["skills"].append(meta)

        for child in sorted(p_root.iterdir()):
            if not child.is_dir() or child.name.startswith((".", "__")):
                continue

            if child.name.lower() == "plugins":
                for sub in sorted(child.iterdir()):
                    if not sub.is_dir() or sub.name.startswith((".", "__")):
                        continue
                    p_name = sub.name
                    if p_name not in plugins_map:
                        plugins_map[p_name] = {
                            "name": p_name,
                            "display_name": p_name.replace("-", " ").replace("_", " ").title(),
                            "version": "1.0.0",
                            "description": f"Plugin package {p_name}",
                            "domain": "general",
                            "path": str(sub),
                            "skills": []
                        }
                    for f in sorted(sub.rglob("*.md")):
                        parts_lower = [part.lower() for part in f.parts]
                        if any(ignored in parts_lower for ignored in ["references", "assets", "examples", "docs"]):
                            continue
                        if f.name.lower() in ["readme.md", "changelog.md", "versioning.md", "claude.md", "taxonomy.md"]:
                            continue
                        meta = extract_skill_meta(f, default_plugin=p_name)
                        if not any(s["id"] == meta["id"] for s in plugins_map[p_name]["skills"]):
                            plugins_map[p_name]["skills"].append(meta)
            else:
                child_mds = [
                    f for f in sorted(child.rglob("*.md"))
                    if f.is_file()
                    and f.name.lower() not in ["readme.md", "changelog.md", "versioning.md", "claude.md", "taxonomy.md"]
                    and not any(ignored in [part.lower() for part in f.parts] for ignored in ["references", "assets", "examples", "docs"])
                ]
                if child_mds:
                    p_name = child.name
                    if p_name not in plugins_map:
                        plugins_map[p_name] = {
                            "name": p_name,
                            "display_name": p_name.replace("-", " ").replace("_", " ").title(),
                            "version": "1.0.0",
                            "description": f"Plugin package {p_name}",
                            "domain": "general",
                            "path": str(child),
                            "skills": []
                        }
                    for f in child_mds:
                        meta = extract_skill_meta(f, default_plugin=p_name)
                        if not any(s["id"] == meta["id"] for s in plugins_map[p_name]["skills"]):
                            plugins_map[p_name]["skills"].append(meta)

    plugins_data = []
    for p_name, p_info in plugins_map.items():
        if p_info["skills"]:
            plugins_data.append({
                "name": p_name,
                "display_name": p_info.get("display_name", p_name),
                "version": p_info.get("version", "1.0.0"),
                "description": p_info.get("description", ""),
                "domain": p_info.get("domain", ""),
                "path": p_info["path"],
                "skills_count": len(p_info["skills"]),
                "skills": p_info["skills"]
            })

    return {
        "status": "success",
        "source_mode": effective_source_mode,
        "git_repo": effective_git_repo,
        "local_path": effective_local_path,
        "marketplace_path": primary_marketplace_root or (str(potential_roots[0]) if potential_roots else None),
        "plugins": plugins_data,
        "total_skills": sum(p["skills_count"] for p in plugins_data)
    }


@router.get("/plugins/content")
async def get_plugin_skill_content(
    path: str,
    request: Request,
    db_manager = Depends(get_db_manager)
):
    """Retrieve the full markdown instructions of a discovered skill (from memory cache, GitHub API, or local file)."""
    from skills_service import _SKILL_CACHE

    if path in _SKILL_CACHE and _SKILL_CACHE[path].get("content"):
        return {"path": path, "content": _SKILL_CACHE[path]["content"]}

    if path.startswith("github://"):
        rem = path[len("github://"):]
        parts = rem.split("/", 2)
        if len(parts) == 3:
            owner, repo, blob_path = parts
            org = _get_or_create_effective_org(request, db_manager)
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

    f_path = Path(path)
    if not f_path.exists() or not f_path.is_file() or f_path.suffix.lower() != ".md":
        raise HTTPException(status_code=404, detail="Skill file not found")
    try:
        content = f_path.read_text(encoding="utf-8")
        return {"path": str(f_path), "content": content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read skill: {str(e)}")


@router.get("/{skill_id}", response_model=SkillResponse)
async def get_skill(
    skill_id: str,
    db_manager = Depends(get_db_manager)
):
    """Get a specific skill by ID."""
    skill = db_manager.get_skill(skill_id)
    if not skill:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Skill not found: {skill_id}"
        )
    return skill_to_response(skill)


@router.put("/{skill_id}", response_model=SkillResponse)
async def update_skill(
    skill_id: str,
    skill_data: SkillUpdate,
    config_manager = Depends(get_config_manager),
    db_manager = Depends(get_db_manager)
):
    """Update an existing skill."""
    # Get existing skill
    existing = db_manager.get_skill(skill_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Skill not found: {skill_id}"
        )

    # Update fields that were provided
    update_data = skill_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(existing, field, value)

    # Save updates
    config_manager.save_skill(existing)  # Updates the file
    db_manager.save_skill(existing)      # Updates the DB

    return skill_to_response(existing)


@router.delete("/{skill_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_skill(
    skill_id: str,
    config_manager = Depends(get_config_manager),
    db_manager = Depends(get_db_manager)
):
    """Delete a skill."""
    # Check if exists
    existing = db_manager.get_skill(skill_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Skill not found: {skill_id}"
        )

    # Delete from both stores
    skill_file = config_manager.skills_dir / f"{skill_id}.md"
    if skill_file.exists():
        skill_file.unlink()
    db_manager.delete_skill(skill_id)

    return None