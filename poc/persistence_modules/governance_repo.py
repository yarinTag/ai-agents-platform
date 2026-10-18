"""
Department MCP Access & Tool-Level Governance Repository Mixin.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any, Union
import uuid
from .models import DepartmentMCPAccess
from shared.validators import parse_allowed_tools


class GovernanceRepositoryMixin:
    """Mixin providing department MCP access grants and tool-level permission checks."""

    def grant_department_mcp_access(
        self,
        department_id: str,
        connector_id: str,
        allowed_tools: Union[str, List[str]] = "*",
        organization_id: Optional[str] = None,
        granted_by_user_id: Optional[str] = None
    ) -> DepartmentMCPAccess:
        """
        Grant or update a department's access to an MCP connector with tool-level filtering.
        """
        tools_str, _ = parse_allowed_tools(allowed_tools)

        if not organization_id:
            dept = self.get_department(department_id)
            if dept:
                organization_id = dept.organization_id

        access_id = f"dmcp_{uuid.uuid4().hex[:12]}"
        now = datetime.now().isoformat()

        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR IGNORE INTO mcp_connectors (id, name, provider, status)
                VALUES (?, ?, ?, 'CONNECTED')
            """, (connector_id, connector_id.replace('-', ' ').replace('_', ' ').title(), connector_id))

            conn.execute("""
                INSERT INTO department_mcp_access (
                    id, organization_id, department_id, connector_id, allowed_tools, is_active, granted_by_user_id, granted_at
                ) VALUES (?, ?, ?, ?, ?, 1, ?, ?)
                ON CONFLICT(department_id, connector_id) DO UPDATE SET
                    allowed_tools = excluded.allowed_tools,
                    is_active = 1,
                    organization_id = COALESCE(excluded.organization_id, department_mcp_access.organization_id),
                    granted_by_user_id = excluded.granted_by_user_id,
                    granted_at = excluded.granted_at
            """, (access_id, organization_id, department_id, connector_id, tools_str, granted_by_user_id, now))
            conn.commit()

        access = self.get_department_mcp_access(department_id, connector_id)
        if not access:
            raise RuntimeError(f"Failed to grant MCP access to department {department_id}")
        return access

    def revoke_department_mcp_access(self, department_id: str, connector_id: str) -> bool:
        """Revoke a department's access to an MCP connector (soft-delete / deactivate)."""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                UPDATE department_mcp_access
                SET is_active = 0
                WHERE department_id = ? AND connector_id = ?
            """, (department_id, connector_id))
            conn.commit()
            return cursor.rowcount > 0

    def get_department_mcp_access(self, department_id: str, connector_id: str) -> Optional[DepartmentMCPAccess]:
        """Get active MCP access record for department and connector."""
        with self._get_connection() as conn:
            row = conn.execute("""
                SELECT * FROM department_mcp_access
                WHERE department_id = ? AND connector_id = ? AND is_active = 1
            """, (department_id, connector_id)).fetchone()
            if not row:
                return None
            return DepartmentMCPAccess(
                id=row['id'],
                department_id=row['department_id'],
                connector_id=row['connector_id'],
                allowed_tools=row['allowed_tools'] or "*",
                organization_id=row['organization_id'],
                is_active=bool(row['is_active']),
                granted_by_user_id=row['granted_by_user_id'],
                granted_at=row['granted_at']
            )

    def list_department_mcp_access(self, department_id: str) -> List[DepartmentMCPAccess]:
        """List all active MCP grants for a department."""
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM department_mcp_access
                WHERE department_id = ? AND is_active = 1
                ORDER BY connector_id ASC
            """, (department_id,)).fetchall()
            return [
                DepartmentMCPAccess(
                    id=r['id'],
                    department_id=r['department_id'],
                    connector_id=r['connector_id'],
                    allowed_tools=r['allowed_tools'] or "*",
                    organization_id=r['organization_id'],
                    is_active=bool(r['is_active']),
                    granted_by_user_id=r['granted_by_user_id'],
                    granted_at=r['granted_at']
                )
                for r in rows
            ]

    def check_department_mcp_permission(
        self,
        department_id: Optional[str],
        connector_id: str,
        tool_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Check if a department is permitted to access an MCP connector and an optional specific tool.
        """
        if not department_id:
            return {
                "allowed": True,
                "reason": "No department restriction applied (unassigned/local access)",
                "allowed_tools": ["*"]
            }

        access = self.get_department_mcp_access(department_id, connector_id)
        if not access:
            return {
                "allowed": False,
                "reason": f"Department '{department_id}' does not have granted access to MCP connector '{connector_id}'",
                "allowed_tools": []
            }

        allowed_raw, parsed_tools = parse_allowed_tools(access.allowed_tools or "*")

        if allowed_raw == "*":
            return {
                "allowed": True,
                "reason": f"Department '{department_id}' has full access to all tools in connector '{connector_id}'",
                "allowed_tools": ["*"]
            }

        if not tool_name:
            return {
                "allowed": True,
                "reason": f"Department '{department_id}' has filtered access to connector '{connector_id}'",
                "allowed_tools": parsed_tools
            }

        if tool_name in parsed_tools:
            return {
                "allowed": True,
                "reason": f"Tool '{tool_name}' is explicitly allowed for department '{department_id}'",
                "allowed_tools": parsed_tools
            }

        return {
            "allowed": False,
            "reason": f"Tool '{tool_name}' is blocked by department policy: not in allowed tools list for department '{department_id}' on connector '{connector_id}'",
            "allowed_tools": parsed_tools
        }
