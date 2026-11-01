"""Workflow and immutable revision schema initialization."""
import sqlite3


def initialize(conn, insert_revision):
    # 2. Workflows table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS workflows (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            department_id TEXT,
            definition_json TEXT NOT NULL,
            webhook_enabled INTEGER DEFAULT 1,
            webhook_token TEXT UNIQUE,
            cron_expression TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE SET NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_workflows_dept ON workflows(department_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_workflows_token ON workflows(webhook_token)")
    try:
        conn.execute("ALTER TABLE workflows ADD COLUMN organization_id TEXT")
    except Exception:
        pass
    conn.execute("CREATE INDEX IF NOT EXISTS idx_workflows_org ON workflows(organization_id)")

    try:
        conn.execute("ALTER TABLE workflows ADD COLUMN revision INTEGER NOT NULL DEFAULT 1")
    except sqlite3.OperationalError as exc:
        if "duplicate column" not in str(exc).lower():
            raise
    conn.execute("""
        CREATE TABLE IF NOT EXISTS workflow_revisions (
            workflow_id TEXT NOT NULL,
            revision INTEGER NOT NULL,
            snapshot_json TEXT NOT NULL,
            changed_fields_json TEXT NOT NULL,
            actor_id TEXT,
            actor_label TEXT NOT NULL,
            change_summary TEXT,
            created_at TEXT NOT NULL,
            PRIMARY KEY (workflow_id, revision),
            FOREIGN KEY (workflow_id) REFERENCES workflows(id) ON DELETE CASCADE
        )
    """)
    # Existing workflows get a baseline of their current saved state only.
    for row in conn.execute("""SELECT w.* FROM workflows w WHERE NOT EXISTS
        (SELECT 1 FROM workflow_revisions r WHERE r.workflow_id = w.id)""").fetchall():
        insert_revision(conn, dict(row), [], None, "Legacy baseline",
            "State captured when revision history was introduced", row["updated_at"] or row["created_at"])

    # 3. Workflow executions table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS workflow_executions (
            id TEXT PRIMARY KEY,
            workflow_id TEXT NOT NULL,
            trigger_type TEXT NOT NULL,
            trigger_payload TEXT,
            status TEXT NOT NULL DEFAULT 'PENDING',
            department_id TEXT,
            sandbox_path TEXT,
            total_input_tokens INTEGER DEFAULT 0,
            total_output_tokens INTEGER DEFAULT 0,
            total_cost_usd REAL DEFAULT 0.0,
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            error_message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (workflow_id) REFERENCES workflows(id) ON DELETE CASCADE,
            FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE SET NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_wf_exec_wf ON workflow_executions(workflow_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_wf_exec_status ON workflow_executions(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_wf_exec_dept ON workflow_executions(department_id)")
    try:
        conn.execute("ALTER TABLE workflow_executions ADD COLUMN payload_hash TEXT")
    except Exception:
        pass
    conn.execute("CREATE INDEX IF NOT EXISTS idx_wf_exec_hash ON workflow_executions(workflow_id, payload_hash, status)")

    # 4. Workflow step runs table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS workflow_step_runs (
            id TEXT PRIMARY KEY,
            execution_id TEXT NOT NULL,
            step_key TEXT NOT NULL,
            agent_id TEXT,
            status TEXT NOT NULL DEFAULT 'PENDING',
            task_run_id TEXT,
            input_data TEXT,
            output_data TEXT,
            input_tokens INTEGER DEFAULT 0,
            output_tokens INTEGER DEFAULT 0,
            cost_usd REAL DEFAULT 0.0,
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            error_message TEXT,
            FOREIGN KEY (execution_id) REFERENCES workflow_executions(id) ON DELETE CASCADE,
            FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE SET NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_step_runs_exec ON workflow_step_runs(execution_id)")

    # 5. Run evaluations & learning records table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS run_evaluations (
            id TEXT PRIMARY KEY,
            execution_id TEXT NOT NULL,
            workflow_id TEXT NOT NULL,
            rating INTEGER,
            feedback_notes TEXT,
            lessons_extracted TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (execution_id) REFERENCES workflow_executions(id) ON DELETE CASCADE,
            FOREIGN KEY (workflow_id) REFERENCES workflows(id) ON DELETE CASCADE
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_eval_wf ON run_evaluations(workflow_id)")



    # New small workflow chat, independent of the removed Workflow Assistant.
    conn.execute("""CREATE TABLE IF NOT EXISTS workflow_builder_jobs (
        id TEXT PRIMARY KEY, organization_id TEXT NOT NULL, user_id TEXT NOT NULL,
        department_id TEXT NOT NULL, request_hash TEXT NOT NULL, request_json TEXT NOT NULL,
        status TEXT NOT NULL, result_json TEXT, error TEXT, provider_id TEXT NOT NULL,
        model_id TEXT NOT NULL, input_tokens INTEGER NOT NULL DEFAULT 0,
        output_tokens INTEGER NOT NULL DEFAULT 0, cost_usd REAL,
        cost_source TEXT NOT NULL, workflow_id TEXT, created_at TEXT NOT NULL,
        deadline_at TEXT NOT NULL,
        FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE CASCADE
    )""")
    conn.execute("""CREATE UNIQUE INDEX IF NOT EXISTS idx_builder_active_department
        ON workflow_builder_jobs(department_id) WHERE status='GENERATING'""")

    conn.execute("""CREATE TABLE IF NOT EXISTS workflow_execution_tool_contexts (
        execution_id TEXT PRIMARY KEY, context_json TEXT NOT NULL,
        FOREIGN KEY (execution_id) REFERENCES workflow_executions(id) ON DELETE CASCADE
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS workflow_tool_scopes (
        task_id TEXT PRIMARY KEY, execution_id TEXT NOT NULL, scope_json TEXT NOT NULL,
        FOREIGN KEY (task_id) REFERENCES task_runs(run_id) ON DELETE CASCADE,
        FOREIGN KEY (execution_id) REFERENCES workflow_executions(id) ON DELETE CASCADE
    )""")
