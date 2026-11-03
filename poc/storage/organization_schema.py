"""Legacy schema creation/migration statements for organization."""


def initialize(conn):
    # 0. Organizations table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS organizations (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            slug TEXT UNIQUE NOT NULL,
            domain TEXT,
            settings_json TEXT DEFAULT '{}',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    try:
        conn.execute("ALTER TABLE organizations ADD COLUMN plugins_source_mode TEXT DEFAULT 'local'")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE organizations ADD COLUMN plugins_git_repo TEXT")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE organizations ADD COLUMN plugins_local_path TEXT")
    except Exception:
        pass

    # 1. Departments table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS departments (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            monthly_budget_usd REAL DEFAULT 100.0,
            current_spend_usd REAL DEFAULT 0.0,
            budget_action TEXT DEFAULT 'REQUIRE_APPROVAL',
            alert_threshold_pct REAL DEFAULT 80.0,
            organization_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE
        )
    """)
    try:
        conn.execute("ALTER TABLE departments ADD COLUMN organization_id TEXT REFERENCES organizations(id) ON DELETE CASCADE")
    except Exception:
        pass

    # 1b. Department MCP Access Governance table (Tool-level filtering)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS department_mcp_access (
            id TEXT PRIMARY KEY,
            organization_id TEXT,
            department_id TEXT NOT NULL,
            connector_id TEXT NOT NULL,
            allowed_tools TEXT DEFAULT '*',
            is_active INTEGER DEFAULT 1,
            granted_by_user_id TEXT,
            granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
            FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE CASCADE,
            FOREIGN KEY (connector_id) REFERENCES mcp_connectors(id) ON DELETE CASCADE,
            UNIQUE(department_id, connector_id)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_dept_mcp_lookup ON department_mcp_access(department_id, is_active)")

    # 1c. Users table (Enterprise Multi-Tenant Users)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            organization_id TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            full_name TEXT NOT NULL,
            role TEXT DEFAULT 'MEMBER',
            status TEXT DEFAULT 'ACTIVE',
            password_hash TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login_at TIMESTAMP,
            FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_users_org ON users(organization_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")

    # 1d. Department Members table (User to Department assignment)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS department_members (
            id TEXT PRIMARY KEY,
            department_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            role TEXT DEFAULT 'OPERATOR',
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE(department_id, user_id)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_dept_members_dept ON department_members(department_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_dept_members_user ON department_members(user_id)")

    # 1e. Organization & Department Invitations (Email-based Onboarding)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS org_invitations (
            id TEXT PRIMARY KEY,
            organization_id TEXT NOT NULL,
            department_id TEXT,
            email TEXT NOT NULL,
            role TEXT DEFAULT 'MEMBER',
            invite_token TEXT UNIQUE NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            status TEXT DEFAULT 'PENDING',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
            FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE CASCADE
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_invitations_email ON org_invitations(email, status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_invitations_org ON org_invitations(organization_id)")
    from .runtime_settings import initialize as initialize_runtime_settings
    initialize_runtime_settings(conn)

    from .hosted_budget import initialize as initialize_hosted_budget
    initialize_hosted_budget(conn)
