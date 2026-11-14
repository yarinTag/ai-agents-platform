"""Legacy schema creation/migration statements for execution."""


def initialize(conn):
    # Agents table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS agents (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            system_prompt TEXT NOT NULL,
            skills TEXT,  -- JSON array
            model TEXT,
            effort TEXT,
            max_tokens INTEGER,
            temperature REAL,
            repo_path TEXT,
            github_url TEXT,
            department TEXT DEFAULT 'Engineering',
            avatar TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Add columns if table already existed without them
    for col, col_type in [
        ("repo_path", "TEXT"),
        ("github_url", "TEXT"),
        ("department", "TEXT DEFAULT 'Engineering'"),
        ("avatar", "TEXT"),
        ("parent_id", "TEXT"),
        ("role_type", "TEXT DEFAULT 'WORKER'"),
        ("max_concurrent_children", "INTEGER DEFAULT 3"),
        ("delegation_strategy", "TEXT DEFAULT 'hierarchical'"),
        ("allowed_child_ids", "TEXT"),
        ("allowed_tools", "TEXT"),
        ("template_id", "TEXT"),
        ("dangerously_skip_permissions", "INTEGER DEFAULT 0"),
        ("allow_sibling_communication", "INTEGER DEFAULT 1"),
        ("allowed_peer_ids", "TEXT"),
        ("mcp_permissions", "TEXT"),
        ("runtime_provider", "TEXT"),
        ("is_workflow_agent", "INTEGER DEFAULT 0"),
        ("workflow_id", "TEXT"),
        ("organization_id", "TEXT"),
        ("department_id", "TEXT")
    ]:
        try:
            conn.execute(f"ALTER TABLE agents ADD COLUMN {col} {col_type}")
        except Exception:
            pass

    conn.execute("CREATE INDEX IF NOT EXISTS idx_agents_parent ON agents(parent_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_agents_org ON agents(organization_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_agents_department_id ON agents(department_id)")

    # Projects table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            working_directory TEXT NOT NULL,
            instructions TEXT,
            skills TEXT,  -- JSON array
            allowed_tools TEXT,  -- JSON array
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    try:
        conn.execute("ALTER TABLE projects ADD COLUMN organization_id TEXT")
    except Exception:
        pass
    conn.execute("CREATE INDEX IF NOT EXISTS idx_projects_org ON projects(organization_id)")

    # Skills table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS skills (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            content TEXT NOT NULL,
            project_id TEXT,  -- NULL for organization-wide skills
            organization_id TEXT REFERENCES organizations(id) ON DELETE CASCADE,
            is_system INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects (id)
        )
    """)

    # Task runs table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS task_runs (
            run_id TEXT PRIMARY KEY,
            agent_id TEXT NOT NULL,
            project_id TEXT,
            prompt TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL,
            started_at TIMESTAMP,
            ended_at TIMESTAMP,
            result TEXT,
            error TEXT,
            exit_code INTEGER,
            events TEXT,  -- JSON array
            parent_task_id TEXT,
            root_task_id TEXT,
            assigned_by TEXT,
            FOREIGN KEY (agent_id) REFERENCES agents (id),
            FOREIGN KEY (project_id) REFERENCES projects (id)
        )
    """)

    # Add delegation, tracing, dependencies, structured result, and session continuation columns to task_runs if not present
    for col, col_type in [
        ("parent_task_id", "TEXT"),
        ("root_task_id", "TEXT"),
        ("assigned_by", "TEXT"),
        ("session_id", "TEXT"),
        ("dependencies", "TEXT"),
        ("structured_result", "TEXT"),
        ("acceptance_criteria", "TEXT"),
        ("retry_count", "INTEGER DEFAULT 0"),
        ("input_tokens", "INTEGER DEFAULT 0"),
        ("output_tokens", "INTEGER DEFAULT 0"),
        ("cache_read_tokens", "INTEGER DEFAULT 0"),
        ("cache_write_tokens", "INTEGER DEFAULT 0"),
        ("cost_usd", "REAL DEFAULT 0.0"),
        ("cost_source", "TEXT DEFAULT 'UNKNOWN'"),
        ("model", "TEXT"),
        ("organization_id", "TEXT")
    ]:
        try:
            conn.execute(f"ALTER TABLE task_runs ADD COLUMN {col} {col_type}")
        except Exception:
            pass

    # Create indexes for better query performance
    conn.execute("CREATE INDEX IF NOT EXISTS idx_task_runs_agent ON task_runs(agent_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_task_runs_project ON task_runs(project_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_task_runs_status ON task_runs(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_task_runs_created ON task_runs(created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_task_runs_parent ON task_runs(parent_task_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_task_runs_root ON task_runs(root_task_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_task_runs_assigned ON task_runs(assigned_by)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_task_runs_org ON task_runs(organization_id)")
