"""Teams persistence operations; dependencies are injected callbacks."""
from .records import AgentTeam
from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid


class TeamsRepository:
    def __init__(self, connection_factory):
        self._get_connection = connection_factory

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

    @staticmethod
    def _row_to_team(conn, row) -> AgentTeam:
        team = dict(row)
        members = conn.execute(
            "SELECT agent_id, role_in_team, joined_at FROM team_members WHERE team_id = ?",
            (team["id"],),
        ).fetchall()
        team["members"] = [dict(member) for member in members]
        return AgentTeam(**team)

    def get_agent_team(self, team_id: str) -> Optional[AgentTeam]:
        """Get an agent team with its current members."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM agent_teams WHERE id = ?", (team_id,)).fetchone()
            if not row:
                return None
            return self._row_to_team(conn, row)

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
            return [self._row_to_team(conn, row) for row in rows]

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
