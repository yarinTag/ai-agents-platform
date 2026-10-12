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
from typing import List, Optional, Dict, Any, Union, Iterator
from contextlib import contextmanager
from pathlib import Path

from dataclasses import dataclass, asdict, field

# Import from local modules using absolute imports
from config import AgentConfig, ProjectConfig, Skill, AgentTemplate, SuperAgentConfig, AgentRole
from runtime_adapter import AgentRun, TaskStatus

try:
    from events.models import PlatformEvent
except ImportError:
    from poc.events.models import PlatformEvent


@dataclass
class AgentMessage:
    """First-class internal agent-to-agent message."""
    id: str
    from_agent_id: str
    to_agent_id: str
    content: str
    task_id: Optional[str] = None
    run_id: Optional[str] = None
    parent_message_id: Optional[str] = None
    message_type: str = "QUESTION"  # QUESTION, ANSWER, REQUEST, DELEGATION, STATUS, RESULT, HANDOFF
    status: str = "SENT"  # SENT, DELIVERED, READ, ANSWERED, FAILED
    metadata: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None
    responded_at: Optional[str] = None
    channel_key: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AgentMessage':
        import inspect
        valid_fields = set(inspect.signature(cls).parameters.keys())
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered)


@dataclass
class MCPConnector:
    """Represents a connected Model Context Protocol server/service."""
    id: str
    name: str
    provider: str
    status: str = "DISCONNECTED"  # CONNECTED, DISCONNECTED, ERROR
    configuration: Optional[Dict[str, Any]] = None
    capabilities: Optional[List[str]] = None
    error_message: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MCPTool:
    """An individual tool exposed by an MCP connector."""
    id: str
    connector_id: str
    name: str
    description: str
    input_schema: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MCPToolCall:
    """Historical and active record of an MCP tool invocation."""
    id: str
    connector_id: str
    tool_id: str
    agent_id: str
    task_id: Optional[str] = None
    run_id: Optional[str] = None
    status: str = "STARTED"  # STARTED, COMPLETED, FAILED
    arguments: Optional[Dict[str, Any]] = None
    result: Optional[str] = None
    error: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AgentTeam:
    """A collaborative team of agents coordinated by a manager."""
    id: str
    name: str
    manager_agent_id: str
    project_id: Optional[str] = None
    description: Optional[str] = None
    status: str = "ACTIVE"  # ACTIVE, COMPLETED, DISBANDED
    members: Optional[List[Dict[str, Any]]] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Department:
    """Organizational department with budget controls."""
    id: str
    name: str
    description: Optional[str] = None
    monthly_budget_usd: float = 100.0
    current_spend_usd: float = 0.0
    budget_action: str = "REQUIRE_APPROVAL"  # HARD_STOP, REQUIRE_APPROVAL, NOTIFY_ONLY
    alert_threshold_pct: float = 80.0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Workflow:
    """Autonomous agentic workflow definition."""
    id: str
    name: str
    description: Optional[str] = None
    department_id: Optional[str] = None
    definition_json: str = "{}"
    webhook_enabled: bool = True
    webhook_token: Optional[str] = None
    cron_expression: Optional[str] = None
    is_active: bool = True
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class WorkflowExecution:
    """Single execution instance of a workflow."""
    id: str
    workflow_id: str
    trigger_type: str  # WEBHOOK, CRON, MANUAL, META_ORCHESTRATOR
    trigger_payload: Optional[str] = None
    status: str = "PENDING"  # PENDING, RUNNING, WAITING_APPROVAL, COMPLETED, FAILED, CANCELLED
    department_id: Optional[str] = None
    sandbox_path: Optional[str] = None
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None
    created_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class WorkflowStepRun:
    """Execution record for an individual step within a workflow."""
    id: str
    execution_id: str
    step_key: str
    agent_id: Optional[str] = None
    status: str = "PENDING"
    task_run_id: Optional[str] = None
    input_data: Optional[str] = None
    output_data: Optional[str] = None
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RunEvaluation:
    """Feedback and lesson learned from a workflow execution."""
    id: str
    execution_id: str
    workflow_id: str
    rating: Optional[int] = None
    feedback_notes: Optional[str] = None
    lessons_extracted: Optional[str] = None
    created_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


POC_ROOT = Path(__file__).resolve().parent
DEFAULT_DB_PATH = POC_ROOT / "data" / "agents_platform.db"


class DatabaseManager:
    """Manages SQLite database for persistence."""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            self.db_path = DEFAULT_DB_PATH
        else:
            self.db_path = Path(db_path)
        self.max_agents: int = int(os.getenv("PLATFORM_MAX_AGENTS", "18"))
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()

    @contextmanager
    def _get_connection(self) -> Iterator[sqlite3.Connection]:
        """
        Yield a database connection, then always close it.

        Mirrors sqlite3's own ``with conn:`` semantics (commit on success,
        rollback on exception) and additionally closes the connection on the
        way out. Closing is required: sqlite3's connection context manager
        ends the transaction but never releases the underlying handle, so
        every call used to leak a file descriptor and a WAL read lock (which
        also prevents the -wal file from ever being checkpointed).
        """
        conn = sqlite3.connect(self.db_path)
        try:
            # Enable foreign keys
            conn.execute("PRAGMA foreign_keys = ON")
            # Enable WAL mode for better concurrent access
            conn.execute("PRAGMA journal_mode = WAL")
            # Enable busy timeout (5000ms) to prevent immediate locking errors
            conn.execute("PRAGMA busy_timeout = 5000")
            # Return rows as dictionaries
            conn.row_factory = sqlite3.Row
            try:
                yield conn
            except BaseException:
                conn.rollback()
                raise
            else:
                conn.commit()
        finally:
            conn.close()

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
                ("dangerously_skip_permissions", "INTEGER DEFAULT 0"),
                ("allow_sibling_communication", "INTEGER DEFAULT 1"),
                ("allowed_peer_ids", "TEXT"),
                ("mcp_permissions", "TEXT"),
                ("runtime_provider", "TEXT"),
                ("is_workflow_agent", "INTEGER DEFAULT 0"),
                ("workflow_id", "TEXT")
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

            # Add delegation, tracing, dependencies, structured result, and session continuation columns to task_runs if not present
            for col, col_type in [
                ("parent_task_id", "TEXT"),
                ("root_task_id", "TEXT"),
                ("assigned_by", "TEXT"),
                ("session_id", "TEXT"),
                ("dependencies", "TEXT"),
                ("structured_result", "TEXT"),
                ("acceptance_criteria", "TEXT"),
                ("retry_count", "INTEGER DEFAULT 0"),
                ("input_tokens", "INTEGER DEFAULT 0"),
                ("output_tokens", "INTEGER DEFAULT 0"),
                ("cache_read_tokens", "INTEGER DEFAULT 0"),
                ("cache_write_tokens", "INTEGER DEFAULT 0"),
                ("cost_usd", "REAL DEFAULT 0.0"),
                ("cost_source", "TEXT DEFAULT 'UNKNOWN'"),
                ("model", "TEXT")
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

            # MCP Connectors table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS mcp_connectors (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'DISCONNECTED',
                    configuration TEXT,
                    capabilities TEXT,
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # MCP Tools table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS mcp_tools (
                    id TEXT PRIMARY KEY,
                    connector_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT,
                    input_schema TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (connector_id) REFERENCES mcp_connectors(id) ON DELETE CASCADE
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_mcp_tools_conn ON mcp_tools(connector_id)")

            # MCP Tool Calls table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS mcp_tool_calls (
                    id TEXT PRIMARY KEY,
                    connector_id TEXT NOT NULL,
                    tool_id TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    task_id TEXT,
                    run_id TEXT,
                    status TEXT NOT NULL DEFAULT 'STARTED',
                    arguments TEXT,
                    result TEXT,
                    error TEXT,
                    started_at TIMESTAMP NOT NULL,
                    completed_at TIMESTAMP,
                    FOREIGN KEY (connector_id) REFERENCES mcp_connectors(id) ON DELETE CASCADE,
                    FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_mcp_calls_agent ON mcp_tool_calls(agent_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_mcp_calls_conn ON mcp_tool_calls(connector_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_mcp_calls_task ON mcp_tool_calls(task_id)")

            # MCP Agent Permissions table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS mcp_agent_permissions (
                    id TEXT PRIMARY KEY,
                    agent_id TEXT NOT NULL,
                    connector_id TEXT NOT NULL,
                    tool_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE,
                    FOREIGN KEY (connector_id) REFERENCES mcp_connectors(id) ON DELETE CASCADE
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_mcp_perm_agent ON mcp_agent_permissions(agent_id)")

            # Agent Teams table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS agent_teams (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    manager_agent_id TEXT NOT NULL,
                    project_id TEXT,
                    description TEXT,
                    status TEXT NOT NULL DEFAULT 'ACTIVE',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (manager_agent_id) REFERENCES agents(id) ON DELETE CASCADE,
                    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_teams_mgr ON agent_teams(manager_agent_id)")

            # Team Members table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS team_members (
                    team_id TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    role_in_team TEXT DEFAULT 'MEMBER',
                    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (team_id, agent_id),
                    FOREIGN KEY (team_id) REFERENCES agent_teams(id) ON DELETE CASCADE,
                    FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE
                )
            """)

            # Platform-wide key/value settings (runtime provider choice, setup state).
            # Secrets are never stored here — only non-secret selections.
            conn.execute("""
                CREATE TABLE IF NOT EXISTS platform_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

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
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

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

            # Seed default agent templates and baseline agents if tables are empty
            self._seed_default_templates(conn)
            self._seed_default_agents(conn)

            conn.commit()

    # Platform settings methods
    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Read a platform setting, returning `default` when unset."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT value FROM platform_settings WHERE key = ?", (key,)
            )
            row = cursor.fetchone()
            return row['value'] if row else default

    def set_setting(self, key: str, value: Optional[str]):
        """Upsert a platform setting."""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO platform_settings (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
            """, (key, value, datetime.now()))
            conn.commit()

    def delete_setting(self, key: str):
        """Remove a platform setting."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM platform_settings WHERE key = ?", (key,))
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
            INSERT OR IGNORE INTO agent_templates
            (id, name, description, role, system_prompt, model, skills, tools, suggested_children, category, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [(d[0], d[1], d[2], d[3], d[4], d[5], d[6], d[7], d[8], d[9], now, now) for d in defaults])

    def _seed_default_agents(self, conn: sqlite3.Connection):
        """Seed default baseline agents (canonical 11 agents) if agents table is empty."""
        cursor = conn.execute("SELECT COUNT(*) FROM agents")
        if cursor.fetchone()[0] > 0:
            return

        agents_file = POC_ROOT / "backend" / "config" / "agents.json"
        defaults = []
        if agents_file.exists():
            try:
                with open(agents_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    defaults = list(data.values()) if isinstance(data, dict) else []
            except Exception as e:
                logging.getLogger(__name__).warning(f"Failed to read baseline agents from {agents_file}: {e}")

        if not defaults:
            return

        now = datetime.now().isoformat()
        for item in defaults:
            aid = item.get("id")
            if not aid:
                continue
            role_type = item.get("role_type")
            if not role_type:
                if aid == "chief-orchestrator":
                    role_type = "ROOT_ORCHESTRATOR"
                elif "lead" in aid:
                    role_type = "MANAGER"
                else:
                    role_type = "WORKER"

            parent_id = item.get("parent_id")
            if not parent_id:
                if role_type == "MANAGER":
                    parent_id = "chief-orchestrator"
                elif aid in ("secuirty", "marketing-content"):
                    parent_id = "lead-engineer" if aid == "secuirty" else "marketing-lead"
                elif aid == "general-task-agent":
                    parent_id = "operations-lead"

            conn.execute("""
                INSERT OR IGNORE INTO agents
                (id, name, description, system_prompt, skills, model, effort, max_tokens, temperature,
                 repo_path, github_url, department, avatar, created_at, updated_at,
                 parent_id, role_type, max_concurrent_children, delegation_strategy,
                 allowed_child_ids, allowed_tools, template_id, dangerously_skip_permissions,
                 allow_sibling_communication, allowed_peer_ids, mcp_permissions, runtime_provider)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                aid,
                item.get("name", aid),
                item.get("description", ""),
                item.get("system_prompt", "Autonomous agent"),
                json.dumps(item.get("skills", [])),
                item.get("model", "default"),
                item.get("effort", "medium"),
                item.get("max_tokens", 8000),
                item.get("temperature", 0.7),
                item.get("repo_path"),
                item.get("github_url"),
                item.get("department", "Engineering"),
                item.get("avatar", "brain" if aid == "chief-orchestrator" else None),
                now, now,
                parent_id,
                role_type,
                item.get("max_concurrent_children", 3),
                item.get("delegation_strategy", "hierarchical"),
                json.dumps(item.get("allowed_child_ids", [])),
                json.dumps(item.get("allowed_tools", [])),
                item.get("template_id"),
                1 if item.get("dangerously_skip_permissions") else 0,
                1 if item.get("allow_sibling_communication", True) else 0,
                json.dumps(item.get("allowed_peer_ids", [])),
                json.dumps(item.get("mcp_permissions", [])),
                item.get("runtime_provider")
            ))

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
            dangerously_skip_permissions=bool(row['dangerously_skip_permissions']) if 'dangerously_skip_permissions' in keys and row['dangerously_skip_permissions'] is not None else False,
            allow_sibling_communication=bool(row['allow_sibling_communication']) if 'allow_sibling_communication' in keys and row['allow_sibling_communication'] is not None else True,
            allowed_peer_ids=json.loads(row['allowed_peer_ids']) if 'allowed_peer_ids' in keys and row['allowed_peer_ids'] else [],
            mcp_permissions=json.loads(row['mcp_permissions']) if 'mcp_permissions' in keys and row['mcp_permissions'] else [],
            runtime_provider=row['runtime_provider'] if 'runtime_provider' in keys and row['runtime_provider'] else None,
            is_workflow_agent=bool(row['is_workflow_agent']) if 'is_workflow_agent' in keys and row['is_workflow_agent'] is not None else False,
            workflow_id=row['workflow_id'] if 'workflow_id' in keys else None
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
            if not existing:
                is_wf = bool(getattr(agent, "is_workflow_agent", False) or getattr(agent, "role_type", "") == "WORKFLOW_AUTOMATION")
                if not is_wf:
                    count = conn.execute("SELECT COUNT(*) FROM agents WHERE is_workflow_agent = 0").fetchone()[0]
                    if count >= self.max_agents:
                        raise ValueError(f"Platform agent capacity reached: maximum {self.max_agents} agents allowed")
            created_at = existing['created_at'] if existing else (getattr(agent, "created_at", None) or datetime.now().isoformat())
            updated_at = datetime.now().isoformat()

            conn.execute("""
                INSERT INTO agents
                (id, name, description, system_prompt, skills, model, effort, max_tokens, temperature,
                 repo_path, github_url, department, avatar, created_at, updated_at,
                 parent_id, role_type, max_concurrent_children, delegation_strategy,
                 allowed_child_ids, allowed_tools, template_id, dangerously_skip_permissions,
                 allow_sibling_communication, allowed_peer_ids, mcp_permissions, runtime_provider,
                 is_workflow_agent, workflow_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    dangerously_skip_permissions=excluded.dangerously_skip_permissions,
                    allow_sibling_communication=excluded.allow_sibling_communication,
                    allowed_peer_ids=excluded.allowed_peer_ids,
                    mcp_permissions=excluded.mcp_permissions,
                    runtime_provider=excluded.runtime_provider,
                    is_workflow_agent=excluded.is_workflow_agent,
                    workflow_id=excluded.workflow_id
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
                1 if getattr(agent, "dangerously_skip_permissions", False) else 0,
                1 if getattr(agent, "allow_sibling_communication", True) else 0,
                json.dumps(getattr(agent, "allowed_peer_ids", []) or []),
                json.dumps(getattr(agent, "mcp_permissions", []) or []),
                getattr(agent, "runtime_provider", None),
                1 if getattr(agent, "is_workflow_agent", False) else 0,
                getattr(agent, "workflow_id", None)
            ))
            conn.commit()

        if not existing:
            try:
                self.create_agent_session(agent.id, title="Session 1", close_existing=False)
            except Exception:
                pass

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
        """Delete an agent and clean up any linked task runs, messages, permissions, and hierarchy relationships."""
        with self._get_connection() as conn:
            conn.execute("UPDATE agents SET parent_id = NULL WHERE parent_id = ?", (agent_id,))
            conn.execute("DELETE FROM team_members WHERE agent_id = ?", (agent_id,))
            conn.execute("DELETE FROM agent_teams WHERE manager_agent_id = ?", (agent_id,))
            conn.execute("DELETE FROM mcp_agent_permissions WHERE agent_id = ?", (agent_id,))
            conn.execute("DELETE FROM agent_messages WHERE from_agent_id = ? OR to_agent_id = ?", (agent_id, agent_id))
            conn.execute("DELETE FROM agent_interactions WHERE requester_agent_id = ? OR target_approver_id = ?", (agent_id, agent_id))
            conn.execute("DELETE FROM chat_messages WHERE agent_id = ?", (agent_id,))
            conn.execute("DELETE FROM agent_conversations WHERE agent_id = ?", (agent_id,))
            conn.execute("DELETE FROM task_runs WHERE agent_id = ?", (agent_id,))
            conn.execute("DELETE FROM super_agent_configs WHERE agent_id = ?", (agent_id,))
            conn.execute("DELETE FROM agents WHERE id = ?", (agent_id,))
            conn.commit()

    def clean_database(self, seed_baseline: bool = True):
        """Clean all tables from database and optionally reseed default templates and baseline agents."""
        with self._get_connection() as conn:
            conn.execute("PRAGMA foreign_keys = OFF")
            tables = [
                "war_room_messages", "war_room_sessions",
                "chat_messages", "agent_conversations",
                "agent_messages", "agent_interactions",
                "task_runs", "team_members", "agent_teams",
                "mcp_tool_calls", "mcp_agent_permissions",
                "super_agent_configs", "project_memories",
                "event_log", "audit_logs", "cron_jobs",
                "skills", "projects", "agent_templates", "agents"
            ]
            for t in tables:
                conn.execute(f"DELETE FROM {t}")
            conn.execute("PRAGMA foreign_keys = ON")
            conn.commit()

        # Re-initialize default seeds
        with self._get_connection() as conn:
            self._seed_default_templates(conn)
            if seed_baseline:
                self._seed_default_agents(conn)
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
        deps_val = row['dependencies'] if 'dependencies' in keys else None
        if deps_val:
            try:
                deps = json.loads(deps_val) if isinstance(deps_val, str) else list(deps_val)
            except Exception:
                deps = []
        else:
            deps = []

        sr_val = row['structured_result'] if 'structured_result' in keys else None
        if sr_val:
            try:
                sr = json.loads(sr_val) if isinstance(sr_val, str) else dict(sr_val)
            except Exception:
                sr = None
        else:
            sr = None

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
            session_id=row['session_id'] if 'session_id' in keys else None,
            dependencies=deps,
            structured_result=sr,
            acceptance_criteria=row['acceptance_criteria'] if 'acceptance_criteria' in keys else None,
            retry_count=int(row['retry_count']) if 'retry_count' in keys and row['retry_count'] is not None else 0,
            input_tokens=int(row['input_tokens']) if 'input_tokens' in keys and row['input_tokens'] is not None else 0,
            output_tokens=int(row['output_tokens']) if 'output_tokens' in keys and row['output_tokens'] is not None else 0,
            cache_read_tokens=int(row['cache_read_tokens']) if 'cache_read_tokens' in keys and row['cache_read_tokens'] is not None else 0,
            cache_write_tokens=int(row['cache_write_tokens']) if 'cache_write_tokens' in keys and row['cache_write_tokens'] is not None else 0,
            cost_usd=float(row['cost_usd']) if 'cost_usd' in keys and row['cost_usd'] is not None else 0.0,
            cost_source=row['cost_source'] if 'cost_source' in keys and row['cost_source'] else 'UNKNOWN',
            model=row['model'] if 'model' in keys else None
        )

    def save_task_run(self, run: AgentRun):
        """Save or update a task run."""
        deps_json = json.dumps(run.dependencies) if getattr(run, "dependencies", None) else None
        sr_json = json.dumps(run.structured_result) if getattr(run, "structured_result", None) else None
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO task_runs
                (run_id, agent_id, project_id, prompt, status, created_at, started_at, ended_at,
                 result, error, exit_code, events, parent_task_id, root_task_id, assigned_by, session_id,
                 dependencies, structured_result, acceptance_criteria, retry_count,
                 input_tokens, output_tokens, cache_read_tokens, cache_write_tokens, cost_usd, cost_source, model)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    agent_id = excluded.agent_id,
                    project_id = excluded.project_id,
                    prompt = excluded.prompt,
                    status = excluded.status,
                    created_at = excluded.created_at,
                    started_at = COALESCE(excluded.started_at, task_runs.started_at),
                    ended_at = excluded.ended_at,
                    result = excluded.result,
                    error = excluded.error,
                    exit_code = excluded.exit_code,
                    events = COALESCE(excluded.events, task_runs.events),
                    parent_task_id = COALESCE(excluded.parent_task_id, task_runs.parent_task_id),
                    root_task_id = COALESCE(excluded.root_task_id, task_runs.root_task_id),
                    assigned_by = COALESCE(excluded.assigned_by, task_runs.assigned_by),
                    session_id = COALESCE(excluded.session_id, task_runs.session_id),
                    dependencies = COALESCE(excluded.dependencies, task_runs.dependencies),
                    structured_result = COALESCE(excluded.structured_result, task_runs.structured_result),
                    acceptance_criteria = COALESCE(excluded.acceptance_criteria, task_runs.acceptance_criteria),
                    retry_count = COALESCE(excluded.retry_count, task_runs.retry_count),
                    input_tokens = COALESCE(excluded.input_tokens, task_runs.input_tokens),
                    output_tokens = COALESCE(excluded.output_tokens, task_runs.output_tokens),
                    cache_read_tokens = COALESCE(excluded.cache_read_tokens, task_runs.cache_read_tokens),
                    cache_write_tokens = COALESCE(excluded.cache_write_tokens, task_runs.cache_write_tokens),
                    cost_usd = COALESCE(excluded.cost_usd, task_runs.cost_usd),
                    cost_source = COALESCE(excluded.cost_source, task_runs.cost_source),
                    model = COALESCE(excluded.model, task_runs.model)
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
                getattr(run, "session_id", None),
                deps_json,
                sr_json,
                getattr(run, "acceptance_criteria", None),
                getattr(run, "retry_count", 0),
                getattr(run, "input_tokens", 0) or 0,
                getattr(run, "output_tokens", 0) or 0,
                getattr(run, "cache_read_tokens", 0) or 0,
                getattr(run, "cache_write_tokens", 0) or 0,
                float(getattr(run, "cost_usd", 0.0) or 0.0),
                getattr(run, "cost_source", "UNKNOWN"),
                getattr(run, "model", None)
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
        result: Optional[str] = None,
        dependencies: Optional[List[str]] = None,
        structured_result: Optional[Dict[str, Any]] = None,
        acceptance_criteria: Optional[str] = None,
        retry_count: Optional[int] = None,
        ended_at: Optional[datetime] = None,
        input_tokens: Optional[int] = None,
        output_tokens: Optional[int] = None,
        cache_read_tokens: Optional[int] = None,
        cache_write_tokens: Optional[int] = None,
        cost_usd: Optional[float] = None,
        cost_source: Optional[str] = None,
        model: Optional[str] = None
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
        if dependencies is not None:
            fields.append("dependencies = ?")
            params.append(json.dumps(dependencies))
        if structured_result is not None:
            fields.append("structured_result = ?")
            params.append(json.dumps(structured_result))
        if acceptance_criteria is not None:
            fields.append("acceptance_criteria = ?")
            params.append(acceptance_criteria)
        if retry_count is not None:
            fields.append("retry_count = ?")
            params.append(retry_count)
        if ended_at is not None:
            fields.append("ended_at = ?")
            params.append(ended_at.isoformat() if isinstance(ended_at, datetime) else str(ended_at))
        if input_tokens is not None:
            fields.append("input_tokens = ?")
            params.append(input_tokens)
        if output_tokens is not None:
            fields.append("output_tokens = ?")
            params.append(output_tokens)
        if cache_read_tokens is not None:
            fields.append("cache_read_tokens = ?")
            params.append(cache_read_tokens)
        if cache_write_tokens is not None:
            fields.append("cache_write_tokens = ?")
            params.append(cache_write_tokens)
        if cost_usd is not None:
            fields.append("cost_usd = ?")
            params.append(cost_usd)
        if cost_source is not None:
            fields.append("cost_source = ?")
            params.append(cost_source)
        if model is not None:
            fields.append("model = ?")
            params.append(model)

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
        if agent_id and not target_approver_id:
            query += " AND (requester_agent_id = ? OR target_approver_id = ?)"
            params.extend([agent_id, agent_id])
        elif agent_id:
            query += " AND requester_agent_id = ?"
            params.append(agent_id)
        if target_approver_id and not agent_id:
            query += " AND target_approver_id = ?"
            params.append(target_approver_id)
        elif target_approver_id and agent_id:
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
    def create_agent_session(
        self,
        agent_id: str,
        project_id: Optional[str] = None,
        title: Optional[str] = None,
        close_existing: bool = True,
        task_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new session for an agent.
        If close_existing is True, marks all previous active sessions as CLOSED.
        Links the supervisor's active session ID so child-parent A2A context is retained.
        """
        with self._get_connection() as conn:
            now = datetime.now().isoformat()
            if close_existing:
                conn.execute(
                    "UPDATE agent_conversations SET status = 'CLOSED', updated_at = ? WHERE agent_id = ? AND status = 'ACTIVE'",
                    (now, agent_id)
                )

            # Determine supervisor session from agent hierarchy
            supervisor_session_id = None
            try:
                agent = self.get_agent(agent_id)
                if agent and getattr(agent, "parent_id", None):
                    sup_row = conn.execute(
                        "SELECT id, claude_session_id FROM agent_conversations WHERE agent_id = ? AND status = 'ACTIVE' ORDER BY updated_at DESC LIMIT 1",
                        (agent.parent_id,)
                    ).fetchone()
                    if sup_row:
                        supervisor_session_id = sup_row["id"]
                    else:
                        sup_any = conn.execute(
                            "SELECT id FROM agent_conversations WHERE agent_id = ? ORDER BY updated_at DESC LIMIT 1",
                            (agent.parent_id,)
                        ).fetchone()
                        if sup_any:
                            supervisor_session_id = sup_any["id"]
            except Exception:
                pass

            conv_id = f"conv_{uuid.uuid4().hex[:12]}"
            claude_session_id = f"sess_{agent_id}_{uuid.uuid4().hex[:8]}"
            count_row = conn.execute("SELECT COUNT(*) FROM agent_conversations WHERE agent_id = ?", (agent_id,)).fetchone()
            seq_num = (count_row[0] + 1) if count_row else 1
            session_title = title or f"Session {seq_num}"
            assigned_task_id = task_id or f"task_{conv_id.replace('conv_', '')}"

            conn.execute("""
                INSERT INTO agent_conversations (
                    id, agent_id, project_id, title, claude_session_id, runtime_session_id, task_id, supervisor_session_id, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE', ?, ?)
            """, (conv_id, agent_id, project_id, session_title, claude_session_id, claude_session_id, assigned_task_id, supervisor_session_id, now, now))
            conn.commit()

            return {
                "id": conv_id,
                "agent_id": agent_id,
                "project_id": project_id,
                "title": session_title,
                "claude_session_id": claude_session_id,
                "runtime_session_id": claude_session_id,
                "task_id": assigned_task_id,
                "supervisor_session_id": supervisor_session_id,
                "status": "ACTIVE",
                "created_at": now,
                "updated_at": now
            }

    def list_agent_sessions(self, agent_id: str) -> List[Dict[str, Any]]:
        """List all chat sessions for an agent, latest first, enriched with supervisor info."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM agent_conversations WHERE agent_id = ? ORDER BY created_at DESC",
                (agent_id,)
            ).fetchall()
            sessions = [dict(r) for r in rows]

            # Resolve supervisor info if parent agent exists
            parent_id = None
            parent_name = None
            parent_active_session_id = None
            parent_active_session_title = None
            try:
                agent = self.get_agent(agent_id)
                if agent and getattr(agent, "parent_id", None):
                    parent_id = agent.parent_id
                    parent_agent = self.get_agent(parent_id)
                    parent_name = parent_agent.name if parent_agent else parent_id
                    sup_active = conn.execute(
                        "SELECT id, title FROM agent_conversations WHERE agent_id = ? AND status = 'ACTIVE' ORDER BY updated_at DESC LIMIT 1",
                        (parent_id,)
                    ).fetchone()
                    if sup_active:
                        parent_active_session_id = sup_active["id"]
                        parent_active_session_title = sup_active["title"]
            except Exception:
                pass

            for s in sessions:
                s["supervisor_agent_id"] = parent_id
                s["supervisor_agent_name"] = parent_name
                if s.get("supervisor_session_id"):
                    try:
                        sup_row = conn.execute("SELECT title FROM agent_conversations WHERE id = ?", (s["supervisor_session_id"],)).fetchone()
                        s["supervisor_session_title"] = sup_row["title"] if sup_row else (parent_active_session_title or "Supervisor Session")
                    except Exception:
                        s["supervisor_session_title"] = parent_active_session_title or "Supervisor Session"
                else:
                    s["supervisor_session_id"] = parent_active_session_id
                    s["supervisor_session_title"] = parent_active_session_title

            return sessions

    def get_conversation(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a specific conversation/session by ID, enriched with supervisor info."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM agent_conversations WHERE id = ?",
                (conversation_id,)
            ).fetchone()
            if not row:
                return None
            res = dict(row)
            try:
                agent = self.get_agent(res["agent_id"])
                if agent and getattr(agent, "parent_id", None):
                    res["supervisor_agent_id"] = agent.parent_id
                    parent_agent = self.get_agent(agent.parent_id)
                    res["supervisor_agent_name"] = parent_agent.name if parent_agent else agent.parent_id
                    sup_active = conn.execute(
                        "SELECT id, title FROM agent_conversations WHERE agent_id = ? AND status = 'ACTIVE' ORDER BY updated_at DESC LIMIT 1",
                        (agent.parent_id,)
                    ).fetchone()
                    if sup_active:
                        if not res.get("supervisor_session_id"):
                            res["supervisor_session_id"] = sup_active["id"]
                        res["supervisor_session_title"] = sup_active["title"]
            except Exception:
                pass
            return res

    def activate_agent_session(self, agent_id: str, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Set a specific session as ACTIVE, closing any other active sessions."""
        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE agent_conversations SET status = 'CLOSED', updated_at = ? WHERE agent_id = ?",
                (now, agent_id)
            )
            conn.execute(
                "UPDATE agent_conversations SET status = 'ACTIVE', updated_at = ? WHERE id = ? AND agent_id = ?",
                (now, conversation_id, agent_id)
            )
            conn.commit()
            return self.get_conversation(conversation_id)

    def close_agent_session(self, conversation_id: str) -> bool:
        """Close an active session."""
        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE agent_conversations SET status = 'CLOSED', updated_at = ? WHERE id = ?",
                (now, conversation_id)
            )
            conn.commit()
            return True

    def get_or_create_channel(
        self,
        manager_id: str,
        worker_id: str,
        task_id: str,
        project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get or create a dedicated, isolated communication channel between a manager and a worker
        for a specific task, preventing cross-talk between sibling subagents.
        Channel key format: channel:{manager_id}:{worker_id}:{task_id}
        """
        channel_key = f"channel:{manager_id}:{worker_id}:{task_id}"
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM agent_conversations WHERE channel_key = ? LIMIT 1",
                (channel_key,)
            ).fetchone()
            if row:
                return dict(row)

            conv_id = f"conv_chan_{uuid.uuid4().hex[:12]}"
            now = datetime.now().isoformat()
            title = f"Channel: {manager_id} <-> {worker_id} ({task_id})"

            conn.execute("""
                INSERT INTO agent_conversations (
                    id, agent_id, project_id, title, task_id, status, channel_key, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 'ACTIVE', ?, ?, ?)
            """, (conv_id, worker_id, project_id, title, task_id, channel_key, now, now))
            conn.commit()

            return self.get_conversation(conv_id)

    def get_or_create_conversation(self, agent_id: str, project_id: Optional[str] = None) -> Dict[str, Any]:
        """Get the active conversation for an agent, or create a new one."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM agent_conversations WHERE agent_id = ? AND status = 'ACTIVE' ORDER BY updated_at DESC LIMIT 1",
                (agent_id,)
            ).fetchone()

            if row:
                res = dict(row)
                if not res.get("task_id"):
                    assigned_task_id = f"task_{res['id'].replace('conv_', '')}"
                    conn.execute("UPDATE agent_conversations SET task_id = ? WHERE id = ?", (assigned_task_id, res["id"]))
                    conn.commit()
                    res["task_id"] = assigned_task_id
                return res

            # If no ACTIVE session, try latest existing before creating fresh
            any_row = conn.execute(
                "SELECT * FROM agent_conversations WHERE agent_id = ? ORDER BY updated_at DESC LIMIT 1",
                (agent_id,)
            ).fetchone()
            if any_row:
                now_str = datetime.now().isoformat()
                assigned_task_id = any_row["task_id"] or f"task_{any_row['id'].replace('conv_', '')}"
                conn.execute(
                    "UPDATE agent_conversations SET status = 'ACTIVE', task_id = ?, updated_at = ? WHERE id = ?",
                    (assigned_task_id, now_str, any_row["id"])
                )
                conn.commit()
                return self.get_conversation(any_row["id"])

        return self.create_agent_session(agent_id, project_id=project_id, close_existing=False)

    def update_conversation_session(self, conversation_id: str, claude_session_id: str, task_id: Optional[str] = None):
        """Associate a runtime/CLI session ID and optional task_id with the conversation."""
        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            if task_id:
                conn.execute("""
                    UPDATE agent_conversations
                    SET claude_session_id = ?, runtime_session_id = ?, task_id = ?, updated_at = ?
                    WHERE id = ?
                """, (claude_session_id, claude_session_id, task_id, now, conversation_id))
            else:
                conn.execute("""
                    UPDATE agent_conversations
                    SET claude_session_id = ?, runtime_session_id = ?, updated_at = ?
                    WHERE id = ?
                """, (claude_session_id, claude_session_id, now, conversation_id))
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
                message_data.get('created_at') or now
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

    def get_chat_history(self, agent_id: str, limit: int = 100, conversation_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve recent chat history for an agent (optionally filtered by conversation_id)."""
        with self._get_connection() as conn:
            if conversation_id:
                rows = conn.execute("""
                    SELECT * FROM (
                        SELECT * FROM chat_messages
                        WHERE agent_id = ? AND conversation_id = ?
                        ORDER BY created_at DESC
                        LIMIT ?
                    ) sub
                    ORDER BY created_at ASC
                """, (agent_id, conversation_id, limit)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT * FROM (
                        SELECT * FROM chat_messages
                        WHERE agent_id = ?
                        ORDER BY created_at DESC
                        LIMIT ?
                    ) sub
                    ORDER BY created_at ASC
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

    def has_chat_message_for_task(self, agent_id: str, task_id: str, sender_type: str, content: Optional[str] = None) -> bool:
        """Check if a chat message already exists for a specific task and sender type, or with identical prompt."""
        with self._get_connection() as conn:
            if content:
                row = conn.execute("""
                    SELECT 1 FROM chat_messages
                    WHERE agent_id = ? 
                      AND (task_id = ? OR json_extract(metadata, '$.task_id') = ?)
                      AND content = ?
                      AND sender_type = ?
                    LIMIT 1
                """, (agent_id, task_id, task_id, content, sender_type)).fetchone()
            else:
                row = conn.execute("""
                    SELECT 1 FROM chat_messages
                    WHERE agent_id = ? 
                      AND (task_id = ? OR json_extract(metadata, '$.task_id') = ?)
                      AND sender_type = ?
                    LIMIT 1
                """, (agent_id, task_id, task_id, sender_type)).fetchone()
            return row is not None

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

        source_task_id = memory_data.get('source_task_id')
        source_run_id = memory_data.get('source_run_id')
        confidence = memory_data.get('confidence', 1.0)

        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO project_memories (
                    id, project_id, category, title, content, tags, author_agent_id,
                    source_task_id, source_run_id, confidence, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                mem_id,
                memory_data['project_id'],
                memory_data.get('category', 'INSIGHT'),
                memory_data['title'],
                memory_data['content'],
                tags_str,
                memory_data.get('author_agent_id'),
                source_task_id,
                source_run_id,
                confidence,
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

    # -------------------------------------------------------------
    # Agent-to-Agent Messaging persistence methods
    # -------------------------------------------------------------
    def save_agent_message(self, message: Union[AgentMessage, Dict[str, Any]]) -> AgentMessage:
        """Save a new or updated internal agent message."""
        if isinstance(message, dict):
            msg = AgentMessage.from_dict(message)
        else:
            msg = message

        if not msg.id:
            msg.id = f"msg_{uuid.uuid4().hex[:12]}"
        now = datetime.now().isoformat()
        if not msg.created_at:
            msg.created_at = now

        meta_str = json.dumps(msg.metadata) if msg.metadata else None
        channel_key = msg.channel_key
        if not channel_key and msg.task_id:
            mtype = getattr(msg, "message_type", "QUESTION").upper()
            if mtype == "QUESTION":
                channel_key = f"channel:{msg.to_agent_id}:{msg.from_agent_id}:{msg.task_id}"
            else:
                channel_key = f"channel:{msg.from_agent_id}:{msg.to_agent_id}:{msg.task_id}"

        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO agent_messages (
                    id, from_agent_id, to_agent_id, task_id, run_id, parent_message_id,
                    message_type, content, status, metadata, channel_key, created_at, responded_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    status=excluded.status,
                    responded_at=excluded.responded_at,
                    metadata=excluded.metadata,
                    channel_key=excluded.channel_key
            """, (
                msg.id,
                msg.from_agent_id,
                msg.to_agent_id,
                msg.task_id,
                msg.run_id,
                msg.parent_message_id,
                msg.message_type,
                msg.content,
                msg.status,
                meta_str,
                channel_key,
                msg.created_at,
                msg.responded_at
            ))
            conn.commit()

        return self.get_agent_message(msg.id)

    def get_agent_message(self, message_id: str) -> Optional[AgentMessage]:
        """Retrieve an agent message by ID."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM agent_messages WHERE id = ?", (message_id,)).fetchone()
            if not row:
                return None
            d = dict(row)
            if d.get("metadata"):
                try:
                    d["metadata"] = json.loads(d["metadata"])
                except Exception:
                    pass
            return AgentMessage.from_dict(d)

    def list_agent_messages(
        self,
        from_agent_id: Optional[str] = None,
        to_agent_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        task_id: Optional[str] = None,
        parent_message_id: Optional[str] = None,
        channel_key: Optional[str] = None,
        limit: int = 100
    ) -> List[AgentMessage]:
        """List internal messages between agents with optional filters."""
        query = "SELECT * FROM agent_messages WHERE 1=1"
        params: List[Any] = []
        if channel_key:
            query += " AND channel_key = ?"
            params.append(channel_key)
        if agent_id:
            query += " AND (from_agent_id = ? OR to_agent_id = ?)"
            params.extend([agent_id, agent_id])
        else:
            if from_agent_id:
                query += " AND from_agent_id = ?"
                params.append(from_agent_id)
            if to_agent_id:
                query += " AND to_agent_id = ?"
                params.append(to_agent_id)
        if task_id:
            query += " AND task_id = ?"
            params.append(task_id)
        if parent_message_id:
            query += " AND parent_message_id = ?"
            params.append(parent_message_id)

        query += " ORDER BY created_at ASC LIMIT ?"
        params.append(limit)

        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            results = []
            for r in rows:
                d = dict(r)
                if d.get("metadata"):
                    try:
                        d["metadata"] = json.loads(d["metadata"])
                    except Exception:
                        pass
                results.append(AgentMessage.from_dict(d))
            return results

    def update_agent_message(
        self,
        message_id: str,
        status: Optional[str] = None,
        responded_at: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[AgentMessage]:
        """Update an agent message status and response time."""
        fields = []
        params = []
        if status is not None:
            fields.append("status = ?")
            params.append(status)
        if responded_at is not None:
            fields.append("responded_at = ?")
            params.append(responded_at)
        if metadata is not None:
            fields.append("metadata = ?")
            params.append(json.dumps(metadata))

        if not fields:
            return self.get_agent_message(message_id)

        params.append(message_id)
        with self._get_connection() as conn:
            conn.execute(f"UPDATE agent_messages SET {', '.join(fields)} WHERE id = ?", params)
            conn.commit()

        return self.get_agent_message(message_id)

    # -------------------------------------------------------------
    # Super Agent Configuration persistence methods
    # -------------------------------------------------------------
    def save_super_agent_config(self, config: Union[SuperAgentConfig, Dict[str, Any]]) -> SuperAgentConfig:
        """Save or update decision authority configuration for a Super Agent."""
        if isinstance(config, dict):
            cfg = SuperAgentConfig.from_dict(config)
        else:
            cfg = config

        now = datetime.now().isoformat()
        approval_str = json.dumps(cfg.require_human_approval_for) if cfg.require_human_approval_for else None

        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO super_agent_configs (
                    agent_id, project_id, can_answer_questions, can_delegate,
                    can_create_subtasks, can_use_mcp, can_make_project_decisions,
                    can_modify_files, can_execute_commands, require_human_approval_for,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(agent_id) DO UPDATE SET
                    project_id=excluded.project_id,
                    can_answer_questions=excluded.can_answer_questions,
                    can_delegate=excluded.can_delegate,
                    can_create_subtasks=excluded.can_create_subtasks,
                    can_use_mcp=excluded.can_use_mcp,
                    can_make_project_decisions=excluded.can_make_project_decisions,
                    can_modify_files=excluded.can_modify_files,
                    can_execute_commands=excluded.can_execute_commands,
                    require_human_approval_for=excluded.require_human_approval_for,
                    updated_at=excluded.updated_at
            """, (
                cfg.agent_id,
                cfg.project_id,
                1 if cfg.can_answer_questions else 0,
                1 if cfg.can_delegate else 0,
                1 if cfg.can_create_subtasks else 0,
                1 if cfg.can_use_mcp else 0,
                1 if cfg.can_make_project_decisions else 0,
                1 if cfg.can_modify_files else 0,
                1 if cfg.can_execute_commands else 0,
                approval_str,
                now,
                now
            ))
            conn.commit()

        return self.get_super_agent_config(cfg.agent_id)

    def get_super_agent_config(self, agent_id: str) -> Optional[SuperAgentConfig]:
        """Get super agent authority configuration by agent ID."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM super_agent_configs WHERE agent_id = ?", (agent_id,)).fetchone()
            if not row:
                return None
            return self._row_to_super_agent_config(row)

    def get_super_agent_for_project(self, project_id: str) -> Optional[SuperAgentConfig]:
        """Get the configured Super Agent for a designated project."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM super_agent_configs WHERE project_id = ?", (project_id,)).fetchone()
            if not row:
                return None
            return self._row_to_super_agent_config(row)

    def list_super_agent_configs(self) -> List[SuperAgentConfig]:
        """List all configured Super Agents across projects."""
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM super_agent_configs ORDER BY created_at DESC").fetchall()
            return [self._row_to_super_agent_config(r) for r in rows]

    def _row_to_super_agent_config(self, row: sqlite3.Row) -> SuperAgentConfig:
        d = dict(row)
        approval_list = json.loads(d["require_human_approval_for"]) if d.get("require_human_approval_for") else []
        return SuperAgentConfig(
            agent_id=d["agent_id"],
            project_id=d["project_id"],
            can_answer_questions=bool(d["can_answer_questions"]),
            can_delegate=bool(d["can_delegate"]),
            can_create_subtasks=bool(d["can_create_subtasks"]),
            can_use_mcp=bool(d["can_use_mcp"]),
            can_make_project_decisions=bool(d["can_make_project_decisions"]),
            can_modify_files=bool(d["can_modify_files"]),
            can_execute_commands=bool(d["can_execute_commands"]),
            require_human_approval_for=approval_list
        )

    # -------------------------------------------------------------
    # MCP (Model Context Protocol) persistence methods
    # -------------------------------------------------------------
    def save_mcp_connector(self, connector: Union[MCPConnector, Dict[str, Any]]) -> MCPConnector:
        """Register or update an MCP connector."""
        if isinstance(connector, dict):
            c = MCPConnector(**connector)
        else:
            c = connector

        now = datetime.now().isoformat()
        cfg_str = json.dumps(c.configuration) if c.configuration else None
        caps_str = json.dumps(c.capabilities) if c.capabilities else None

        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO mcp_connectors (
                    id, name, provider, status, configuration, capabilities, error_message, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name,
                    provider=excluded.provider,
                    status=excluded.status,
                    configuration=excluded.configuration,
                    capabilities=excluded.capabilities,
                    error_message=excluded.error_message,
                    updated_at=excluded.updated_at
            """, (
                c.id,
                c.name,
                c.provider,
                c.status,
                cfg_str,
                caps_str,
                c.error_message,
                c.created_at or now,
                now
            ))
            conn.commit()

        return self.get_mcp_connector(c.id)

    def get_mcp_connector(self, connector_id: str) -> Optional[MCPConnector]:
        """Retrieve an MCP connector by ID."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM mcp_connectors WHERE id = ?", (connector_id,)).fetchone()
            if not row:
                return None
            d = dict(row)
            if d.get("configuration"):
                try:
                    d["configuration"] = json.loads(d["configuration"])
                except Exception:
                    pass
            if d.get("capabilities"):
                try:
                    d["capabilities"] = json.loads(d["capabilities"])
                except Exception:
                    pass
            return MCPConnector(**d)

    def list_mcp_connectors(self) -> List[MCPConnector]:
        """List all registered MCP connectors."""
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM mcp_connectors ORDER BY name ASC").fetchall()
            results = []
            for r in rows:
                d = dict(r)
                if d.get("configuration"):
                    try:
                        d["configuration"] = json.loads(d["configuration"])
                    except Exception:
                        pass
                if d.get("capabilities"):
                    try:
                        d["capabilities"] = json.loads(d["capabilities"])
                    except Exception:
                        pass
                results.append(MCPConnector(**d))
            return results

    def delete_mcp_connector(self, connector_id: str) -> bool:
        """Delete an MCP connector and associated tools."""
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM mcp_connectors WHERE id = ?", (connector_id,))
            conn.commit()
            return cursor.rowcount > 0

    def save_mcp_tool(self, tool: Union[MCPTool, Dict[str, Any]]) -> MCPTool:
        """Save or update an MCP tool."""
        if isinstance(tool, dict):
            t = MCPTool(**tool)
        else:
            t = tool

        now = datetime.now().isoformat()
        schema_str = json.dumps(t.input_schema) if t.input_schema else None

        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO mcp_tools (
                    id, connector_id, name, description, input_schema, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name,
                    description=excluded.description,
                    input_schema=excluded.input_schema
            """, (
                t.id,
                t.connector_id,
                t.name,
                t.description,
                schema_str,
                t.created_at or now
            ))
            conn.commit()

        return self.get_mcp_tool(t.id)

    def get_mcp_tool(self, tool_id: str) -> Optional[MCPTool]:
        """Retrieve an MCP tool by ID."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM mcp_tools WHERE id = ?", (tool_id,)).fetchone()
            if not row:
                return None
            d = dict(row)
            if d.get("input_schema"):
                try:
                    d["input_schema"] = json.loads(d["input_schema"])
                except Exception:
                    pass
            return MCPTool(**d)

    def list_mcp_tools(self, connector_id: Optional[str] = None) -> List[MCPTool]:
        """List MCP tools, optionally filtered by connector."""
        query = "SELECT * FROM mcp_tools"
        params = []
        if connector_id:
            query += " WHERE connector_id = ?"
            params.append(connector_id)
        query += " ORDER BY name ASC"

        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            results = []
            for r in rows:
                d = dict(r)
                if d.get("input_schema"):
                    try:
                        d["input_schema"] = json.loads(d["input_schema"])
                    except Exception:
                        pass
                results.append(MCPTool(**d))
            return results

    def save_mcp_tool_call(self, call: Union[MCPToolCall, Dict[str, Any]]) -> MCPToolCall:
        """Record an MCP tool execution invocation."""
        if isinstance(call, dict):
            tc = MCPToolCall(**call)
        else:
            tc = call

        if not tc.id:
            tc.id = f"mcpcall_{uuid.uuid4().hex[:12]}"
        now = datetime.now().isoformat()
        if not tc.started_at:
            tc.started_at = now

        args_str = json.dumps(tc.arguments) if tc.arguments else None

        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO mcp_tool_calls (
                    id, connector_id, tool_id, agent_id, task_id, run_id,
                    status, arguments, result, error, started_at, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    status=excluded.status,
                    result=excluded.result,
                    error=excluded.error,
                    completed_at=excluded.completed_at
            """, (
                tc.id,
                tc.connector_id,
                tc.tool_id,
                tc.agent_id,
                tc.task_id,
                tc.run_id,
                tc.status,
                args_str,
                tc.result,
                tc.error,
                tc.started_at,
                tc.completed_at
            ))
            conn.commit()

        return self.get_mcp_tool_call(tc.id)

    def get_mcp_tool_call(self, call_id: str) -> Optional[MCPToolCall]:
        """Retrieve an MCP tool call by ID."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM mcp_tool_calls WHERE id = ?", (call_id,)).fetchone()
            if not row:
                return None
            d = dict(row)
            if d.get("arguments"):
                try:
                    d["arguments"] = json.loads(d["arguments"])
                except Exception:
                    pass
            return MCPToolCall(**d)

    def list_mcp_tool_calls(
        self,
        agent_id: Optional[str] = None,
        connector_id: Optional[str] = None,
        task_id: Optional[str] = None,
        limit: int = 100
    ) -> List[MCPToolCall]:
        """List historical MCP tool calls."""
        query = "SELECT * FROM mcp_tool_calls WHERE 1=1"
        params = []
        if agent_id:
            query += " AND agent_id = ?"
            params.append(agent_id)
        if connector_id:
            query += " AND connector_id = ?"
            params.append(connector_id)
        if task_id:
            query += " AND task_id = ?"
            params.append(task_id)
        query += " ORDER BY started_at DESC LIMIT ?"
        params.append(limit)

        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            results = []
            for r in rows:
                d = dict(r)
                if d.get("arguments"):
                    try:
                        d["arguments"] = json.loads(d["arguments"])
                    except Exception:
                        pass
                results.append(MCPToolCall(**d))
            return results

    def update_mcp_tool_call(
        self,
        call_id: str,
        status: str,
        result: Optional[str] = None,
        error: Optional[str] = None,
        completed_at: Optional[str] = None
    ) -> Optional[MCPToolCall]:
        """Update the status and result of an MCP tool call."""
        fields = ["status = ?"]
        params = [status]
        if result is not None:
            fields.append("result = ?")
            params.append(result)
        if error is not None:
            fields.append("error = ?")
            params.append(error)
        if completed_at is not None:
            fields.append("completed_at = ?")
            params.append(completed_at)

        params.append(call_id)
        with self._get_connection() as conn:
            conn.execute(f"UPDATE mcp_tool_calls SET {', '.join(fields)} WHERE id = ?", params)
            conn.commit()

        return self.get_mcp_tool_call(call_id)

    def add_mcp_permission(self, agent_id: str, connector_id: str, tool_id: Optional[str] = None) -> Dict[str, Any]:
        """Grant an agent permission to use a connector or specific tool."""
        perm_id = f"perm_{uuid.uuid4().hex[:10]}"
        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO mcp_agent_permissions (id, agent_id, connector_id, tool_id, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (perm_id, agent_id, connector_id, tool_id, now))
            conn.commit()
        return {"id": perm_id, "agent_id": agent_id, "connector_id": connector_id, "tool_id": tool_id}

    def get_agent_mcp_permissions(self, agent_id: str) -> List[Dict[str, Any]]:
        """List active MCP permissions for an agent."""
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM mcp_agent_permissions WHERE agent_id = ?", (agent_id,)).fetchall()
            return [dict(r) for r in rows]

    def revoke_mcp_permission(self, agent_id: str, connector_id: str, tool_id: Optional[str] = None) -> bool:
        """Revoke MCP permission from an agent."""
        query = "DELETE FROM mcp_agent_permissions WHERE agent_id = ? AND connector_id = ?"
        params = [agent_id, connector_id]
        if tool_id is not None:
            query += " AND tool_id = ?"
            params.append(tool_id)
        with self._get_connection() as conn:
            cursor = conn.execute(query, params)
            conn.commit()
            return cursor.rowcount > 0

    def check_agent_mcp_permission(self, agent_id: str, connector_id: str, tool_name: Optional[str] = None) -> bool:
        """
        Check if an agent has permission to invoke an MCP connector/tool.
        Checks:
        1. Agent config dangerously_skip_permissions
        2. Agent config mcp_permissions list (e.g. ['github', 'google_workspace.*'])
        3. Database mcp_agent_permissions table
        """
        agent = self.get_agent(agent_id)
        if not agent:
            return False
        if getattr(agent, "dangerously_skip_permissions", False):
            return True

        # Check in agent config mcp_permissions
        agent_mcp = getattr(agent, "mcp_permissions", []) or []
        for p in agent_mcp:
            p_clean = p.strip().lower()
            if p_clean in ("*", "all"):
                return True
            if p_clean == connector_id.lower() or p_clean == f"{connector_id.lower()}.*":
                return True
            if tool_name and p_clean == f"{connector_id.lower()}.{tool_name.lower()}":
                return True

        # Check in DB table
        perms = self.get_agent_mcp_permissions(agent_id)
        for perm in perms:
            if perm["connector_id"].lower() == connector_id.lower():
                if not perm.get("tool_id"):
                    return True
                if tool_name and perm["tool_id"].lower() == tool_name.lower():
                    return True

        return False

    # -------------------------------------------------------------
    # Agent Teams persistence methods
    # -------------------------------------------------------------
    def create_agent_team(self, team_data: Dict[str, Any]) -> AgentTeam:
        """Create a new temporary agent team with assigned members."""
        team_id = team_data.get("id") or f"team_{uuid.uuid4().hex[:10]}"
        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO agent_teams (id, name, manager_agent_id, project_id, description, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                team_id,
                team_data["name"],
                team_data["manager_agent_id"],
                team_data.get("project_id"),
                team_data.get("description"),
                team_data.get("status", "ACTIVE"),
                now,
                now
            ))
            # Insert members if provided
            for member in team_data.get("members", []):
                agent_id = member["agent_id"] if isinstance(member, dict) else member
                role = member.get("role_in_team", "MEMBER") if isinstance(member, dict) else "MEMBER"
                conn.execute("""
                    INSERT OR REPLACE INTO team_members (team_id, agent_id, role_in_team, joined_at)
                    VALUES (?, ?, ?, ?)
                """, (team_id, agent_id, role, now))
            conn.commit()

        return self.get_agent_team(team_id)

    def get_agent_team(self, team_id: str) -> Optional[AgentTeam]:
        """Get an agent team with its current members."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM agent_teams WHERE id = ?", (team_id,)).fetchone()
            if not row:
                return None
            team_dict = dict(row)
            m_rows = conn.execute("SELECT agent_id, role_in_team, joined_at FROM team_members WHERE team_id = ?", (team_id,)).fetchall()
            team_dict["members"] = [dict(mr) for mr in m_rows]
            return AgentTeam(**team_dict)

    def list_agent_teams(self, manager_agent_id: Optional[str] = None, project_id: Optional[str] = None, status: Optional[str] = None) -> List[AgentTeam]:
        """List active or completed agent teams."""
        query = "SELECT * FROM agent_teams WHERE 1=1"
        params = []
        if manager_agent_id:
            query += " AND manager_agent_id = ?"
            params.append(manager_agent_id)
        if project_id:
            query += " AND project_id = ?"
            params.append(project_id)
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY created_at DESC"


        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            teams = []
            for r in rows:
                t_dict = dict(r)
                m_rows = conn.execute("SELECT agent_id, role_in_team, joined_at FROM team_members WHERE team_id = ?", (t_dict["id"],)).fetchall()
                t_dict["members"] = [dict(mr) for mr in m_rows]
                teams.append(AgentTeam(**t_dict))
            return teams

    def add_team_member(self, team_id: str, agent_id: str, role_in_team: str = "MEMBER") -> bool:
        """Add an agent to a team."""
        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO team_members (team_id, agent_id, role_in_team, joined_at)
                VALUES (?, ?, ?, ?)
            """, (team_id, agent_id, role_in_team, now))
            conn.commit()
            return True

    def remove_team_member(self, team_id: str, agent_id: str) -> bool:
        """Remove an agent from a team."""
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM team_members WHERE team_id = ? AND agent_id = ?", (team_id, agent_id))
            conn.commit()
            return cursor.rowcount > 0

    def update_agent_team(self, team_id: str, **kwargs) -> Optional[AgentTeam]:
        """Update an agent team's attributes or status."""
        fields = []
        params = []
        now = datetime.now().isoformat()
        for k, v in kwargs.items():
            if k in ("name", "description", "status", "project_id"):
                fields.append(f"{k} = ?")
                params.append(v)
        if fields:
            fields.append("updated_at = ?")
            params.append(now)
            params.append(team_id)
            with self._get_connection() as conn:
                conn.execute(f"UPDATE agent_teams SET {', '.join(fields)} WHERE id = ?", params)
                conn.commit()
        return self.get_agent_team(team_id)

    # =========================================================================
    # Departments & Budgets (Aligned with user decisions: HARD_STOP on API_KEY)
    # =========================================================================

    def create_department(
        self,
        id: str,
        name: str,
        description: Optional[str] = None,
        monthly_budget_usd: float = 100.0,
        budget_action: str = "HARD_STOP",
        alert_threshold_pct: float = 80.0
    ) -> Department:
        """Create a new department."""
        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO departments (id, name, description, monthly_budget_usd, budget_action, alert_threshold_pct, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (id, name, description, monthly_budget_usd, budget_action, alert_threshold_pct, now, now))
            conn.commit()
        return self.get_department(id)

    def get_department(self, id: str) -> Optional[Department]:
        """Fetch a department by ID."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM departments WHERE id = ?", (id,)).fetchone()
            if not row:
                return None
            d = dict(row)
            return Department(
                id=d['id'],
                name=d['name'],
                description=d.get('description'),
                monthly_budget_usd=float(d.get('monthly_budget_usd') or 100.0),
                current_spend_usd=self.get_department_monthly_spend(id),
                budget_action=d.get('budget_action') or 'HARD_STOP',
                alert_threshold_pct=float(d.get('alert_threshold_pct') or 80.0),
                created_at=d.get('created_at'),
                updated_at=d.get('updated_at')
            )

    def list_departments(self) -> List[Department]:
        """List all departments."""
        with self._get_connection() as conn:
            rows = conn.execute("SELECT id FROM departments ORDER BY name ASC").fetchall()
            return [self.get_department(r['id']) for r in rows if r['id']]

    def update_department(self, id: str, **kwargs) -> Optional[Department]:
        """Update department configuration."""
        fields = []
        params = []
        now = datetime.now().isoformat()
        for k in ("name", "description", "monthly_budget_usd", "budget_action", "alert_threshold_pct"):
            if k in kwargs and kwargs[k] is not None:
                fields.append(f"{k} = ?")
                params.append(kwargs[k])
        if fields:
            fields.append("updated_at = ?")
            params.append(now)
            params.append(id)
            with self._get_connection() as conn:
                conn.execute(f"UPDATE departments SET {', '.join(fields)} WHERE id = ?", params)
                conn.commit()
        return self.get_department(id)

    def get_department_monthly_spend(self, department_id: str, year: Optional[int] = None, month: Optional[int] = None) -> float:
        """
        Calculate actual monthly spend for a department.
        Per user decision: ONLY enforces and counts runs using API keys (cost_source='API_KEY').
        Subscription CLI runs are zero-billed against the budget.
        """
        now = datetime.now()
        y = year or now.year
        m = month or now.month
        month_prefix = f"{y:04d}-{m:02d}%"

        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT COALESCE(SUM(total_cost_usd), 0.0) as total
                FROM workflow_executions
                WHERE department_id = ?
                  AND created_at LIKE ?
            """, (department_id, month_prefix))
            row = cursor.fetchone()
            return float(row['total']) if row else 0.0

    def check_department_budget(self, department_id: str, requested_cost: float = 0.0) -> Dict[str, Any]:
        """
        Check department budget limits against monthly spend.
        Action: HARD_STOP (per user decision) when spend >= monthly_budget_usd.
        """
        dept = self.get_department(department_id)
        if not dept:
            return {"allowed": True, "reason": "No department limit"}

        current_spend = dept.current_spend_usd
        budget = dept.monthly_budget_usd

        if (current_spend + requested_cost) >= budget:
            return {
                "allowed": False,
                "action": dept.budget_action,
                "department_id": department_id,
                "current_spend_usd": current_spend,
                "monthly_budget_usd": budget,
                "message": f"Department '{dept.name}' exceeded monthly budget (${current_spend:.2f}/${budget:.2f}). Additional budget required."
            }

        is_alert = (current_spend / budget) * 100.0 >= dept.alert_threshold_pct if budget > 0 else False
        return {
            "allowed": True,
            "department_id": department_id,
            "current_spend_usd": current_spend,
            "monthly_budget_usd": budget,
            "is_alert": is_alert
        }

    # =========================================================================
    # Workflows & Executions
    # =========================================================================

    def create_workflow(
        self,
        id: str,
        name: str,
        definition_json: str,
        department_id: Optional[str] = None,
        description: Optional[str] = None,
        cron_expression: Optional[str] = None,
        webhook_enabled: bool = True
    ) -> Workflow:
        """Create a workflow definition."""
        now = datetime.now().isoformat()
        webhook_token = f"whk_{uuid.uuid4().hex}" if webhook_enabled else None
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO workflows (id, name, description, department_id, definition_json, webhook_enabled, webhook_token, cron_expression, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
            """, (id, name, description, department_id, definition_json, 1 if webhook_enabled else 0, webhook_token, cron_expression, now, now))
            conn.commit()
        return self.get_workflow(id)

    def get_workflow(self, id: str) -> Optional[Workflow]:
        """Get a workflow by ID."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM workflows WHERE id = ?", (id,)).fetchone()
            if not row:
                return None
            d = dict(row)
            return Workflow(
                id=d['id'],
                name=d['name'],
                description=d.get('description'),
                department_id=d.get('department_id'),
                definition_json=d.get('definition_json') or "{}",
                webhook_enabled=bool(d.get('webhook_enabled', 1)),
                webhook_token=d.get('webhook_token'),
                cron_expression=d.get('cron_expression'),
                is_active=bool(d.get('is_active', 1)),
                created_at=d.get('created_at'),
                updated_at=d.get('updated_at')
            )

    def update_workflow(self, id: str, **kwargs) -> Optional[Workflow]:
        """Update workflow configuration, definition, and channel bindings."""
        fields = []
        params = []
        now = datetime.now().isoformat()
        allowed_keys = ("name", "description", "department_id", "definition_json", "webhook_enabled", "cron_expression", "is_active")
        for k in allowed_keys:
            if k in kwargs and kwargs[k] is not None:
                fields.append(f"{k} = ?")
                if k in ("webhook_enabled", "is_active"):
                    params.append(1 if kwargs[k] else 0)
                else:
                    params.append(kwargs[k])
        if fields:
            fields.append("updated_at = ?")
            params.append(now)
            params.append(id)
            with self._get_connection() as conn:
                conn.execute(f"UPDATE workflows SET {', '.join(fields)} WHERE id = ?", params)
                conn.commit()
        return self.get_workflow(id)

    def get_workflow_by_webhook_token(self, webhook_token: str) -> Optional[Workflow]:
        """Lookup an active workflow by its incoming webhook token."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM workflows WHERE webhook_token = ? AND is_active = 1", (webhook_token,)).fetchone()
            if not row:
                return None
            d = dict(row)
            return Workflow(
                id=d['id'],
                name=d['name'],
                description=d.get('description'),
                department_id=d.get('department_id'),
                definition_json=d.get('definition_json') or "{}",
                webhook_enabled=bool(d.get('webhook_enabled', 1)),
                webhook_token=d.get('webhook_token'),
                cron_expression=d.get('cron_expression'),
                is_active=bool(d.get('is_active', 1)),
                created_at=d.get('created_at'),
                updated_at=d.get('updated_at')
            )

    def list_workflows(self, department_id: Optional[str] = None, active_only: bool = False) -> List[Workflow]:
        """List workflows with filtering."""
        query = "SELECT id FROM workflows WHERE 1=1"
        params = []
        if department_id:
            query += " AND department_id = ?"
            params.append(department_id)
        if active_only:
            query += " AND is_active = 1"
        query += " ORDER BY name ASC"

        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self.get_workflow(r['id']) for r in rows if r['id']]

    def delete_workflow(self, id: str) -> bool:
        """Delete a workflow and cascade delete executions."""
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM workflows WHERE id = ?", (id,))
            conn.commit()
            return cursor.rowcount > 0

    def create_workflow_execution(
        self,
        execution_id: str,
        workflow_id: str,
        trigger_type: str,
        trigger_payload: Optional[str] = None,
        department_id: Optional[str] = None,
        sandbox_path: Optional[str] = None
    ) -> WorkflowExecution:
        """Create a new workflow execution instance."""
        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO workflow_executions (
                    id, workflow_id, trigger_type, trigger_payload, status,
                    department_id, sandbox_path, started_at, created_at
                ) VALUES (?, ?, ?, ?, 'RUNNING', ?, ?, ?, ?)
            """, (execution_id, workflow_id, trigger_type, trigger_payload, department_id, sandbox_path, now, now))
            conn.commit()
        return self.get_workflow_execution(execution_id)

    def get_workflow_execution(self, execution_id: str) -> Optional[WorkflowExecution]:
        """Get workflow execution status and metrics."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM workflow_executions WHERE id = ?", (execution_id,)).fetchone()
            if not row:
                return None
            d = dict(row)
            return WorkflowExecution(
                id=d['id'],
                workflow_id=d['workflow_id'],
                trigger_type=d['trigger_type'],
                trigger_payload=d.get('trigger_payload'),
                status=d.get('status') or 'PENDING',
                department_id=d.get('department_id'),
                sandbox_path=d.get('sandbox_path'),
                total_input_tokens=int(d.get('total_input_tokens') or 0),
                total_output_tokens=int(d.get('total_output_tokens') or 0),
                total_cost_usd=float(d.get('total_cost_usd') or 0.0),
                started_at=d.get('started_at'),
                completed_at=d.get('completed_at'),
                error_message=d.get('error_message'),
                created_at=d.get('created_at')
            )

    def update_workflow_execution(self, execution_id: str, **kwargs) -> Optional[WorkflowExecution]:
        """Update status, token counts, or error for an execution."""
        fields = []
        params = []
        for k in ("status", "total_input_tokens", "total_output_tokens", "total_cost_usd", "completed_at", "error_message"):
            if k in kwargs and kwargs[k] is not None:
                fields.append(f"{k} = ?")
                params.append(kwargs[k])
        if fields:
            params.append(execution_id)
            with self._get_connection() as conn:
                conn.execute(f"UPDATE workflow_executions SET {', '.join(fields)} WHERE id = ?", params)
                conn.commit()
        return self.get_workflow_execution(execution_id)

    def save_run_evaluation(
        self,
        id: str,
        execution_id: str,
        workflow_id: str,
        rating: Optional[int] = None,
        feedback_notes: Optional[str] = None,
        lessons_extracted: Optional[str] = None
    ) -> RunEvaluation:
        """Save a human or automated evaluation for learning."""
        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO run_evaluations (id, execution_id, workflow_id, rating, feedback_notes, lessons_extracted, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (id, execution_id, workflow_id, rating, feedback_notes, lessons_extracted, now))
            conn.commit()
        return RunEvaluation(
            id=id,
            execution_id=execution_id,
            workflow_id=workflow_id,
            rating=rating,
            feedback_notes=feedback_notes,
            lessons_extracted=lessons_extracted,
            created_at=now
        )


# Global database instance
db_manager = DatabaseManager()