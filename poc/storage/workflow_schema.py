"""Legacy schema creation/migration statements for workflow."""


def initialize(conn):
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
