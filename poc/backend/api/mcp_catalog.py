"""Mcp: catalog ownership."""

from fastapi import APIRouter

router = APIRouter()


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
            {"name": "get_repository_activity", "description": "Read recent commits, issues, pull requests and releases through the governed runtime"},
            {"name": "list_commits", "description": "Read recent GitHub commits"},
            {"name": "list_pull_requests", "description": "Read recent GitHub pull requests"},
            {"name": "list_releases", "description": "Read recent GitHub releases"},
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



@router.get("/catalog")
def get_catalog():
    """Retrieve available MCP integrations catalog."""
    return {"catalog": CATALOG_MCP_SERVERS}

