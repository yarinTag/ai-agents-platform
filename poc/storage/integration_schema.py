"""Legacy schema creation/migration statements for integration."""


def initialize(conn):
    # MCP Connectors table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS mcp_connectors (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            provider TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'DISCONNECTED',
            configuration TEXT,
            capabilities TEXT,
            error_message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    try:
        conn.execute("ALTER TABLE mcp_connectors ADD COLUMN organization_id TEXT")
    except Exception:
        pass
    conn.execute("CREATE INDEX IF NOT EXISTS idx_mcp_connectors_org ON mcp_connectors(organization_id)")

    # MCP Tools table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS mcp_tools (
            id TEXT PRIMARY KEY,
            connector_id TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            input_schema TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (connector_id) REFERENCES mcp_connectors(id) ON DELETE CASCADE
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_mcp_tools_conn ON mcp_tools(connector_id)")

    # MCP Tool Calls table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS mcp_tool_calls (
            id TEXT PRIMARY KEY,
            connector_id TEXT NOT NULL,
            tool_id TEXT NOT NULL,
            agent_id TEXT NOT NULL,
            task_id TEXT,
            run_id TEXT,
            status TEXT NOT NULL DEFAULT 'STARTED',
            arguments TEXT,
            result TEXT,
            error TEXT,
            started_at TIMESTAMP NOT NULL,
            completed_at TIMESTAMP,
            FOREIGN KEY (connector_id) REFERENCES mcp_connectors(id) ON DELETE CASCADE,
            FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_mcp_calls_agent ON mcp_tool_calls(agent_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_mcp_calls_conn ON mcp_tool_calls(connector_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_mcp_calls_task ON mcp_tool_calls(task_id)")

    # MCP Agent Permissions table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS mcp_agent_permissions (
            id TEXT PRIMARY KEY,
            agent_id TEXT NOT NULL,
            connector_id TEXT NOT NULL,
            tool_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE,
            FOREIGN KEY (connector_id) REFERENCES mcp_connectors(id) ON DELETE CASCADE
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_mcp_perm_agent ON mcp_agent_permissions(agent_id)")

    # Agent Teams table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS agent_teams (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            manager_agent_id TEXT NOT NULL,
            project_id TEXT,
            description TEXT,
            status TEXT NOT NULL DEFAULT 'ACTIVE',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (manager_agent_id) REFERENCES agents(id) ON DELETE CASCADE,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_teams_mgr ON agent_teams(manager_agent_id)")

    # Team Members table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS team_members (
            team_id TEXT NOT NULL,
            agent_id TEXT NOT NULL,
            role_in_team TEXT DEFAULT 'MEMBER',
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (team_id, agent_id),
            FOREIGN KEY (team_id) REFERENCES agent_teams(id) ON DELETE CASCADE,
            FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE
        )
    """)

    # Platform-wide key/value settings (runtime provider choice, setup state).
    # Secrets are never stored here — only non-secret selections.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS platform_settings (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
