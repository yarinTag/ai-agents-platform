"""Workflow, immutable revision and isolated authoring schema initialization."""
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

    # Authoring proposals are intentionally separate from executable workflows.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS workflow_assistant_drafts (
            id TEXT PRIMARY KEY,
            organization_id TEXT NOT NULL,
            department_id TEXT NOT NULL,
            created_by TEXT NOT NULL,
            intent_text TEXT NOT NULL DEFAULT '',
            proposal_json TEXT NOT NULL,
            validation_json TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('READY_FOR_REVIEW', 'BLOCKED', 'NEEDS_CLARIFICATION')),
            revision INTEGER NOT NULL CHECK(revision >= 1),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            idempotency_key TEXT,
            request_hash TEXT NOT NULL,
            UNIQUE(organization_id, created_by, idempotency_key),
            FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
            FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE CASCADE
        )
    """)
    conn.execute("""CREATE INDEX IF NOT EXISTS idx_assistant_drafts_scope
        ON workflow_assistant_drafts(organization_id, department_id, updated_at)""")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS workflow_assistant_draft_revisions (
            draft_id TEXT NOT NULL,
            revision INTEGER NOT NULL,
            snapshot_json TEXT NOT NULL,
            actor_id TEXT NOT NULL,
            actor_label TEXT NOT NULL,
            source TEXT NOT NULL,
            client_id TEXT,
            created_at TEXT NOT NULL,
            PRIMARY KEY(draft_id, revision),
            FOREIGN KEY (draft_id) REFERENCES workflow_assistant_drafts(id) ON DELETE CASCADE
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS workflow_assistant_generations (
            id TEXT PRIMARY KEY,
            organization_id TEXT NOT NULL,
            department_id TEXT NOT NULL,
            created_by TEXT NOT NULL,
            planner_agent_id TEXT NOT NULL,
            request_json TEXT NOT NULL,
            request_hash TEXT NOT NULL,
            idempotency_key TEXT,
            status TEXT NOT NULL CHECK(status IN ('QUEUED', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED')),
            result_json TEXT,
            saved_draft_id TEXT REFERENCES workflow_assistant_drafts(id) ON DELETE SET NULL,
            saved_draft_revision INTEGER,
            error_code TEXT,
            error_message TEXT,
            input_tokens INTEGER NOT NULL DEFAULT 0,
            output_tokens INTEGER NOT NULL DEFAULT 0,
            cost_usd REAL,
            cost_source TEXT,
            model TEXT,
            created_at TEXT NOT NULL,
            started_at TEXT,
            completed_at TEXT,
            deadline_at TEXT NOT NULL,
            UNIQUE(organization_id, created_by, idempotency_key),
            FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
            FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE CASCADE
        )
    """)
    try:
        conn.execute("ALTER TABLE workflow_assistant_generations ADD COLUMN saved_draft_id TEXT REFERENCES workflow_assistant_drafts(id) ON DELETE SET NULL")
    except sqlite3.OperationalError as exc:
        if "duplicate column" not in str(exc).lower():
            raise
    try:
        conn.execute("ALTER TABLE workflow_assistant_generations ADD COLUMN saved_draft_revision INTEGER")
    except sqlite3.OperationalError as exc:
        if "duplicate column" not in str(exc).lower():
            raise
    conn.execute("""CREATE INDEX IF NOT EXISTS idx_assistant_generations_scope
        ON workflow_assistant_generations(organization_id, department_id, status)""")

    conn.execute("""CREATE TABLE IF NOT EXISTS workflow_assistant_tool_calls (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        generation_id TEXT NOT NULL REFERENCES workflow_assistant_generations(id) ON DELETE CASCADE,
        tool_name TEXT NOT NULL CHECK(tool_name IN ('workflow_catalog','workflow_schema','validate_workflow_yaml')),
        proposal_hash TEXT,
        validation_id TEXT UNIQUE,
        proposal_json TEXT,
        created_at TEXT NOT NULL
    )""")
    try:
        conn.execute("ALTER TABLE workflow_assistant_tool_calls ADD COLUMN proposal_hash TEXT")
    except sqlite3.OperationalError as exc:
        if "duplicate column" not in str(exc).lower():
            raise
    for column in ('validation_id', 'proposal_json'):
        try:
            conn.execute(f"ALTER TABLE workflow_assistant_tool_calls ADD COLUMN {column} TEXT")
        except sqlite3.OperationalError as exc:
            if "duplicate column" not in str(exc).lower():
                raise
    conn.execute("""CREATE UNIQUE INDEX IF NOT EXISTS idx_assistant_validation_id
        ON workflow_assistant_tool_calls(validation_id)""")
    conn.execute("""CREATE INDEX IF NOT EXISTS idx_assistant_tool_calls_generation
        ON workflow_assistant_tool_calls(generation_id, id)""")

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


