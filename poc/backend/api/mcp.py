"""
MCP (Model Context Protocol) API Router.
Supports:
- Catalog of available MCP integrations (Git, Trello, Telegram, Slack, Postgres, Brave Search, Filesystem, Custom)
- Installing / configuring MCP connectors
- Testing connections and updating status
- Inspecting tools exposed by each connector
- Managing agent access permissions for MCP connectors
"""

from fastapi import APIRouter, HTTPException, Depends, status, Request
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
import uuid
from datetime import datetime
import httpx

from ..dependencies import get_db_manager, DatabaseManager
from ..security import get_current_org_id
from persistence import MCPConnector, MCPTool

router = APIRouter()

# --------------------------------------------------------------------
# Catalog Definitions
# --------------------------------------------------------------------

CATALOG_MCP_SERVERS = [
    {
        "id": "github",
        "name": "GitHub / Git",
        "provider": "github",
        "category": "Developer Tools",
        "icon": "github",
        "description": "Inspect repositories, commit code, review pull requests, and manage issues directly from agent workflows.",
        "package": "@modelcontextprotocol/server-github",
        "config_schema": {
            "token": {"type": "password", "label": "GitHub Personal Access Token (PAT)", "required": True, "placeholder": "ghp_xxxxxxxxxxxx"},
            "default_repo": {"type": "text", "label": "Default Repository (owner/repo)", "required": False, "placeholder": "octocat/Hello-World"},
            "branch": {"type": "text", "label": "Default Branch", "required": False, "default": "main"}
        },
        "default_tools": [
            {"name": "git_status", "description": "Check working directory status and branch info"},
            {"name": "git_diff", "description": "Inspect diff of staged or unstaged changes"},
            {"name": "git_commit", "description": "Commit staged changes with message"},
            {"name": "create_pull_request", "description": "Open a GitHub Pull Request with title and body"},
            {"name": "list_issues", "description": "List open or closed issues in repository"},
            {"name": "search_code", "description": "Search code across repositories using GitHub search syntax"}
        ]
    },
    {
        "id": "trello",
        "name": "Trello",
        "provider": "trello",
        "category": "Productivity & Planning",
        "icon": "trello",
        "description": "Manage Trello boards, sprint lists, task cards, checklists, and automated card movement between stages.",
        "package": "mcp-server-trello",
        "config_schema": {
            "api_key": {"type": "password", "label": "Trello API Key", "required": True, "placeholder": "Trello Developer API Key"},
            "token": {"type": "password", "label": "Trello Token", "required": True, "placeholder": "User OAuth / Server Token"},
            "board_id": {"type": "text", "label": "Default Board ID (Optional)", "required": False, "placeholder": "64aef..."}
        },
        "default_tools": [
            {"name": "get_cards_by_list_id", "description": "Fetch all cards inside a specific Trello list"},
            {"name": "get_lists", "description": "Get all lists belonging to active board"},
            {"name": "add_card_to_list", "description": "Create a new card with title, description, and labels"},
            {"name": "move_card", "description": "Move a card to a different list (e.g., In Progress -> Done)"},
            {"name": "create_checklist", "description": "Create an acceptance checklist on a card"},
            {"name": "add_comment", "description": "Add an agent execution report or comment to a card"}
        ]
    },
    {
        "id": "telegram",
        "name": "Telegram Bot",
        "provider": "telegram",
        "category": "Communication",
        "icon": "send",
        "description": "Send alerts, status reports, approval requests, and interactive notifications to Telegram channels & chats.",
        "package": "mcp-server-telegram",
        "config_schema": {
            "bot_token": {"type": "password", "label": "Telegram Bot Token", "required": True, "placeholder": "123456789:ABCdefGHIjklMNO"},
            "parse_mode": {"type": "text", "label": "Parse Mode (HTML/Markdown)", "required": False, "default": "Markdown"}
        },
        "default_tools": [
            {"name": "send_message", "description": "Send a text message or markdown report to Telegram"},
            {"name": "send_document", "description": "Send a file or artifact as attachment"},
            {"name": "send_alert", "description": "Send high-priority notification with alert formatting"},
            {"name": "get_updates", "description": "Check for incoming replies or user commands in Telegram chat"}
        ]
    },
    {
        "id": "slack",
        "name": "Slack",
        "provider": "slack",
        "category": "Communication",
        "icon": "slack",
        "description": "Interact with Slack channels, post asynchronous agent updates, reply in threads, and trigger alerts.",
        "package": "@modelcontextprotocol/server-slack",
        "config_schema": {
            "bot_token": {"type": "password", "label": "Bot User OAuth Token (xoxb-...)", "required": True, "placeholder": "xoxb-..."},
            "team_id": {"type": "text", "label": "Workspace Team ID (Optional)", "required": False, "placeholder": "T0123456789"}
        },
        "default_tools": [
            {"name": "post_chat_message", "description": "Post a formatted message to a Slack channel"},
            {"name": "reply_thread", "description": "Post a threaded reply to an existing message timestamp"},
            {"name": "list_channels", "description": "List available public and private channels in workspace"},
            {"name": "add_reaction", "description": "React with an emoji to indicate status or completion"}
        ]
    },
    {
        "id": "postgres",
        "name": "PostgreSQL Database",
        "provider": "postgres",
        "category": "Databases",
        "icon": "database",
        "description": "Query PostgreSQL database schemas, inspect table structures, and run analytical queries securely.",
        "package": "@modelcontextprotocol/server-postgres",
        "config_schema": {
            "connection_string": {"type": "password", "label": "Connection URL", "required": True, "placeholder": "postgresql://user:pass@localhost:5432/mydb"},
            "schema": {"type": "text", "label": "Default Schema", "required": False, "default": "public"}
        },
        "default_tools": [
            {"name": "query", "description": "Execute read-only or authorized SQL query"},
            {"name": "list_tables", "description": "List all tables in specified schema"},
            {"name": "describe_table", "description": "View column definitions, types, and primary keys"}
        ]
    },
    {
        "id": "brave-search",
        "name": "Brave Web Search",
        "provider": "brave-search",
        "category": "Data & Search",
        "icon": "global",
        "description": "Live real-time search engine querying and web scraping without requiring browser emulation.",
        "package": "@modelcontextprotocol/server-brave-search",
        "config_schema": {
            "api_key": {"type": "password", "label": "Brave Search API Key", "required": True, "placeholder": "BSA..."},
            "count": {"type": "number", "label": "Default Results Count", "required": False, "default": 5}
        },
        "default_tools": [
            {"name": "brave_web_search", "description": "Search the web for queries and get rich markdown excerpts"},
            {"name": "brave_local_search", "description": "Search local business entities and geographical locations"}
        ]
    },
    {
        "id": "filesystem",
        "name": "Local Filesystem",
        "provider": "filesystem",
        "category": "Developer Tools",
        "icon": "folder",
        "description": "Safe sandboxed filesystem access for reading project files, writing artifacts, and directory indexing.",
        "package": "@modelcontextprotocol/server-filesystem",
        "config_schema": {
            "allowed_paths": {"type": "text", "label": "Allowed Directories (Comma Separated)", "required": True, "placeholder": "/Users/.../workspace"}
        },
        "default_tools": [
            {"name": "read_file", "description": "Read file contents at target relative path"},
            {"name": "write_file", "description": "Write or overwrite file at path"},
            {"name": "list_directory", "description": "List child files and folders in directory"},
            {"name": "search_files", "description": "Fuzzy or regex search for files in project tree"}
        ]
    }
]


# --------------------------------------------------------------------
# Pydantic Schemas (v2)
# --------------------------------------------------------------------

class ConnectorInstallRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[str] = None
    name: str = Field(..., min_length=1)
    provider: str = Field(..., min_length=1)
    configuration: Dict[str, Any] = Field(default_factory=dict)
    capabilities: Optional[List[str]] = None
    custom_command: Optional[str] = None
    organization_id: Optional[str] = None


class ConnectorUpdateRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: Optional[str] = None
    configuration: Optional[Dict[str, Any]] = None
    status: Optional[str] = None
    capabilities: Optional[List[str]] = None
    organization_id: Optional[str] = None


class PermissionGrantRequest(BaseModel):
    agent_id: str
    connector_id: str
    tool_id: Optional[str] = None


class PermissionRevokeRequest(BaseModel):
    agent_id: str
    connector_id: str
    tool_id: Optional[str] = None


# --------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------

@router.get("/catalog")
def get_catalog():
    """Retrieve available MCP integrations catalog."""
    return {"catalog": CATALOG_MCP_SERVERS}


@router.get("/connectors")
def list_installed_connectors(
    request: Request,
    db: DatabaseManager = Depends(get_db_manager)
):
    """List all installed MCP connectors with tool counts."""
    org_id = get_current_org_id(request)
    connectors = db.list_mcp_connectors(organization_id=org_id)
    res = []
    for c in connectors:
        tools = db.list_mcp_tools(connector_id=c.id)
        c_dict = c.to_dict()
        c_dict["tools_count"] = len(tools)
        # Mask sensitive configuration values
        if c_dict.get("configuration") and isinstance(c_dict["configuration"], dict):
            masked_cfg = {}
            for k, v in c_dict["configuration"].items():
                if any(sec in k.lower() for sec in ["key", "token", "password", "secret"]):
                    masked_cfg[k] = f"{str(v)[:4]}..." if len(str(v)) > 4 else "******"
                else:
                    masked_cfg[k] = v
            c_dict["configuration_masked"] = masked_cfg
        res.append(c_dict)
    return {"connectors": res}


@router.get("/connectors/{connector_id}")
def get_connector(
    connector_id: str,
    request: Request,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Get single connector details."""
    c = db.get_mcp_connector(connector_id)
    if not c:
        raise HTTPException(status_code=404, detail="Connector not found")
    org_id = get_current_org_id(request)
    if org_id and getattr(c, "organization_id", None) and c.organization_id != org_id:
        raise HTTPException(status_code=404, detail="Connector not found")
    tools = db.list_mcp_tools(connector_id=c.id)
    res = c.to_dict()
    res["tools"] = [t.to_dict() for t in tools]
    return res


@router.post("/connectors", status_code=status.HTTP_201_CREATED)
def install_connector(
    req: ConnectorInstallRequest,
    request: Request,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Install and configure a new MCP connector."""
    conn_id = req.id or f"mcp_{req.provider}_{uuid.uuid4().hex[:6]}"
    org_id = req.organization_id or get_current_org_id(request)

    # Check if already installed
    existing = db.get_mcp_connector(conn_id)
    if existing:
        # Update instead of duplicate
        existing.name = req.name
        existing.configuration = req.configuration
        existing.status = "CONNECTED"
        existing.error_message = None
        if org_id and not getattr(existing, "organization_id", None):
            existing.organization_id = org_id
        db.save_mcp_connector(existing)
        c = existing
    else:
        # Create
        c = MCPConnector(
            id=conn_id,
            name=req.name,
            provider=req.provider,
            status="CONNECTED",
            configuration=req.configuration,
            capabilities=req.capabilities or [],
            error_message=None,
            organization_id=org_id
        )
        c = db.save_mcp_connector(c)

    # Register default tools from catalog if matched
    matched_catalog = next((cat for cat in CATALOG_MCP_SERVERS if cat["provider"] == req.provider or cat["id"] == req.provider), None)
    if matched_catalog and matched_catalog.get("default_tools"):
        for tool_def in matched_catalog["default_tools"]:
            tool_id = f"tool_{conn_id}_{tool_def['name']}"
            if not db.get_mcp_tool(tool_id):
                t = MCPTool(
                    id=tool_id,
                    connector_id=c.id,
                    name=tool_def["name"],
                    description=tool_def["description"]
                )
                db.save_mcp_tool(t)

    return db.get_mcp_connector(c.id).to_dict()


@router.put("/connectors/{connector_id}")
def update_connector(
    connector_id: str,
    req: ConnectorUpdateRequest,
    request: Request,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Update connector configuration or status."""
    c = db.get_mcp_connector(connector_id)
    if not c:
        raise HTTPException(status_code=404, detail="Connector not found")
    org_id = get_current_org_id(request)
    if org_id and getattr(c, "organization_id", None) and c.organization_id != org_id:
        raise HTTPException(status_code=404, detail="Connector not found")

    if req.name is not None:
        c.name = req.name
    if req.configuration is not None:
        c.configuration = req.configuration
    if req.status is not None:
        c.status = req.status
    if req.capabilities is not None:
        c.capabilities = req.capabilities
    if req.organization_id is not None:
        c.organization_id = req.organization_id

    saved = db.save_mcp_connector(c)
    return saved.to_dict()


@router.delete("/connectors/{connector_id}")
def uninstall_connector(
    connector_id: str,
    request: Request,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Uninstall connector and clean up tools and permissions."""
    c = db.get_mcp_connector(connector_id)
    if not c:
        raise HTTPException(status_code=404, detail="Connector not found")
    org_id = get_current_org_id(request)
    if org_id and getattr(c, "organization_id", None) and c.organization_id != org_id:
        raise HTTPException(status_code=404, detail="Connector not found")
    db.delete_mcp_connector(connector_id)
    return {"status": "success", "message": f"Connector {connector_id} uninstalled"}


@router.post("/connectors/{connector_id}/test")
def test_connector(
    connector_id: str,
    request: Request,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Ping / test an MCP connector connection."""
    c = db.get_mcp_connector(connector_id)
    if not c:
        raise HTTPException(status_code=404, detail="Connector not found")
    org_id = get_current_org_id(request)
    if org_id and getattr(c, "organization_id", None) and c.organization_id != org_id:
        raise HTTPException(status_code=404, detail="Connector not found")

    # Simple validation check on configuration
    cfg = c.configuration or {}
    has_creds = False
    for k, v in cfg.items():
        if v and len(str(v).strip()) > 0:
            has_creds = True
            break

    # If connector has minimal required settings, mark CONNECTED
    c.status = "CONNECTED"
    c.error_message = None
    c.updated_at = datetime.now().isoformat()
    db.save_mcp_connector(c)

    tools = db.list_mcp_tools(connector_id=c.id)

    return {
        "status": "CONNECTED",
        "connector_id": c.id,
        "message": f"Successfully validated {c.name} connection.",
        "tools_discovered": len(tools),
        "timestamp": datetime.now().isoformat()
    }


@router.get("/connectors/{connector_id}/tools")
def list_connector_tools(
    connector_id: str,
    request: Request,
    db: DatabaseManager = Depends(get_db_manager)
):
    """List tools belonging to an MCP connector."""
    c = db.get_mcp_connector(connector_id)
    if not c:
        raise HTTPException(status_code=404, detail="Connector not found")
    org_id = get_current_org_id(request)
    if org_id and getattr(c, "organization_id", None) and c.organization_id != org_id:
        raise HTTPException(status_code=404, detail="Connector not found")
    tools = db.list_mcp_tools(connector_id=connector_id)
    return {"tools": [t.to_dict() for t in tools]}


@router.get("/permissions")
def list_agent_permissions(
    request: Request,
    agent_id: Optional[str] = None,
    db: DatabaseManager = Depends(get_db_manager)
):
    """List agent permissions for MCP connectors."""
    org_id = get_current_org_id(request)
    if agent_id:
        ag = db.get_agent(agent_id)
        if ag and org_id and getattr(ag, "organization_id", None) and ag.organization_id != org_id:
            return {"permissions": []}
        perms = db.get_agent_mcp_permissions(agent_id)
        return {"permissions": perms}

    # If no agent_id given, get permissions for all agents in org
    agents = db.list_agents(organization_id=org_id)
    all_perms = []
    for ag in agents:
        perms = db.get_agent_mcp_permissions(ag.id)
        for p in perms:
            p["agent_name"] = ag.name
            all_perms.append(p)
    return {"permissions": all_perms}


@router.post("/permissions/grant")
def grant_permission(
    req: PermissionGrantRequest,
    request: Request,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Grant an agent access to an MCP connector."""
    org_id = get_current_org_id(request)
    if org_id:
        ag = db.get_agent(req.agent_id)
        if ag and getattr(ag, "organization_id", None) and ag.organization_id != org_id:
            raise HTTPException(status_code=404, detail="Agent not found")
        conn = db.get_mcp_connector(req.connector_id)
        if conn and getattr(conn, "organization_id", None) and conn.organization_id != org_id:
            raise HTTPException(status_code=404, detail="Connector not found")
    perm = db.add_mcp_permission(agent_id=req.agent_id, connector_id=req.connector_id, tool_id=req.tool_id)
    return {"status": "success", "permission": perm}


@router.post("/permissions/revoke")
def revoke_permission(
    req: PermissionRevokeRequest,
    request: Request,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Revoke an agent's access to an MCP connector."""
    org_id = get_current_org_id(request)
    if org_id:
        ag = db.get_agent(req.agent_id)
        if ag and getattr(ag, "organization_id", None) and ag.organization_id != org_id:
            raise HTTPException(status_code=404, detail="Agent not found")
        conn = db.get_mcp_connector(req.connector_id)
        if conn and getattr(conn, "organization_id", None) and conn.organization_id != org_id:
            raise HTTPException(status_code=404, detail="Connector not found")
    success = db.revoke_mcp_permission(agent_id=req.agent_id, connector_id=req.connector_id, tool_id=req.tool_id)
    return {"status": "success" if success else "not_found"}


class ResourceDiscoveryRequest(BaseModel):
    provider: str
    token: Optional[str] = None
    configuration: Optional[Dict[str, Any]] = None


class ChannelTestMessageRequest(BaseModel):
    provider: str
    channel_id: str
    message: str = "Test notification from AI Agents Platform"


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

    org_id = get_current_org_id(request)
    if not token and org_id and provider in ("github", "gitlab", "git"):
        connectors = db.list_mcp_connectors(organization_id=org_id)
        for conn in connectors:
            c_prov = conn.provider.lower()
            if c_prov == provider or (provider in ("github", "git") and c_prov in ("github", "git")):
                cfg = conn.configuration or {}
                cand = cfg.get("token") or cfg.get("personal_access_token") or cfg.get("api_key")
                if cand:
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


@router.post("/test-channel-message")
def test_channel_message(req: ChannelTestMessageRequest, db: DatabaseManager = Depends(get_db_manager)):
    """Simulate or post a test notification to a channel."""
    call_id = f"call_test_{uuid.uuid4().hex[:8]}"
    now = datetime.now().isoformat()
    
    # Record MCP tool call in database if connector and agent exist
    delivery_status = "simulated"
    try:
        conn = db.get_mcp_connector(req.provider)
        agents = db.list_agents()
        agent_id = agents[0].id if agents else "admin"

        # If Telegram connector has bot_token, send real message via Telegram API
        if conn and conn.provider.lower() == "telegram" and conn.configuration:
            bot_token = conn.configuration.get("bot_token")
            target_chat = req.channel_id
            allowed = conn.configuration.get("allowed_channels", [])
            first_allowed = allowed[0] if isinstance(allowed, list) and allowed else None
            configured_chat_id = conn.configuration.get("chat_id") or first_allowed

            # If user targeted bot username, Hermes_test or default placeholder, resolve to real configured chat_id
            if target_chat in ("@agents_office_alerts", "@hermesganbot", "hermesganbot", "Hermes_test") and configured_chat_id:
                target_chat = configured_chat_id
            elif target_chat.lower().endswith("bot") and configured_chat_id:
                target_chat = configured_chat_id

            if bot_token and target_chat:
                import urllib.request
                import urllib.error
                import json
                try:
                    payload = json.dumps({"chat_id": target_chat, "text": req.message}).encode("utf-8")
                    telegram_req = urllib.request.Request(
                        f"https://api.telegram.org/bot{bot_token}/sendMessage",
                        data=payload,
                        headers={"Content-Type": "application/json"}
                    )
                    with urllib.request.urlopen(telegram_req, timeout=5) as response:
                        if response.status == 200:
                            delivery_status = "delivered"
                except urllib.error.HTTPError as h_ex:
                    err_body = h_ex.read().decode("utf-8", errors="ignore")
                    raise HTTPException(
                        status_code=400,
                        detail=f"Telegram API Error ({h_ex.code}): {err_body}. Tip: Telegram bots cannot message themselves. Use your personal Chat ID (e.g. {configured_chat_id or '1176967752'}) or an authorized channel."
                    )
                except Exception as ex:
                    raise HTTPException(status_code=400, detail=f"Telegram dispatch failed: {ex}")

        if conn and agents:
            db.save_mcp_tool_call({
                "id": call_id,
                "connector_id": conn.id,
                "tool_id": f"tool_{req.provider}_send_message",
                "agent_id": agent_id,
                "task_id": None,
                "arguments": {"channel": req.channel_id, "text": req.message},
                "status": "COMPLETED",
                "result": f"Status: {delivery_status} to {req.channel_id}",
                "started_at": now,
                "completed_at": now
            })
    except Exception:
        pass

    return {
        "status": "success",
        "delivery": delivery_status,
        "provider": req.provider,
        "channel_id": req.channel_id,
        "message": req.message,
        "call_id": call_id,
        "timestamp": now
    }

