"""Maintenance persistence operations; dependencies are injected callbacks."""
from typing import Optional


class MaintenanceRepository:
    def __init__(self, connection_factory, _seed_default_agents, _seed_default_templates):
        self._get_connection = connection_factory
        self._seed_default_agents = _seed_default_agents
        self._seed_default_templates = _seed_default_templates

    def claim_orphaned_records(self, org_id: str, default_dept_id: Optional[str] = None) -> None:
        """Assign any legacy/orphaned records (organization_id IS NULL) to the specified organization."""
        if not org_id:
            return
        with self._get_connection() as conn:
            if not default_dept_id:
                dept_row = conn.execute(
                    "SELECT id FROM departments WHERE organization_id = ? ORDER BY created_at ASC LIMIT 1",
                    (org_id,)
                ).fetchone()
                if dept_row:
                    default_dept_id = dept_row["id"]
            for tbl in ("projects", "task_runs", "mcp_connectors"):
                try:
                    conn.execute(f"UPDATE {tbl} SET organization_id = ? WHERE organization_id IS NULL", (org_id,))
                except Exception:
                    pass
            if default_dept_id:
                for tbl in ("agents", "workflows"):
                    try:
                        conn.execute(
                            f"UPDATE {tbl} SET organization_id = ?, department_id = COALESCE(department_id, ?) WHERE organization_id IS NULL OR department_id IS NULL",
                            (org_id, default_dept_id)
                        )
                    except Exception:
                        pass
            else:
                for tbl in ("agents", "workflows"):
                    try:
                        conn.execute(f"UPDATE {tbl} SET organization_id = ? WHERE organization_id IS NULL", (org_id,))
                    except Exception:
                        pass
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
