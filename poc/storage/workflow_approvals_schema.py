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
    conn.execute("""CREATE TABLE IF NOT EXISTS pr_channel_deliveries (
        approval_id TEXT PRIMARY KEY REFERENCES workflow_approvals(id) ON DELETE CASCADE,
        binding_id TEXT NOT NULL, token_digest TEXT UNIQUE, connector_id TEXT, channel_id TEXT,
        message_id TEXT, bot_id TEXT, status TEXT NOT NULL, rendered TEXT,
        retry_at INTEGER NOT NULL DEFAULT 0, callback_id TEXT, decision INTEGER, identity_link_id TEXT
    )""")
    if not any(row[1] == 'identity_link_id' for row in conn.execute('PRAGMA table_info(pr_channel_deliveries)')):
        conn.execute('ALTER TABLE pr_channel_deliveries ADD COLUMN identity_link_id TEXT')
