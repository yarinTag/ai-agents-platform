"""Connectors persistence operations; dependencies are injected callbacks."""
from .row_mapping import decode_json_columns
from .records import MCPConnector, MCPTool
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
import json


class ConnectorsRepository:
    def __init__(self, connection_factory):
        self._get_connection = connection_factory

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
                    id, name, provider, status, configuration, capabilities, error_message, created_at, updated_at, organization_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name,
                    provider=excluded.provider,
                    status=excluded.status,
                    configuration=excluded.configuration,
                    capabilities=excluded.capabilities,
                    error_message=excluded.error_message,
                    updated_at=excluded.updated_at,
                    organization_id=COALESCE(excluded.organization_id, mcp_connectors.organization_id)
            """, (
                c.id,
                c.name,
                c.provider,
                c.status,
                cfg_str,
                caps_str,
                c.error_message,
                c.created_at or now,
                now,
                getattr(c, "organization_id", None)
            ))
            conn.commit()

        return self.get_mcp_connector(c.id)

    def get_mcp_connector(self, connector_id: str) -> Optional[MCPConnector]:
        """Retrieve an MCP connector by ID."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM mcp_connectors WHERE id = ?", (connector_id,)).fetchone()
            if not row:
                return None
            return MCPConnector(**decode_json_columns(row, 'configuration', 'capabilities'))

    def list_mcp_connectors(self, organization_id: Optional[str] = None) -> List[MCPConnector]:
        """List all registered MCP connectors, optionally scoped by organization."""
        with self._get_connection() as conn:
            if organization_id:
                rows = conn.execute("SELECT * FROM mcp_connectors WHERE organization_id = ? ORDER BY name ASC", (organization_id,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM mcp_connectors ORDER BY name ASC").fetchall()
            return [MCPConnector(**decode_json_columns(row, 'configuration', 'capabilities')) for row in rows]

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
            return MCPTool(**decode_json_columns(row, 'input_schema'))

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
            return [MCPTool(**decode_json_columns(row, 'input_schema')) for row in rows]
