"""Legacy schema creation/migration statements for event."""


def initialize(conn):
    # Event log table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS event_log (
            id TEXT PRIMARY KEY,
            sequence_number INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            agent_id TEXT,
            task_id TEXT,
            execution_id TEXT,
            parent_task_id TEXT,
            project_id TEXT,
            correlation_id TEXT,
            payload TEXT,
            source TEXT NOT NULL,
            timestamp TIMESTAMP NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_type ON event_log(event_type)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_agent ON event_log(agent_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_task ON event_log(task_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_seq ON event_log(sequence_number)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_time ON event_log(timestamp)")

    # Agent templates table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS agent_templates (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            role TEXT NOT NULL,
            system_prompt TEXT NOT NULL,
            model TEXT DEFAULT 'default',
            skills TEXT,
            tools TEXT,
            suggested_children TEXT,
            category TEXT DEFAULT 'Engineering',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_templates_category ON agent_templates(category)")

    # Audit logs table for security tracking and compliance
    conn.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id TEXT PRIMARY KEY,
            action TEXT NOT NULL,
            actor TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            details TEXT,
            ip_address TEXT,
            correlation_id TEXT,
            timestamp TIMESTAMP NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_logs(action)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_logs(entity_type, entity_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_time ON audit_logs(timestamp)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_correlation ON audit_logs(correlation_id)")
