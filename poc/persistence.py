"""
Persistence layer for the AI Agents Platform PoC.
Uses SQLite to store agents, projects, skills, and task runs.
"""

import sqlite3
import json
import os
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from pathlib import Path

# Import from local modules using absolute imports
from config import AgentConfig, ProjectConfig, Skill
from runtime_adapter import AgentRun, TaskStatus


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
                ("avatar", "TEXT")
            ]:
                try:
                    conn.execute(f"ALTER TABLE agents ADD COLUMN {col} {col_type}")
                except Exception:
                    pass

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
                    FOREIGN KEY (agent_id) REFERENCES agents (id),
                    FOREIGN KEY (project_id) REFERENCES projects (id)
                )
            """)

            # Create indexes for better query performance
            conn.execute("CREATE INDEX IF NOT EXISTS idx_task_runs_agent ON task_runs(agent_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_task_runs_project ON task_runs(project_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_task_runs_status ON task_runs(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_task_runs_created ON task_runs(created_at)")

            conn.commit()

    # Agent methods
    def save_agent(self, agent: AgentConfig):
        """Save or update an agent."""
        with self._get_connection() as conn:
            existing = conn.execute("SELECT created_at FROM agents WHERE id = ?", (agent.id,)).fetchone()
            created_at = existing['created_at'] if existing else (getattr(agent, "created_at", None) or datetime.now().isoformat())
            updated_at = datetime.now().isoformat()

            conn.execute("""
                INSERT INTO agents
                (id, name, description, system_prompt, skills, model, effort, max_tokens, temperature, repo_path, github_url, department, avatar, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    updated_at=excluded.updated_at
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
                str(updated_at)
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
                    repo_path=row['repo_path'] if 'repo_path' in row.keys() else None,
                    github_url=row['github_url'] if 'github_url' in row.keys() else None,
                    department=row['department'] if 'department' in row.keys() else 'Engineering',
                    avatar=row['avatar'] if 'avatar' in row.keys() else None,
                    created_at=str(row['created_at']) if 'created_at' in row.keys() and row['created_at'] else None,
                    updated_at=str(row['updated_at']) if 'updated_at' in row.keys() and row['updated_at'] else None
                )
        return None

    def list_agents(self) -> List[AgentConfig]:
        """List all agents."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM agents ORDER BY name")
            return [
                AgentConfig(
                    id=row['id'],
                    name=row['name'],
                    description=row['description'],
                    system_prompt=row['system_prompt'],
                    skills=json.loads(row['skills']) if row['skills'] else [],
                    model=row['model'],
                    effort=row['effort'],
                    max_tokens=row['max_tokens'],
                    temperature=row['temperature'],
                    repo_path=row['repo_path'] if 'repo_path' in row.keys() else None,
                    github_url=row['github_url'] if 'github_url' in row.keys() else None,
                    department=row['department'] if 'department' in row.keys() else 'Engineering',
                    avatar=row['avatar'] if 'avatar' in row.keys() else None,
                    created_at=str(row['created_at']) if 'created_at' in row.keys() and row['created_at'] else None,
                    updated_at=str(row['updated_at']) if 'updated_at' in row.keys() and row['updated_at'] else None
                )
                for row in cursor.fetchall()
            ]

    def delete_agent(self, agent_id: str):
        """Delete an agent and clean up any linked task runs."""
        with self._get_connection() as conn:
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
    def save_task_run(self, run: AgentRun):
        """Save or update a task run."""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO task_runs
                (run_id, agent_id, project_id, prompt, status, created_at, started_at, ended_at,
                 result, error, exit_code, events)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                run.run_id,
                run.agent_id,
                run.project_id,
                run.prompt,
                run.status.value,
                run.created_at.isoformat() if run.created_at else None,
                run.started_at.isoformat() if run.started_at else None,
                run.ended_at.isoformat() if run.ended_at else None,
                run.result,
                run.error,
                run.exit_code,
                json.dumps(run.events) if run.events else None
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
                    events=json.loads(row['events']) if row['events'] else []
                )
        return None

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
                params.append(status.value)

            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)

            cursor = conn.execute(query, params)
            return [
                AgentRun(
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
                    events=json.loads(row['events']) if row['events'] else []
                )
                for row in cursor.fetchall()
            ]

    def delete_task_run(self, run_id: str):
        """Delete a task run."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM task_runs WHERE run_id = ?", (run_id,))
            conn.commit()


# Global database instance
db_manager = DatabaseManager()