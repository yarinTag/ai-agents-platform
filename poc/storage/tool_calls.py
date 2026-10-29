"""Tool Calls persistence operations; dependencies are injected callbacks."""
from .row_mapping import decode_json_columns
from .records import MCPToolCall
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
import json
import uuid


class ToolCallsRepository:
    def __init__(self, connection_factory):
        self._get_connection = connection_factory

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
            return MCPToolCall(**decode_json_columns(row, 'arguments'))

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
            return [MCPToolCall(**decode_json_columns(row, 'arguments')) for row in rows]

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
