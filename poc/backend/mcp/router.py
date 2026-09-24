"""
REST API Router for MCP (Model Context Protocol) subsystem.
Exposes endpoints for connector status, tool discovery, execution, permissions, and history.
"""

from fastapi import APIRouter, HTTPException, Depends, status, Query
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

from ..dependencies import (
    get_db_manager, get_event_service, get_mcp_registry, get_mcp_executor,
    DatabaseManager, EventService, EventType
)
from persistence import MCPConnector, MCPTool, MCPToolCall
from mcp import MCPRegistry, MCPExecutor, MCPPermissionDeniedError

router = APIRouter()


class ConnectorCreateRequest(BaseModel):
    id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    provider: str = Field(..., min_length=1)
    configuration: Optional[Dict[str, Any]] = None
    capabilities: Optional[List[str]] = None


class ToolInvokeRequest(BaseModel):
    agent_id: str = Field(..., min_length=1)
    connector_id: str = Field(..., min_length=1)
    tool_name: str = Field(..., min_length=1)
    arguments: Dict[str, Any] = Field(default_factory=dict)
    task_id: Optional[str] = None
    run_id: Optional[str] = None


class PermissionGrantRequest(BaseModel):
    agent_id: str = Field(..., min_length=1)
    connector_id: str = Field(..., min_length=1)
    tool_id: Optional[str] = None


class ConnectorSummaryResponse(BaseModel):
    id: str
    name: str
    provider: str
    status: str
    capabilities: Optional[List[str]] = None
    tool_count: int = 0
    active_calls: int = 0
    last_activity: Optional[str] = None
    error_message: Optional[str] = None


@router.get("/connectors", response_model=List[ConnectorSummaryResponse])
async def list_connectors(
    db: DatabaseManager = Depends(get_db_manager),
    registry: MCPRegistry = Depends(get_mcp_registry)
):
    """List all registered MCP connectors with status, tool counts, and activity."""
    # Ensure default connectors seeded
    registry.seed_default_connectors()
    connectors = db.list_mcp_connectors()
    all_calls = db.list_mcp_tool_calls(limit=100)

    summaries = []
    for c in connectors:
        tools = db.list_mcp_tools(connector_id=c.id)
        c_calls = [tc for tc in all_calls if tc.connector_id == c.id]
        active = sum(1 for tc in c_calls if tc.status == "STARTED")
        last_act = c_calls[0].started_at if c_calls else c.created_at

        summaries.append(ConnectorSummaryResponse(
            id=c.id,
            name=c.name,
            provider=c.provider,
            status=c.status,
            capabilities=c.capabilities,
            tool_count=len(tools),
            active_calls=active,
            last_activity=last_act,
            error_message=c.error_message
        ))
    return summaries


@router.get("/connectors/{connector_id}")
async def get_connector_detail(
    connector_id: str,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Retrieve full connector details with its registered tools and recent calls."""
    connector = db.get_mcp_connector(connector_id)
    if not connector:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"MCP Connector '{connector_id}' not found"
        )
    tools = db.list_mcp_tools(connector_id=connector_id)
    calls = db.list_mcp_tool_calls(connector_id=connector_id, limit=20)

    res = connector.to_dict()
    res["tools"] = [t.to_dict() for t in tools]
    res["recent_calls"] = [tc.to_dict() for tc in calls]
    return res


@router.post("/connectors", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def register_connector(
    req: ConnectorCreateRequest,
    db: DatabaseManager = Depends(get_db_manager),
    event_service: EventService = Depends(get_event_service)
):
    """Register or connect a new MCP server."""
    conn = MCPConnector(
        id=req.id,
        name=req.name,
        provider=req.provider,
        status="CONNECTED",
        configuration=req.configuration,
        capabilities=req.capabilities
    )
    saved = db.save_mcp_connector(conn)

    try:
        event_service.emit(
            event_type=EventType.MCP_CONNECTION_CREATED,
            payload=saved.to_dict(),
            source="mcp_router"
        )
    except Exception:
        pass

    return saved.to_dict()


@router.delete("/connectors/{connector_id}")
async def disconnect_connector(
    connector_id: str,
    db: DatabaseManager = Depends(get_db_manager),
    event_service: EventService = Depends(get_event_service)
):
    """Disconnect and remove an MCP connector."""
    deleted = db.delete_mcp_connector(connector_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connector '{connector_id}' not found"
        )
    try:
        event_service.emit(
            event_type=EventType.MCP_CONNECTION_DISCONNECTED,
            payload={"connector_id": connector_id},
            source="mcp_router"
        )
    except Exception:
        pass
    return {"status": "deleted", "connector_id": connector_id}


@router.get("/tools", response_model=List[Dict[str, Any]])
async def list_tools(
    connector_id: Optional[str] = None,
    db: DatabaseManager = Depends(get_db_manager)
):
    """List available tools exposed across MCP connectors."""
    tools = db.list_mcp_tools(connector_id=connector_id)
    return [t.to_dict() for t in tools]


@router.post("/invoke", response_model=Dict[str, Any])
async def invoke_tool(
    req: ToolInvokeRequest,
    executor: MCPExecutor = Depends(get_mcp_executor)
):
    """
    Execute an MCP tool call on behalf of an agent.
    Enforces server-side permissions and emits real-time start/completion events.
    """
    try:
        result = executor.execute_tool(
            agent_id=req.agent_id,
            connector_id=req.connector_id,
            tool_name=req.tool_name,
            arguments=req.arguments,
            task_id=req.task_id,
            run_id=req.run_id
        )
        return result
    except MCPPermissionDeniedError as perm_err:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(perm_err)
        )
    except Exception as ex:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"MCP tool execution failed: {str(ex)}"
        )


@router.get("/calls", response_model=List[Dict[str, Any]])
async def list_tool_calls(
    agent_id: Optional[str] = None,
    connector_id: Optional[str] = None,
    task_id: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=200),
    db: DatabaseManager = Depends(get_db_manager)
):
    """List historical MCP tool invocations with status and execution details."""
    calls = db.list_mcp_tool_calls(agent_id=agent_id, connector_id=connector_id, task_id=task_id, limit=limit)
    return [c.to_dict() for c in calls]


@router.get("/permissions/{agent_id}", response_model=List[Dict[str, Any]])
async def get_permissions(
    agent_id: str,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Get active MCP permissions for an agent."""
    return db.get_agent_mcp_permissions(agent_id)


@router.post("/permissions", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def grant_permission(
    req: PermissionGrantRequest,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Grant an agent permission to invoke an MCP connector or specific tool."""
    return db.add_mcp_permission(
        agent_id=req.agent_id,
        connector_id=req.connector_id,
        tool_id=req.tool_id
    )


@router.delete("/permissions")
async def revoke_permission(
    agent_id: str,
    connector_id: str,
    tool_id: Optional[str] = None,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Revoke MCP permission from an agent."""
    revoked = db.revoke_mcp_permission(agent_id=agent_id, connector_id=connector_id, tool_id=tool_id)
    return {"status": "revoked" if revoked else "not_found"}
