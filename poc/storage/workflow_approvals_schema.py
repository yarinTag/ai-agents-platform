"""Durable human gates, pinned PR facts and non-retryable merge receipts."""


def _create(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS workflow_approvals (
        id TEXT PRIMARY KEY, execution_id TEXT NOT NULL, step_run_id TEXT NOT NULL,
        task_id TEXT NOT NULL, organization_id TEXT NOT NULL, department_id TEXT NOT NULL,
        workflow_revision INTEGER NOT NULL, status TEXT NOT NULL,
        config_json TEXT NOT NULL, subjects_json TEXT NOT NULL, report TEXT NOT NULL,
        created_at TEXT NOT NULL, expires_at TEXT NOT NULL, resolved_at TEXT,
        resolved_by TEXT, error TEXT, receipts_json TEXT NOT NULL DEFAULT '[]',
        position INTEGER NOT NULL DEFAULT 0, remaining_json TEXT NOT NULL DEFAULT '[]',
        UNIQUE(execution_id, position),
        FOREIGN KEY(execution_id) REFERENCES workflow_executions(id) ON DELETE CASCADE
    )''')
    conn.execute("""CREATE TABLE IF NOT EXISTS pr_channel_deliveries (
        approval_id TEXT PRIMARY KEY REFERENCES workflow_approvals(id) ON DELETE CASCADE,
        binding_id TEXT NOT NULL, token_digest TEXT UNIQUE, connector_id TEXT, channel_id TEXT,
        message_id TEXT, bot_id TEXT, status TEXT NOT NULL, rendered TEXT,
        retry_at INTEGER NOT NULL DEFAULT 0, callback_id TEXT, decision INTEGER, identity_link_id TEXT
    )""")
    columns = {row[1] for row in conn.execute('PRAGMA table_info(pr_channel_deliveries)')}
    if 'claimed_at' not in columns:
        conn.execute('ALTER TABLE pr_channel_deliveries ADD COLUMN claimed_at INTEGER')
    if 'identity_link_id' not in columns:
        conn.execute('ALTER TABLE pr_channel_deliveries ADD COLUMN identity_link_id TEXT')


def initialize(conn):
    # Normalize legacy delivery columns before copying both sides of the FK.
    conn.execute('SAVEPOINT approval_sequence')
    columns = {row[1] for row in conn.execute('PRAGMA table_info(workflow_approvals)')}
    _create(conn)
    if columns and 'position' not in columns:
        conn.execute('ALTER TABLE pr_channel_deliveries RENAME TO legacy_pr_channel_deliveries')
        conn.execute('ALTER TABLE workflow_approvals RENAME TO legacy_workflow_approvals')
        _create(conn)
        approval_columns = (
            'id,execution_id,step_run_id,task_id,organization_id,department_id,workflow_revision,'
            'status,config_json,subjects_json,report,created_at,expires_at,resolved_at,resolved_by,error,receipts_json'
        )
        delivery_columns = (
            'approval_id,binding_id,token_digest,connector_id,channel_id,message_id,bot_id,status,rendered,'
            'retry_at,callback_id,decision,identity_link_id,claimed_at'
        )
        conn.execute(f'INSERT INTO workflow_approvals ({approval_columns}) '
                     f'SELECT {approval_columns} FROM legacy_workflow_approvals')
        conn.execute(f'INSERT INTO pr_channel_deliveries ({delivery_columns}) '
                     f'SELECT {delivery_columns} FROM legacy_pr_channel_deliveries')
        conn.execute('DROP TABLE legacy_pr_channel_deliveries')
        conn.execute('DROP TABLE legacy_workflow_approvals')
    columns = {row[1] for row in conn.execute('PRAGMA table_info(workflow_approvals)')}
    if 'advance_pending' not in columns:
        conn.execute('ALTER TABLE workflow_approvals ADD COLUMN advance_pending INTEGER NOT NULL DEFAULT 0')
        conn.execute('ALTER TABLE workflow_approvals ADD COLUMN advance_claim_until INTEGER')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_workflow_approvals_scope '
                 'ON workflow_approvals(organization_id,department_id,status)')
    conn.execute("""CREATE UNIQUE INDEX IF NOT EXISTS idx_workflow_approvals_live
        ON workflow_approvals(execution_id) WHERE status IN ('NOTIFYING','PENDING','RESOLVING','EXPIRING')""")
    conn.execute('RELEASE approval_sequence')
