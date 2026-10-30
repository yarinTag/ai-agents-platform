"""Legacy schema creation/migration statements for collaboration."""


def initialize(conn):
    # Cron jobs table for scheduled recurring workflows
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cron_jobs (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            cron_expression TEXT NOT NULL,
            agent_id TEXT NOT NULL,
            project_id TEXT,
            prompt TEXT NOT NULL,
            input_data TEXT,
            enabled INTEGER DEFAULT 1,
            concurrency_policy TEXT DEFAULT 'SKIP',
            misfire_policy TEXT DEFAULT 'RUN_ONCE',
            timezone TEXT DEFAULT 'UTC',
            last_run_at TIMESTAMP,
            last_run_id TEXT,
            last_status TEXT,
            next_run_at TIMESTAMP NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (agent_id) REFERENCES agents (id) ON DELETE CASCADE,
            FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE SET NULL,
            FOREIGN KEY (last_run_id) REFERENCES task_runs (run_id) ON DELETE SET NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cron_jobs_poll ON cron_jobs(enabled, next_run_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cron_jobs_agent ON cron_jobs(agent_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cron_jobs_project ON cron_jobs(project_id)")

    # Agent interactions table for questions, clarifications, and manager/human approvals
    conn.execute("""
        CREATE TABLE IF NOT EXISTS agent_interactions (
            id TEXT PRIMARY KEY,
            task_id TEXT NOT NULL,
            requester_agent_id TEXT NOT NULL,
            target_approver_id TEXT NOT NULL,
            interaction_type TEXT NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            context_data TEXT,
            status TEXT DEFAULT 'PENDING',
            resolution_response TEXT,
            resolved_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            resolved_at TIMESTAMP,
            FOREIGN KEY (task_id) REFERENCES task_runs(run_id) ON DELETE CASCADE,
            FOREIGN KEY (requester_agent_id) REFERENCES agents(id) ON DELETE CASCADE
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_interactions_target ON agent_interactions(target_approver_id, status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_interactions_task ON agent_interactions(task_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_interactions_agent ON agent_interactions(requester_agent_id)")

    # Agent conversations table (Chat sessions)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS agent_conversations (
            id TEXT PRIMARY KEY,
            agent_id TEXT NOT NULL,
            project_id TEXT,
            title TEXT DEFAULT 'Direct Chat Session',
            claude_session_id TEXT,
            runtime_session_id TEXT,
            task_id TEXT,
            supervisor_session_id TEXT,
            status TEXT DEFAULT 'ACTIVE',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL
        )
    """)
    # Migration columns if table already exists
    for col, col_type in [
        ("task_id", "TEXT"),
        ("supervisor_session_id", "TEXT"),
        ("status", "TEXT DEFAULT 'ACTIVE'"),
        ("channel_key", "TEXT"),
        ("runtime_session_id", "TEXT")
    ]:
        try:
            conn.execute(f"ALTER TABLE agent_conversations ADD COLUMN {col} {col_type}")
        except Exception:
            pass
    conn.execute("CREATE INDEX IF NOT EXISTS idx_conversations_agent ON agent_conversations(agent_id, updated_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_conversations_channel ON agent_conversations(channel_key)")

    # Chat messages table (Messages, Thoughts, Tool calls, Approvals)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS chat_messages (
            id TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL,
            agent_id TEXT NOT NULL,
            task_id TEXT,
            sender_type TEXT NOT NULL,
            message_type TEXT NOT NULL,
            content TEXT NOT NULL,
            metadata TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (conversation_id) REFERENCES agent_conversations(id) ON DELETE CASCADE,
            FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE,
            FOREIGN KEY (task_id) REFERENCES task_runs(run_id) ON DELETE SET NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_messages_conv ON chat_messages(conversation_id, created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_messages_agent ON chat_messages(agent_id, created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_messages_task ON chat_messages(task_id)")

    # Project Shared Memory table (Knowledge Base, ADRs, Conventions)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS project_memories (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'INSIGHT', -- 'ADR', 'CONVENTION', 'INSIGHT', 'LESSON'
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            tags TEXT, -- JSON array
            author_agent_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
            FOREIGN KEY (author_agent_id) REFERENCES agents(id) ON DELETE SET NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_proj ON project_memories(project_id, category)")

    for col, col_type in [
        ("source_task_id", "TEXT"),
        ("source_run_id", "TEXT"),
        ("confidence", "REAL DEFAULT 1.0")
    ]:
        try:
            conn.execute(f"ALTER TABLE project_memories ADD COLUMN {col} {col_type}")
        except Exception:
            pass

    # War Room Sessions table (Multi-Agent Deliberation & Planning)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS war_room_sessions (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            topic TEXT NOT NULL,
            project_id TEXT,
            moderator_agent_id TEXT NOT NULL,
            participant_agent_ids TEXT NOT NULL, -- JSON array
            status TEXT NOT NULL DEFAULT 'GATHERING', -- 'GATHERING', 'DEBATING', 'CONSENSUS_REACHED', 'EXECUTING', 'COMPLETED'
            synthesized_plan TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL,
            FOREIGN KEY (moderator_agent_id) REFERENCES agents(id) ON DELETE CASCADE
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_war_room_status ON war_room_sessions(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_war_room_proj ON war_room_sessions(project_id)")

    # War Room Messages table (Roundtable Dialogue)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS war_room_messages (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            agent_id TEXT NOT NULL,
            round_number INTEGER DEFAULT 1,
            message_type TEXT NOT NULL DEFAULT 'PROPOSAL', -- 'PROPOSAL', 'CRITIQUE', 'CONSENSUS_VOTE', 'SUMMARY'
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES war_room_sessions(id) ON DELETE CASCADE,
            FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_war_room_msg_session ON war_room_messages(session_id, round_number)")

    # First-Class Agent-to-Agent Messaging table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS agent_messages (
            id TEXT PRIMARY KEY,
            from_agent_id TEXT NOT NULL,
            to_agent_id TEXT NOT NULL,
            task_id TEXT,
            run_id TEXT,
            parent_message_id TEXT,
            message_type TEXT NOT NULL DEFAULT 'QUESTION',
            content TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'SENT',
            metadata TEXT,
            channel_key TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            responded_at TIMESTAMP,
            FOREIGN KEY (from_agent_id) REFERENCES agents(id) ON DELETE CASCADE,
            FOREIGN KEY (to_agent_id) REFERENCES agents(id) ON DELETE CASCADE,
            FOREIGN KEY (parent_message_id) REFERENCES agent_messages(id) ON DELETE SET NULL,
            FOREIGN KEY (task_id) REFERENCES task_runs(run_id) ON DELETE SET NULL
        )
    """)
    try:
        conn.execute("ALTER TABLE agent_messages ADD COLUMN channel_key TEXT")
    except Exception:
        pass
    conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_msg_from ON agent_messages(from_agent_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_msg_to ON agent_messages(to_agent_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_msg_task ON agent_messages(task_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_msg_channel ON agent_messages(channel_key)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_msg_parent ON agent_messages(parent_message_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_msg_created ON agent_messages(created_at)")

    # Super Agent Configs table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS super_agent_configs (
            agent_id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            can_answer_questions INTEGER DEFAULT 1,
            can_delegate INTEGER DEFAULT 1,
            can_create_subtasks INTEGER DEFAULT 1,
            can_use_mcp INTEGER DEFAULT 1,
            can_make_project_decisions INTEGER DEFAULT 1,
            can_modify_files INTEGER DEFAULT 1,
            can_execute_commands INTEGER DEFAULT 1,
            require_human_approval_for TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_super_agent_proj ON super_agent_configs(project_id)")
