"""
Persistence layer for the AI Agents Platform PoC.
Uses SQLite to store agents, projects, skills, and task runs.
"""

import sqlite3
import json
import os
import logging
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any, Union
from pathlib import Path

# Import from local modules using absolute imports
from config import AgentConfig, ProjectConfig, Skill, AgentTemplate
from runtime_adapter import AgentRun, TaskStatus

try:
    from events.models import PlatformEvent
except ImportError:
    from poc.events.models import PlatformEvent



POC_ROOT = Path(__file__).resolve().parent
DEFAULT_DB_PATH = POC_ROOT / "data" / "agents_platform.db"


class DatabaseManager:
    """Manages SQLite database for persistence."""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            self.db_path = DEFAULT_DB_PATH
        else:
            self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()

    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection."""
        conn = sqlite3.connect(self.db_path)
        # Enable foreign keys
        conn.execute("PRAGMA foreign_keys = ON")
        # Enable WAL mode for better concurrent access
        conn.execute("PRAGMA journal_mode = WAL")
        # Enable busy timeout (5000ms) to prevent immediate locking errors
        conn.execute("PRAGMA busy_timeout = 5000")
        # Return rows as dictionaries
        conn.row_factory = sqlite3.Row
        return conn

    def _init_database(self):
        """Initialize database tables."""
        with self._get_connection() as conn:
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
                ("dangerously_skip_permissions", "INTEGER DEFAULT 0")
            ]:
                try:
                    conn.execute(f"ALTER TABLE agents ADD COLUMN {col} {col_type}")
                except Exception:
                    pass

            conn.execute("CREATE INDEX IF NOT EXISTS idx_agents_parent ON agents(parent_id)")

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

            # Skills table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS skills (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    content TEXT NOT NULL,
                    project_id TEXT,  -- NULL for global skills
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

            # Add delegation, tracing, and session continuation columns to task_runs if not present
            for col, col_type in [
                ("parent_task_id", "TEXT"),
                ("root_task_id", "TEXT"),
                ("assigned_by", "TEXT"),
                ("session_id", "TEXT")
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
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE,
                    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_conversations_agent ON agent_conversations(agent_id, updated_at)")

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

            # Seed default agent templates if table empty
            self._seed_default_templates(conn)

            conn.commit()

    def _seed_default_templates(self, conn: sqlite3.Connection):
        """Seed default reusable agent templates if none exist."""
        cursor = conn.execute("SELECT COUNT(*) FROM agent_templates")
        if cursor.fetchone()[0] > 0:
            return

        defaults = [
            (
                "engineering-manager",
                "Engineering Manager",
                "Coordinates engineering teams, delegates tasks, and synthesizes results.",
                "MANAGER",
                "You are an Engineering Manager. Decompose complex user goals, delegate subtasks to specialized developers, and produce executive summaries of technical work.",
                "default",
                json.dumps(["basic-reading"]),
                json.dumps(["read_files", "grep_search"]),
                json.dumps(["frontend-developer", "backend-developer", "qa-engineer"]),
                "Engineering"
            ),
            (
                "frontend-developer",
                "Frontend Developer",
                "Builds, refactors, and tests modern React, TypeScript, and UI interfaces.",
                "WORKER",
                "You are a Frontend Developer specialized in React 19, TypeScript, Vite, and Ant Design. Build responsive, pixel-perfect, accessible components.",
                "default",
                json.dumps(["basic-reading"]),
                json.dumps(["read_files", "write_to_file", "replace_file_content", "run_command"]),
                json.dumps([]),
                "Engineering"
            ),
            (
                "backend-developer",
                "Backend Developer",
                "Builds scalable Python, FastAPI, and database persistence architectures.",
                "WORKER",
                "You are a Senior Backend Engineer specialized in Python, FastAPI, SQLite, and streaming APIs. Write clean, strongly typed, robust services.",
                "default",
                json.dumps(["basic-reading"]),
                json.dumps(["read_files", "write_to_file", "replace_file_content", "run_command"]),
                json.dumps([]),
                "Engineering"
            ),
            (
                "qa-engineer",
                "QA Engineer",
                "Designs automated test suites, validates acceptance criteria, and verifies zero defects.",
                "SPECIALIST",
                "You are a QA Engineer. Run pytest suites, identify edge cases, write integration tests, and ensure code coverage and regressions are prevented.",
                "default",
                json.dumps(["basic-reading"]),
                json.dumps(["read_files", "run_command"]),
                json.dumps([]),
                "Engineering"
            ),
        ]

        now = datetime.now().isoformat()
        conn.executemany("""
            INSERT INTO agent_templates
            (id, name, description, role, system_prompt, model, skills, tools, suggested_children, category, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [(d[0], d[1], d[2], d[3], d[4], d[5], d[6], d[7], d[8], d[9], now, now) for d in defaults])

    def _row_to_agent(self, row: sqlite3.Row) -> AgentConfig:
        """Convert a database row to an AgentConfig instance."""
        keys = row.keys()
        allowed_children = json.loads(row['allowed_child_ids']) if 'allowed_child_ids' in keys and row['allowed_child_ids'] else []
        allowed_tools = json.loads(row['allowed_tools']) if 'allowed_tools' in keys and row['allowed_tools'] else []

        return AgentConfig(
            id=row['id'],
            name=row['name'],
            description=row['description'],
            system_prompt=row['system_prompt'],
            skills=json.loads(row['skills']) if row['skills'] else [],
            model=row['model'],
            effort=row['effort'],
            max_tokens=row['max_tokens'],
            temperature=row['temperature'],
            repo_path=row['repo_path'] if 'repo_path' in keys else None,
            github_url=row['github_url'] if 'github_url' in keys else None,
            department=row['department'] if 'department' in keys and row['department'] else 'Engineering',
            avatar=row['avatar'] if 'avatar' in keys else None,
            created_at=str(row['created_at']) if 'created_at' in keys and row['created_at'] else None,
            updated_at=str(row['updated_at']) if 'updated_at' in keys and row['updated_at'] else None,
            parent_id=row['parent_id'] if 'parent_id' in keys else None,
            role_type=row['role_type'] if 'role_type' in keys and row['role_type'] else 'WORKER',
            max_concurrent_children=row['max_concurrent_children'] if 'max_concurrent_children' in keys and row['max_concurrent_children'] is not None else 3,
            delegation_strategy=row['delegation_strategy'] if 'delegation_strategy' in keys and row['delegation_strategy'] else 'hierarchical',
            allowed_child_ids=allowed_children,
            allowed_tools=allowed_tools,
            template_id=row['template_id'] if 'template_id' in keys else None,
            dangerously_skip_permissions=bool(row['dangerously_skip_permissions']) if 'dangerously_skip_permissions' in keys and row['dangerously_skip_permissions'] is not None else False
        )

    def _row_to_template(self, row: sqlite3.Row) -> AgentTemplate:
        """Convert a database row to an AgentTemplate instance."""
        return AgentTemplate(
            id=row['id'],
            name=row['name'],
            description=row['description'],
            role=row['role'],
            system_prompt=row['system_prompt'],
            model=row['model'] or 'default',
            skills=json.loads(row['skills']) if row['skills'] else [],
            tools=json.loads(row['tools']) if row['tools'] else [],
            suggested_children=json.loads(row['suggested_children']) if row['suggested_children'] else [],
            category=row['category'] or 'Engineering',
            created_at=str(row['created_at']) if 'created_at' in row.keys() and row['created_at'] else None,
            updated_at=str(row['updated_at']) if 'updated_at' in row.keys() and row['updated_at'] else None
        )

    # Agent methods
    def save_agent(self, agent: AgentConfig):
        """Save or update an agent with organizational hierarchy attributes."""
        with self._get_connection() as conn:
            existing = conn.execute("SELECT created_at FROM agents WHERE id = ?", (agent.id,)).fetchone()
            created_at = existing['created_at'] if existing else (getattr(agent, "created_at", None) or datetime.now().isoformat())
            updated_at = datetime.now().isoformat()

            conn.execute("""
                INSERT INTO agents
                (id, name, description, system_prompt, skills, model, effort, max_tokens, temperature,
                 repo_path, github_url, department, avatar, created_at, updated_at,
                 parent_id, role_type, max_concurrent_children, delegation_strategy,
                 allowed_child_ids, allowed_tools, template_id, dangerously_skip_permissions)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name,
                    description=excluded.description,
                    system_prompt=excluded.system_prompt,
                    skills=excluded.skills,
                    model=excluded.model,
                    effort=excluded.effort,
                    max_tokens=excluded.max_tokens,
                    temperature=excluded.temperature,
                    repo_path=excluded.repo_path,
                    github_url=excluded.github_url,
                    department=excluded.department,
                    avatar=excluded.avatar,
                    updated_at=excluded.updated_at,
                    parent_id=excluded.parent_id,
                    role_type=excluded.role_type,
                    max_concurrent_children=excluded.max_concurrent_children,
                    delegation_strategy=excluded.delegation_strategy,
                    allowed_child_ids=excluded.allowed_child_ids,
                    allowed_tools=excluded.allowed_tools,
                    template_id=excluded.template_id,
                    dangerously_skip_permissions=excluded.dangerously_skip_permissions
            """, (
                agent.id,
                agent.name,
                agent.description,
                agent.system_prompt,
                json.dumps(agent.skills),
                agent.model,
                agent.effort,
                agent.max_tokens,
                agent.temperature,
                getattr(agent, "repo_path", None),
                getattr(agent, "github_url", None),
                getattr(agent, "department", "Engineering"),
                getattr(agent, "avatar", None),
                str(created_at),
                str(updated_at),
                getattr(agent, "parent_id", None),
                getattr(agent, "role_type", "WORKER"),
                getattr(agent, "max_concurrent_children", 3),
                getattr(agent, "delegation_strategy", "hierarchical"),
                json.dumps(getattr(agent, "allowed_child_ids", []) or []),
                json.dumps(getattr(agent, "allowed_tools", []) or []),
                getattr(agent, "template_id", None),
                1 if getattr(agent, "dangerously_skip_permissions", False) else 0
            ))
            conn.commit()

    def get_agent(self, agent_id: str) -> Optional[AgentConfig]:
        """Get an agent by ID."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM agents WHERE id = ?", (agent_id,)
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_agent(row)
        return None

    def list_agents(self) -> List[AgentConfig]:
        """List all agents."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM agents ORDER BY name")
            return [self._row_to_agent(row) for row in cursor.fetchall()]

    def get_child_agents(self, parent_id: str) -> List[AgentConfig]:
        """Get all direct child agents managed by a parent agent."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM agents WHERE parent_id = ? ORDER BY name", (parent_id,))
            return [self._row_to_agent(row) for row in cursor.fetchall()]

    def get_agent_hierarchy(self, root_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Build an organizational hierarchy tree.
        If root_id is provided, returns the subtree rooted at that agent.
        Otherwise, returns all tree hierarchies from root agents (parent_id is NULL).
        """
        all_agents = self.list_agents()
        agents_by_parent: Dict[Optional[str], List[AgentConfig]] = {}
        for a in all_agents:
            pid = a.parent_id
            if pid not in agents_by_parent:
                agents_by_parent[pid] = []
            agents_by_parent[pid].append(a)

        def build_node(agent: AgentConfig) -> Dict[str, Any]:
            node = agent.to_dict()
            node["children"] = [build_node(c) for c in agents_by_parent.get(agent.id, [])]
            return node

        if root_id:
            root = self.get_agent(root_id)
            return [build_node(root)] if root else []

        root_agents = agents_by_parent.get(None, [])
        return [build_node(r) for r in root_agents]

    # Template methods
    def save_template(self, template: AgentTemplate) -> AgentTemplate:
        """Save or update an agent template."""
        with self._get_connection() as conn:
            now = datetime.now().isoformat()
            existing = conn.execute("SELECT created_at FROM agent_templates WHERE id = ?", (template.id,)).fetchone()
            created_at = existing['created_at'] if existing else (template.created_at or now)
            updated_at = now

            conn.execute("""
                INSERT INTO agent_templates
                (id, name, description, role, system_prompt, model, skills, tools, suggested_children, category, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name,
                    description=excluded.description,
                    role=excluded.role,
                    system_prompt=excluded.system_prompt,
                    model=excluded.model,
                    skills=excluded.skills,
                    tools=excluded.tools,
                    suggested_children=excluded.suggested_children,
                    category=excluded.category,
                    updated_at=excluded.updated_at
            """, (
                template.id,
                template.name,
                template.description,
                template.role,
                template.system_prompt,
                template.model,
                json.dumps(template.skills),
                json.dumps(template.tools),
                json.dumps(template.suggested_children),
                template.category,
                str(created_at),
                str(updated_at)
            ))
            conn.commit()
            return self.get_template(template.id) or template

    def get_template(self, template_id: str) -> Optional[AgentTemplate]:
        """Get an agent template by ID."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM agent_templates WHERE id = ?", (template_id,))
            row = cursor.fetchone()
            if row:
                return self._row_to_template(row)
        return None

    def list_templates(self, category: Optional[str] = None) -> List[AgentTemplate]:
        """List agent templates, optionally filtered by category."""
        with self._get_connection() as conn:
            if category:
                cursor = conn.execute("SELECT * FROM agent_templates WHERE category = ? ORDER BY name", (category,))
            else:
                cursor = conn.execute("SELECT * FROM agent_templates ORDER BY name")
            return [self._row_to_template(row) for row in cursor.fetchall()]

    def delete_template(self, template_id: str) -> bool:
        """Delete an agent template."""
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM agent_templates WHERE id = ?", (template_id,))
            conn.commit()
            return cursor.rowcount > 0

    def delete_agent(self, agent_id: str):
        """Delete an agent and clean up any linked task runs and hierarchy relationships."""
        with self._get_connection() as conn:
            conn.execute("UPDATE agents SET parent_id = NULL WHERE parent_id = ?", (agent_id,))
            conn.execute("DELETE FROM task_runs WHERE agent_id = ?", (agent_id,))
            conn.execute("DELETE FROM agents WHERE id = ?", (agent_id,))
            conn.commit()

    # Project methods
    def save_project(self, project: ProjectConfig):
        """Save or update a project."""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO projects
                (id, name, description, working_directory, instructions, skills, allowed_tools, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                project.id,
                project.name,
                project.description,
                project.working_directory,
                project.instructions,
                json.dumps(project.skills),
                json.dumps(project.allowed_tools),
                datetime.now()
            ))
            conn.commit()

    def get_project(self, project_id: str) -> Optional[ProjectConfig]:
        """Get a project by ID."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM projects WHERE id = ?", (project_id,)
            )
            row = cursor.fetchone()
            if row:
                return ProjectConfig(
                    id=row['id'],
                    name=row['name'],
                    description=row['description'],
                    working_directory=row['working_directory'],
                    instructions=row['instructions'],
                    skills=json.loads(row['skills']) if row['skills'] else [],
                    allowed_tools=json.loads(row['allowed_tools']) if row['allowed_tools'] else []
                )
        return None

    def list_projects(self) -> List[ProjectConfig]:
        """List all projects."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM projects ORDER BY name")
            return [
                ProjectConfig(
                    id=row['id'],
                    name=row['name'],
                    description=row['description'],
                    working_directory=row['working_directory'],
                    instructions=row['instructions'],
                    skills=json.loads(row['skills']) if row['skills'] else [],
                    allowed_tools=json.loads(row['allowed_tools']) if row['allowed_tools'] else []
                )
                for row in cursor.fetchall()
            ]

    def delete_project(self, project_id: str):
        """Delete a project."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            conn.commit()

    # Skill methods
    def save_skill(self, skill: Skill):
        """Save or update a skill."""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO skills
                (id, name, description, content, project_id, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                skill.id,
                skill.name,
                skill.description,
                skill.content,
                skill.project_id,
                datetime.now()
            ))
            conn.commit()

    def get_skill(self, skill_id: str) -> Optional[Skill]:
        """Get a skill by ID."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM skills WHERE id = ?", (skill_id,)
            )
            row = cursor.fetchone()
            if row:
                return Skill(
                    id=row['id'],
                    name=row['name'],
                    description=row['description'],
                    content=row['content'],
                    project_id=row['project_id']
                )
        return None

    def list_skills(self, project_id: Optional[str] = None) -> List[Skill]:
        """List skills, optionally filtered by project."""
        with self._get_connection() as conn:
            if project_id is not None:
                cursor = conn.execute(
                    "SELECT * FROM skills WHERE project_id = ? OR project_id IS NULL ORDER BY name",
                    (project_id,)
                )
            else:
                cursor = conn.execute("SELECT * FROM skills ORDER BY name")
            return [
                Skill(
                    id=row['id'],
                    name=row['name'],
                    description=row['description'],
                    content=row['content'],
                    project_id=row['project_id']
                )
                for row in cursor.fetchall()
            ]

    def delete_skill(self, skill_id: str):
        """Delete a skill."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM skills WHERE id = ?", (skill_id,))
            conn.commit()

    # Task run methods
    def _row_to_task_run(self, row: sqlite3.Row) -> AgentRun:
        """Convert a database row to an AgentRun object."""
        keys = row.keys() if hasattr(row, "keys") else []
        return AgentRun(
            run_id=row['run_id'],
            agent_id=row['agent_id'],
            project_id=row['project_id'],
            prompt=row['prompt'],
            status=TaskStatus(row['status']),
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
            started_at=datetime.fromisoformat(row['started_at']) if row['started_at'] else None,
            ended_at=datetime.fromisoformat(row['ended_at']) if row['ended_at'] else None,
            result=row['result'],
            error=row['error'],
            exit_code=row['exit_code'],
            events=json.loads(row['events']) if row['events'] else [],
            parent_task_id=row['parent_task_id'] if 'parent_task_id' in keys else None,
            root_task_id=row['root_task_id'] if 'root_task_id' in keys else None,
            assigned_by=row['assigned_by'] if 'assigned_by' in keys else None,
            session_id=row['session_id'] if 'session_id' in keys else None
        )

    def save_task_run(self, run: AgentRun):
        """Save or update a task run."""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO task_runs
                (run_id, agent_id, project_id, prompt, status, created_at, started_at, ended_at,
                 result, error, exit_code, events, parent_task_id, root_task_id, assigned_by, session_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                run.run_id,
                run.agent_id,
                run.project_id,
                run.prompt,
                run.status.value if hasattr(run.status, "value") else str(run.status),
                run.created_at.isoformat() if run.created_at else None,
                run.started_at.isoformat() if run.started_at else None,
                run.ended_at.isoformat() if run.ended_at else None,
                run.result,
                run.error,
                run.exit_code,
                json.dumps(run.events) if run.events else None,
                getattr(run, "parent_task_id", None),
                getattr(run, "root_task_id", None),
                getattr(run, "assigned_by", None),
                getattr(run, "session_id", None)
            ))
            conn.commit()

    def get_task_run(self, run_id: str) -> Optional[AgentRun]:
        """Get a task run by ID."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM task_runs WHERE run_id = ?", (run_id,)
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_task_run(row)
        return None

    def update_task_run(
        self,
        run_id: str,
        status: Optional[TaskStatus] = None,
        error: Optional[str] = None,
        result: Optional[str] = None
    ) -> Optional[AgentRun]:
        """Update specific fields of an existing task run."""
        fields = []
        params = []
        if status is not None:
            fields.append("status = ?")
            params.append(status.value if hasattr(status, "value") else str(status))
        if error is not None:
            fields.append("error = ?")
            params.append(error)
        if result is not None:
            fields.append("result = ?")
            params.append(result)

        if not fields:
            return self.get_task_run(run_id)

        params.append(run_id)
        query = f"UPDATE task_runs SET {', '.join(fields)} WHERE run_id = ?"
        with self._get_connection() as conn:
            conn.execute(query, params)
            conn.commit()

        return self.get_task_run(run_id)


    def list_task_runs(
        self,
        agent_id: Optional[str] = None,
        project_id: Optional[str] = None,
        status: Optional[TaskStatus] = None,
        limit: int = 100
    ) -> List[AgentRun]:
        """List task runs with optional filtering."""
        with self._get_connection() as conn:
            query = "SELECT * FROM task_runs WHERE 1=1"
            params = []

            if agent_id:
                query += " AND agent_id = ?"
                params.append(agent_id)
            if project_id:
                query += " AND project_id = ?"
                params.append(project_id)
            if status:
                query += " AND status = ?"
                params.append(status.value if hasattr(status, "value") else str(status))

            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)

            cursor = conn.execute(query, params)
            return [self._row_to_task_run(row) for row in cursor.fetchall()]

    def delete_task_run(self, run_id: str):
        """Delete a task run and any child subtasks."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM task_runs WHERE parent_task_id = ?", (run_id,))
            conn.execute("DELETE FROM task_runs WHERE run_id = ?", (run_id,))
            conn.commit()

    def get_subtasks(self, parent_task_id: str) -> List[AgentRun]:
        """Query subtasks for a parent task."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM task_runs WHERE parent_task_id = ? ORDER BY created_at ASC",
                (parent_task_id,)
            )
            return [self._row_to_task_run(row) for row in cursor.fetchall()]

    def get_task_tree(self, root_task_id: str) -> Dict[str, Any]:
        """
        Build a nested recursive dictionary representing the task tree rooted at root_task_id.
        Each node contains task run fields and a 'children' list of child nodes.
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                """SELECT * FROM task_runs
                   WHERE run_id = ? OR root_task_id = ? OR parent_task_id = ?
                   ORDER BY created_at ASC""",
                (root_task_id, root_task_id, root_task_id)
            )
            rows = cursor.fetchall()

        if not rows:
            return {}

        nodes: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            run = self._row_to_task_run(row)
            node = run.to_dict()
            node["children"] = []
            nodes[run.run_id] = node

        root_node = nodes.get(root_task_id)
        if not root_node:
            for node in nodes.values():
                if not node.get("parent_task_id") or node.get("parent_task_id") not in nodes:
                    root_node = node
                    break
            if not root_node:
                return {}

        for run_id, node in nodes.items():
            if run_id == root_node["run_id"]:
                continue
            parent_id = node.get("parent_task_id")
            if parent_id and parent_id in nodes:
                nodes[parent_id]["children"].append(node)

        return root_node

    def count_active_subtasks_for_parent(self, parent_agent_id: str) -> int:
        """Count active subtasks (running or pending) assigned by a parent agent."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM task_runs WHERE assigned_by = ? AND LOWER(status) IN ('running', 'pending')",
                (parent_agent_id,)
            )
            row = cursor.fetchone()
            return int(row[0]) if row else 0

    # Event log methods
    def get_next_sequence_number(self) -> int:
        """Query SELECT COALESCE(MAX(sequence_number), 0) + 1 FROM event_log."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT COALESCE(MAX(sequence_number), 0) + 1 AS next_seq FROM event_log")
            row = cursor.fetchone()
            return int(row["next_seq"]) if row else 1

    def save_event(self, event: PlatformEvent) -> PlatformEvent:
        """
        Save an event to the persistent event log.
        If event.sequence_number <= 0, assign self.get_next_sequence_number().
        Insert row into event_log. Commit and return event.
        """
        if event.sequence_number <= 0:
            event.sequence_number = self.get_next_sequence_number()

        event_id = getattr(event, "event_id", None) or getattr(event, "id", None) or str(uuid.uuid4())
        event.event_id = event_id

        payload_str = json.dumps(event.payload) if isinstance(event.payload, (dict, list)) else (
            event.payload if isinstance(event.payload, str) else "{}"
        )
        event_type_str = event.event_type.value if hasattr(event.event_type, "value") else str(event.event_type)
        timestamp_str = event.timestamp.isoformat() if isinstance(event.timestamp, datetime) else str(event.timestamp)

        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO event_log (
                    id, sequence_number, event_type, agent_id, task_id, execution_id,
                    parent_task_id, project_id, correlation_id, payload, source, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event.event_id,
                event.sequence_number,
                event_type_str,
                event.agent_id,
                event.task_id,
                event.execution_id,
                event.parent_task_id,
                event.project_id,
                event.correlation_id,
                payload_str,
                event.source,
                timestamp_str
            ))
            conn.commit()

        return event

    def get_events(
        self,
        agent_id: Optional[str] = None,
        task_id: Optional[str] = None,
        project_id: Optional[str] = None,
        after_sequence: Optional[int] = None,
        since: Optional[Union[str, datetime]] = None,
        limit: int = 100
    ) -> List[PlatformEvent]:
        """
        Query event_log with appropriate WHERE clauses, order by sequence_number ASC, limit.
        Return list of PlatformEvent.
        """
        with self._get_connection() as conn:
            query = "SELECT * FROM event_log WHERE 1=1"
            params: List[Any] = []

            if agent_id is not None:
                query += " AND agent_id = ?"
                params.append(agent_id)
            if task_id is not None:
                query += " AND task_id = ?"
                params.append(task_id)
            if project_id is not None:
                query += " AND project_id = ?"
                params.append(project_id)
            if after_sequence is not None:
                query += " AND sequence_number > ?"
                params.append(after_sequence)
            if since is not None:
                since_str = since.isoformat() if isinstance(since, datetime) else str(since)
                query += " AND timestamp >= ?"
                params.append(since_str)

            query += " ORDER BY sequence_number ASC LIMIT ?"
            params.append(limit)

            cursor = conn.execute(query, params)
            events: List[PlatformEvent] = []
            for row in cursor.fetchall():
                payload = json.loads(row["payload"]) if row["payload"] else {}
                events.append(PlatformEvent(
                    event_id=row["id"],
                    sequence_number=row["sequence_number"],
                    event_type=row["event_type"],
                    agent_id=row["agent_id"],
                    task_id=row["task_id"],
                    execution_id=row["execution_id"],
                    parent_task_id=row["parent_task_id"],
                    project_id=row["project_id"],
                    correlation_id=row["correlation_id"],
                    payload=payload,
                    source=row["source"],
                    timestamp=str(row["timestamp"])
                ))
            return events

    # Audit logging methods
    def log_audit(
        self,
        action: str,
        actor: str,
        entity_type: str,
        entity_id: str,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Record an immutable security audit trail event."""
        log_id = f"aud_{uuid.uuid4().hex[:12]}"
        now = datetime.now().isoformat()
        details_json = json.dumps(details) if details is not None else None
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO audit_logs
                (id, action, actor, entity_type, entity_id, details, ip_address, correlation_id, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (log_id, action, actor, entity_type, entity_id, details_json, ip_address, correlation_id, now))
            conn.commit()

        return {
            "id": log_id,
            "action": action,
            "actor": actor,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "details": details,
            "ip_address": ip_address,
            "correlation_id": correlation_id,
            "timestamp": now
        }

    def get_audit_logs(
        self,
        limit: int = 100,
        entity_type: Optional[str] = None,
        action: Optional[str] = None,
        actor: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve security audit logs with optional filters."""
        query = "SELECT * FROM audit_logs WHERE 1=1"
        params: List[Any] = []
        if entity_type:
            query += " AND entity_type = ?"
            params.append(entity_type)
        if action:
            query += " AND action = ?"
            params.append(action)
        if actor:
            query += " AND actor = ?"
            params.append(actor)
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            res = []
            for r in rows:
                details = None
                if r['details']:
                    try:
                        details = json.loads(r['details'])
                    except Exception:
                        details = r['details']
                res.append({
                    "id": r['id'],
                    "action": r['action'],
                    "actor": r['actor'],
                    "entity_type": r['entity_type'],
                    "entity_id": r['entity_id'],
                    "details": details,
                    "ip_address": r['ip_address'],
                    "correlation_id": r['correlation_id'],
                    "timestamp": str(r['timestamp'])
                })
            return res

    # -------------------------------------------------------------
    # Cron Jobs persistence methods
    # -------------------------------------------------------------
    def create_cron_job(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Save a new scheduled cron job."""
        job_id = job_data.get('id') or f"cron_{uuid.uuid4().hex[:12]}"
        now = datetime.now().isoformat()
        input_data = job_data.get('input_data')
        input_str = json.dumps(input_data) if isinstance(input_data, (dict, list)) else input_data

        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO cron_jobs (
                    id, name, description, cron_expression, agent_id, project_id,
                    prompt, input_data, enabled, concurrency_policy, misfire_policy,
                    timezone, next_run_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job_id,
                job_data['name'],
                job_data.get('description'),
                job_data['cron_expression'],
                job_data['agent_id'],
                job_data.get('project_id'),
                job_data['prompt'],
                input_str,
                1 if job_data.get('enabled', True) else 0,
                job_data.get('concurrency_policy', 'SKIP'),
                job_data.get('misfire_policy', 'RUN_ONCE'),
                job_data.get('timezone', 'UTC'),
                job_data['next_run_at'],
                now,
                now
            ))
            conn.commit()

        return self.get_cron_job(job_id)

    def get_cron_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get a scheduled cron job by ID."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM cron_jobs WHERE id = ?", (job_id,)).fetchone()
            if not row:
                return None
            res = dict(row)
            res['enabled'] = bool(res['enabled'])
            if res.get('input_data'):
                try:
                    res['input_data'] = json.loads(res['input_data'])
                except Exception:
                    pass
            return res

    def list_cron_jobs(
        self,
        agent_id: Optional[str] = None,
        project_id: Optional[str] = None,
        enabled: Optional[bool] = None
    ) -> List[Dict[str, Any]]:
        """List scheduled cron jobs with optional filters."""
        query = "SELECT * FROM cron_jobs WHERE 1=1"
        params: List[Any] = []
        if agent_id:
            query += " AND agent_id = ?"
            params.append(agent_id)
        if project_id:
            query += " AND project_id = ?"
            params.append(project_id)
        if enabled is not None:
            query += " AND enabled = ?"
            params.append(1 if enabled else 0)
        query += " ORDER BY next_run_at ASC"

        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            jobs = []
            for r in rows:
                j = dict(r)
                j['enabled'] = bool(j['enabled'])
                if j.get('input_data'):
                    try:
                        j['input_data'] = json.loads(j['input_data'])
                    except Exception:
                        pass
                jobs.append(j)
            return jobs

    def update_cron_job(self, job_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update properties of an existing cron job."""
        fields = []
        params = []
        now = datetime.now().isoformat()

        for k, v in updates.items():
            if k in ['name', 'description', 'cron_expression', 'agent_id', 'project_id',
                     'prompt', 'concurrency_policy', 'misfire_policy', 'timezone',
                     'last_run_at', 'last_run_id', 'last_status', 'next_run_at']:
                fields.append(f"{k} = ?")
                params.append(v)
            elif k == 'enabled':
                fields.append("enabled = ?")
                params.append(1 if v else 0)
            elif k == 'input_data':
                fields.append("input_data = ?")
                params.append(json.dumps(v) if isinstance(v, (dict, list)) else v)

        if not fields:
            return self.get_cron_job(job_id)

        fields.append("updated_at = ?")
        params.append(now)
        params.append(job_id)

        query = f"UPDATE cron_jobs SET {', '.join(fields)} WHERE id = ?"
        with self._get_connection() as conn:
            conn.execute(query, params)
            conn.commit()

        return self.get_cron_job(job_id)

    def delete_cron_job(self, job_id: str) -> bool:
        """Delete a scheduled cron job."""
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM cron_jobs WHERE id = ?", (job_id,))
            conn.commit()
            return cursor.rowcount > 0

    def get_due_cron_jobs(self, current_time_iso: str) -> List[Dict[str, Any]]:
        """Find enabled cron jobs that are due for execution (next_run_at <= current_time)."""
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM cron_jobs 
                WHERE enabled = 1 AND next_run_at <= ?
                ORDER BY next_run_at ASC
            """, (current_time_iso,)).fetchall()
            jobs = []
            for r in rows:
                j = dict(r)
                j['enabled'] = bool(j['enabled'])
                if j.get('input_data'):
                    try:
                        j['input_data'] = json.loads(j['input_data'])
                    except Exception:
                        pass
                jobs.append(j)
            return jobs

    # -------------------------------------------------------------
    # Agent Interactions & Approvals persistence methods
    # -------------------------------------------------------------
    def create_interaction(self, interaction_data: Dict[str, Any]) -> Dict[str, Any]:
        """Save a new question or approval request from an agent."""
        interaction_id = interaction_data.get('id') or f"inter_{uuid.uuid4().hex[:12]}"
        now = datetime.now().isoformat()
        ctx_data = interaction_data.get('context_data')
        ctx_str = json.dumps(ctx_data) if isinstance(ctx_data, (dict, list)) else ctx_data

        init_status = interaction_data.get('status', 'PENDING')
        res_resp = interaction_data.get('resolution_response')
        res_by = interaction_data.get('resolved_by')

        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO agent_interactions (
                    id, task_id, requester_agent_id, target_approver_id,
                    interaction_type, title, content, context_data,
                    status, resolution_response, resolved_by, created_at, resolved_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                interaction_id,
                interaction_data['task_id'],
                interaction_data['requester_agent_id'],
                interaction_data['target_approver_id'],
                interaction_data.get('interaction_type', 'QUESTION'),
                interaction_data['title'],
                interaction_data['content'],
                ctx_str,
                init_status,
                res_resp,
                res_by,
                now,
                now if init_status != 'PENDING' else None
            ))
            conn.commit()

        return self.get_interaction(interaction_id)

    def get_interaction(self, interaction_id: str) -> Optional[Dict[str, Any]]:
        """Get an interaction by ID."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM agent_interactions WHERE id = ?", (interaction_id,)).fetchone()
            if not row:
                return None
            res = dict(row)
            if res.get('context_data'):
                try:
                    res['context_data'] = json.loads(res['context_data'])
                except Exception:
                    pass
            return res

    def list_interactions(
        self,
        task_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        target_approver_id: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List interactions / pending approvals with filters."""
        query = "SELECT * FROM agent_interactions WHERE 1=1"
        params: List[Any] = []
        if task_id:
            query += " AND task_id = ?"
            params.append(task_id)
        if agent_id:
            query += " AND requester_agent_id = ?"
            params.append(agent_id)
        if target_approver_id:
            query += " AND target_approver_id = ?"
            params.append(target_approver_id)
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY created_at DESC"

        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            items = []
            for r in rows:
                item = dict(r)
                if item.get('context_data'):
                    try:
                        item['context_data'] = json.loads(item['context_data'])
                    except Exception:
                        pass
                items.append(item)
            return items

    def resolve_interaction(
        self,
        interaction_id: str,
        resolution_response: str,
        resolved_by: str,
        decision: str = 'RESOLVED'
    ) -> Optional[Dict[str, Any]]:
        """Mark an interaction as resolved or rejected with a response."""
        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            conn.execute("""
                UPDATE agent_interactions
                SET status = ?, resolution_response = ?, resolved_by = ?, resolved_at = ?
                WHERE id = ?
            """, (decision, resolution_response, resolved_by, now, interaction_id))
            conn.commit()

        return self.get_interaction(interaction_id)

    # -------------------------------------------------------------
    # Agent Conversations & Chat Messages persistence methods
    # -------------------------------------------------------------
    def get_or_create_conversation(self, agent_id: str, project_id: Optional[str] = None) -> Dict[str, Any]:
        """Get the active conversation for an agent, or create a new one."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM agent_conversations WHERE agent_id = ? ORDER BY updated_at DESC LIMIT 1",
                (agent_id,)
            ).fetchone()

            if row:
                return dict(row)

            conv_id = f"conv_{uuid.uuid4().hex[:12]}"
            now = datetime.now().isoformat()
            conn.execute("""
                INSERT INTO agent_conversations (id, agent_id, project_id, title, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (conv_id, agent_id, project_id, f"Chat with {agent_id}", now, now))
            conn.commit()

            return {
                "id": conv_id,
                "agent_id": agent_id,
                "project_id": project_id,
                "title": f"Chat with {agent_id}",
                "claude_session_id": None,
                "created_at": now,
                "updated_at": now
            }

    def update_conversation_session(self, conversation_id: str, claude_session_id: str):
        """Associate a Claude CLI session ID with the conversation."""
        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            conn.execute("""
                UPDATE agent_conversations
                SET claude_session_id = ?, updated_at = ?
                WHERE id = ?
            """, (claude_session_id, now, conversation_id))
            conn.commit()

    def save_chat_message(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Save a new chat message, thought, or tool call."""
        msg_id = message_data.get('id') or f"msg_{uuid.uuid4().hex[:12]}"
        now = datetime.now().isoformat()
        meta = message_data.get('metadata')
        meta_str = json.dumps(meta) if isinstance(meta, (dict, list)) else meta

        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO chat_messages (
                    id, conversation_id, agent_id, task_id,
                    sender_type, message_type, content, metadata, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                msg_id,
                message_data['conversation_id'],
                message_data['agent_id'],
                message_data.get('task_id'),
                message_data.get('sender_type', 'USER'),
                message_data.get('message_type', 'CHAT'),
                message_data['content'],
                meta_str,
                now
            ))
            # Also touch updated_at on the conversation
            conn.execute(
                "UPDATE agent_conversations SET updated_at = ? WHERE id = ?",
                (now, message_data['conversation_id'])
            )
            conn.commit()

            return {
                "id": msg_id,
                "conversation_id": message_data['conversation_id'],
                "agent_id": message_data['agent_id'],
                "task_id": message_data.get('task_id'),
                "sender_type": message_data.get('sender_type', 'USER'),
                "message_type": message_data.get('message_type', 'CHAT'),
                "content": message_data['content'],
                "metadata": meta,
                "created_at": now
            }

    def get_chat_history(self, agent_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Retrieve recent chat history for an agent."""
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM chat_messages
                WHERE agent_id = ?
                ORDER BY created_at ASC
                LIMIT ?
            """, (agent_id, limit)).fetchall()

            res = []
            for r in rows:
                item = dict(r)
                if item.get('metadata'):
                    try:
                        item['metadata'] = json.loads(item['metadata'])
                    except Exception:
                        pass
                res.append(item)
            return res

    def clear_chat_history(self, agent_id: str):
        """Clear all messages and start fresh for an agent."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM chat_messages WHERE agent_id = ?", (agent_id,))
            conn.execute("DELETE FROM agent_conversations WHERE agent_id = ?", (agent_id,))
            conn.commit()

    # -------------------------------------------------------------
    # Project Shared Memory persistence methods
    # -------------------------------------------------------------
    def create_project_memory(self, memory_data: Dict[str, Any]) -> Dict[str, Any]:
        """Save a new knowledge insight, ADR, or convention to the project memory."""
        mem_id = memory_data.get('id') or f"mem_{uuid.uuid4().hex[:12]}"
        now = datetime.now().isoformat()
        tags = memory_data.get('tags')
        tags_str = json.dumps(tags) if isinstance(tags, (list, dict)) else tags

        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO project_memories (
                    id, project_id, category, title, content, tags, author_agent_id, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                mem_id,
                memory_data['project_id'],
                memory_data.get('category', 'INSIGHT'),
                memory_data['title'],
                memory_data['content'],
                tags_str,
                memory_data.get('author_agent_id'),
                now,
                now
            ))
            conn.commit()

        return self.get_project_memory(mem_id)

    def get_project_memory(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a specific memory item by ID."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM project_memories WHERE id = ?", (memory_id,)).fetchone()
            if not row:
                return None
            res = dict(row)
            if res.get('tags'):
                try:
                    res['tags'] = json.loads(res['tags'])
                except Exception:
                    pass
            return res

    def list_project_memories(
        self,
        project_id: str,
        category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List shared memories for a project."""
        query = "SELECT * FROM project_memories WHERE project_id = ?"
        params: List[Any] = [project_id]
        if category:
            query += " AND category = ?"
            params.append(category)
        query += " ORDER BY updated_at DESC"

        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            items = []
            for r in rows:
                item = dict(r)
                if item.get('tags'):
                    try:
                        item['tags'] = json.loads(item['tags'])
                    except Exception:
                        pass
                items.append(item)
            return items

    def delete_project_memory(self, memory_id: str) -> bool:
        """Delete a shared memory item."""
        with self._get_connection() as conn:
            cur = conn.execute("DELETE FROM project_memories WHERE id = ?", (memory_id,))
            conn.commit()
            return cur.rowcount > 0

    # -------------------------------------------------------------
    # War Room Sessions & Messages persistence methods
    # -------------------------------------------------------------
    def create_war_room_session(self, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new multi-agent war room session."""
        session_id = session_data.get('id') or f"wr_{uuid.uuid4().hex[:12]}"
        now = datetime.now().isoformat()
        participants = session_data.get('participant_agent_ids', [])
        part_str = json.dumps(participants) if isinstance(participants, list) else participants

        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO war_room_sessions (
                    id, title, topic, project_id, moderator_agent_id, participant_agent_ids, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id,
                session_data['title'],
                session_data['topic'],
                session_data.get('project_id'),
                session_data['moderator_agent_id'],
                part_str,
                session_data.get('status', 'GATHERING'),
                now,
                now
            ))
            conn.commit()

        return self.get_war_room_session(session_id)

    def get_war_room_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get war room session details by ID."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM war_room_sessions WHERE id = ?", (session_id,)).fetchone()
            if not row:
                return None
            res = dict(row)
            if res.get('participant_agent_ids'):
                try:
                    res['participant_agent_ids'] = json.loads(res['participant_agent_ids'])
                except Exception:
                    pass
            return res

    def list_war_room_sessions(self, project_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List war room sessions."""
        query = "SELECT * FROM war_room_sessions WHERE 1=1"
        params: List[Any] = []
        if project_id:
            query += " AND project_id = ?"
            params.append(project_id)
        query += " ORDER BY updated_at DESC"

        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            items = []
            for r in rows:
                item = dict(r)
                if item.get('participant_agent_ids'):
                    try:
                        item['participant_agent_ids'] = json.loads(item['participant_agent_ids'])
                    except Exception:
                        pass
                items.append(item)
            return items

    def update_war_room_session(self, session_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update war room status or synthesized plan."""
        fields = []
        params = []
        now = datetime.now().isoformat()

        for k, v in updates.items():
            if k in ['status', 'synthesized_plan', 'topic', 'title']:
                fields.append(f"{k} = ?")
                params.append(v)
            elif k == 'participant_agent_ids':
                fields.append("participant_agent_ids = ?")
                params.append(json.dumps(v) if isinstance(v, list) else v)

        if not fields:
            return self.get_war_room_session(session_id)

        fields.append("updated_at = ?")
        params.append(now)
        params.append(session_id)

        with self._get_connection() as conn:
            conn.execute(f"UPDATE war_room_sessions SET {', '.join(fields)} WHERE id = ?", params)
            conn.commit()

        return self.get_war_room_session(session_id)

    def add_war_room_message(self, msg_data: Dict[str, Any]) -> Dict[str, Any]:
        """Add a dialogue message or proposal to a war room session."""
        msg_id = msg_data.get('id') or f"wrmsg_{uuid.uuid4().hex[:12]}"
        now = datetime.now().isoformat()

        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO war_room_messages (
                    id, session_id, agent_id, round_number, message_type, content, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                msg_id,
                msg_data['session_id'],
                msg_data['agent_id'],
                msg_data.get('round_number', 1),
                msg_data.get('message_type', 'PROPOSAL'),
                msg_data['content'],
                now
            ))
            # Touch session
            conn.execute("UPDATE war_room_sessions SET updated_at = ? WHERE id = ?", (now, msg_data['session_id']))
            conn.commit()

        return {
            "id": msg_id,
            "session_id": msg_data['session_id'],
            "agent_id": msg_data['agent_id'],
            "round_number": msg_data.get('round_number', 1),
            "message_type": msg_data.get('message_type', 'PROPOSAL'),
            "content": msg_data['content'],
            "created_at": now
        }

    def get_war_room_messages(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all messages in a war room session chronologically."""
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM war_room_messages
                WHERE session_id = ?
                ORDER BY round_number ASC, created_at ASC
            """, (session_id,)).fetchall()
            return [dict(r) for r in rows]




# Global database instance
db_manager = DatabaseManager()