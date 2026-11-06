"""Durable human gates, pinned PR facts and non-retryable merge receipts."""


def initialize(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS workflow_approvals (
        id TEXT PRIMARY KEY, execution_id TEXT NOT NULL, step_run_id TEXT NOT NULL,
        task_id TEXT NOT NULL, organization_id TEXT NOT NULL, department_id TEXT NOT NULL,
        workflow_revision INTEGER NOT NULL, status TEXT NOT NULL,
        config_json TEXT NOT NULL, subjects_json TEXT NOT NULL, report TEXT NOT NULL,
        created_at TEXT NOT NULL, expires_at TEXT NOT NULL, resolved_at TEXT,
        resolved_by TEXT, error TEXT, receipts_json TEXT NOT NULL DEFAULT '[]',
        UNIQUE(execution_id),
        FOREIGN KEY(execution_id) REFERENCES workflow_executions(id) ON DELETE CASCADE
    )''')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_workflow_approvals_scope ON workflow_approvals(organization_id,department_id,status)')
