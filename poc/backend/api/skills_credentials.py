"""Skills: credentials ownership."""

from fastapi import HTTPException, Request
from typing import Optional, Any
import re
import subprocess
import httpx
from ..security import get_authorized_scope


def _get_or_create_effective_org(request: Request, db_manager) -> Any:
    """Resolve current organization, falling back to existing org or creating default org."""
    scope = get_authorized_scope(request, db_manager)
    org_id = scope.get("org_id")
    org = db_manager.get_organization(org_id) if org_id else None

    if org_id and not org:
        raise HTTPException(status_code=404, detail="Organization not found")

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
    connectors = (
        db_manager.list_mcp_connectors(organization_id=org_id)
        if org_id else db_manager.list_mcp_connectors()
    )

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

    # An organization-scoped request may use only that tenant's credentials.
    # Host CLI credentials and unscoped connectors belong to legacy local mode.
    if org_id:
        return connector_token, connector_provider

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

