"""Department Permissions persistence operations; dependencies are injected callbacks."""
from .records import DepartmentMCPAccess
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
import json
import uuid


def github_default_operations():
    from integrations.tool_definitions import OPERATIONS
    return {*OPERATIONS['github'], 'clone_repository', 'open_pull_request', 'merge_pull_request'}


class DepartmentPermissionsRepository:
    def __init__(self, connection_factory, get_department):
        self._get_connection = connection_factory
        self.get_department = get_department

    def _github_default(self, conn, department_id, connector_id):
        row = conn.execute("""SELECT c.organization_id,c.configuration,c.created_at
            FROM mcp_connectors c JOIN departments d ON d.organization_id=c.organization_id
            WHERE d.id=? AND c.id=? AND lower(c.provider)='github' AND c.status='CONNECTED'""",
            (department_id, connector_id)).fetchone()
        if not row:
            return None
        supported = github_default_operations()
        try:
            configuration = json.loads(row['configuration'] or '{}')
        except (TypeError, ValueError):
            return None
        if not isinstance(configuration, dict):
            return None
        configured = configuration.get('department_default_tools', sorted(supported))
        if not isinstance(configured, list) or not configured or any(
                not isinstance(tool, str) or tool not in supported for tool in configured):
            return None
        return DepartmentMCPAccess(id=f'inherited:{department_id}:{connector_id}',
            department_id=department_id, connector_id=connector_id, organization_id=row['organization_id'],
            allowed_tools=json.dumps(sorted(set(configured))), is_active=True,
            granted_by_user_id=None, granted_at=row['created_at'])

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
        allowed_tools can be '*' (all tools) or a list of specific tool names e.g. ['git_diff', 'list_issues'].
        """
        if isinstance(allowed_tools, list):
            tools_str = json.dumps(allowed_tools)
        elif isinstance(allowed_tools, str):
            tools_str = allowed_tools.strip()
        else:
            tools_str = "*"

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

    def inherit_department_github_access(self, department_id, connector_id):
        with self._get_connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            inherited = self._github_default(conn, department_id, connector_id)
            if inherited is None:
                return None
            conn.execute('DELETE FROM department_mcp_access WHERE department_id=? AND connector_id=?',
                         (department_id, connector_id))
            conn.commit()
            return inherited

    def revoke_department_mcp_access(self, department_id: str, connector_id: str) -> bool:
        """Revoke a department's access to an MCP connector (soft-delete / deactivate)."""
        with self._get_connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            cursor = conn.execute("""
                UPDATE department_mcp_access
                SET is_active = 0
                WHERE department_id = ? AND connector_id = ?
            """, (department_id, connector_id))
            if not cursor.rowcount:
                inherited = self._github_default(conn, department_id, connector_id)
                if inherited:
                    cursor = conn.execute("""INSERT INTO department_mcp_access
                        (id,organization_id,department_id,connector_id,allowed_tools,is_active)
                        VALUES (?,?,?,?,?,0)""", (f'dmcp_{uuid.uuid4().hex[:12]}',
                        inherited.organization_id, department_id, connector_id, '[]'))
            conn.commit()
            return cursor.rowcount > 0

    @staticmethod
    def _row_to_access(row) -> DepartmentMCPAccess:
        """Single persisted record mapping for get/list queries."""
        return DepartmentMCPAccess(
            id=row['id'],
            department_id=row['department_id'],
            connector_id=row['connector_id'],
            allowed_tools=row['allowed_tools'] or '*',
            organization_id=row['organization_id'],
            is_active=bool(row['is_active']),
            granted_by_user_id=row['granted_by_user_id'],
            granted_at=row['granted_at'],
        )

    def get_department_mcp_access(self, department_id: str, connector_id: str) -> Optional[DepartmentMCPAccess]:
        """Get active MCP access record for department and connector."""
        with self._get_connection() as conn:
            row = conn.execute("""
                SELECT * FROM department_mcp_access
                WHERE department_id = ? AND connector_id = ?
            """, (department_id, connector_id)).fetchone()
            if row:
                return self._row_to_access(row) if row['is_active'] else None
            return self._github_default(conn, department_id, connector_id)

    def list_department_mcp_access(self, department_id: str) -> List[DepartmentMCPAccess]:
        """List all active MCP grants for a department."""
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM department_mcp_access
                WHERE department_id = ?
                ORDER BY connector_id ASC
            """, (department_id,)).fetchall()
            overrides = {r['connector_id'] for r in rows}
            connectors = conn.execute("""SELECT c.id FROM mcp_connectors c
                JOIN departments d ON d.organization_id=c.organization_id
                WHERE d.id=? AND lower(c.provider)='github' AND c.status='CONNECTED' ORDER BY c.id""",
                (department_id,)).fetchall()
            inherited = [self._github_default(conn, department_id, c['id']) for c in connectors
                         if c['id'] not in overrides]
            return [self._row_to_access(r) for r in rows if r['is_active']] + [g for g in inherited if g]

    def check_department_mcp_permission(
        self,
        department_id: Optional[str],
        connector_id: str,
        tool_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Check if a department is permitted to access an MCP connector and an optional specific tool.
        Returns:
            {
                "allowed": bool,
                "reason": str,
                "allowed_tools": List[str]
            }
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

        allowed_raw = access.allowed_tools.strip() if access.allowed_tools else "*"

        if allowed_raw == "*":
            return {
                "allowed": True,
                "reason": f"Department '{department_id}' has full access to all tools in connector '{connector_id}'",
                "allowed_tools": ["*"]
            }

        parsed_tools = []
        try:
            if allowed_raw.startswith("["):
                parsed_tools = json.loads(allowed_raw)
            else:
                parsed_tools = [t.strip() for t in allowed_raw.split(",") if t.strip()]
        except Exception:
            parsed_tools = []

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
