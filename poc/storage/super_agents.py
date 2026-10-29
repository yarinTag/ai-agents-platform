"""Super Agents persistence operations; dependencies are injected callbacks."""
from config import SuperAgentConfig
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
import json
import sqlite3


class SuperAgentsRepository:
    def __init__(self, connection_factory):
        self._get_connection = connection_factory

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
