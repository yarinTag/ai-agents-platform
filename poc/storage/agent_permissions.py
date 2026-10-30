"""Agent Permissions persistence operations; dependencies are injected callbacks."""
from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid


class AgentPermissionsRepository:
    def __init__(self, connection_factory, get_agent):
        self._get_connection = connection_factory
        self.get_agent = get_agent

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
