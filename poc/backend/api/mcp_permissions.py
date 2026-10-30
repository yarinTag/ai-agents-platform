"""Mcp: permissions ownership."""

from fastapi import HTTPException, Depends, Request
from typing import Optional
from ..dependencies import get_db_manager, DatabaseManager
from ..security import get_current_org_id
from .mcp_models import PermissionGrantRequest, PermissionRevokeRequest
from fastapi import APIRouter

router = APIRouter()


@router.get("/permissions")
def list_agent_permissions(
    request: Request,
    agent_id: Optional[str] = None,
    db: DatabaseManager = Depends(get_db_manager)
):
    """List agent permissions for MCP connectors."""
    org_id = get_current_org_id(request)
    if agent_id:
        ag = db.get_agent(agent_id)
        if ag and org_id and getattr(ag, "organization_id", None) and ag.organization_id != org_id:
            return {"permissions": []}
        perms = db.get_agent_mcp_permissions(agent_id)
        return {"permissions": perms}

    # If no agent_id given, get permissions for all agents in org
    agents = db.list_agents(organization_id=org_id)
    all_perms = []
    for ag in agents:
        perms = db.get_agent_mcp_permissions(ag.id)
        for p in perms:
            p["agent_name"] = ag.name
            all_perms.append(p)
    return {"permissions": all_perms}



@router.post("/permissions/grant")
def grant_permission(
    req: PermissionGrantRequest,
    request: Request,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Grant an agent access to an MCP connector."""
    org_id = get_current_org_id(request)
    if org_id:
        ag = db.get_agent(req.agent_id)
        if ag and getattr(ag, "organization_id", None) and ag.organization_id != org_id:
            raise HTTPException(status_code=404, detail="Agent not found")
        conn = db.get_mcp_connector(req.connector_id)
        if conn and getattr(conn, "organization_id", None) and conn.organization_id != org_id:
            raise HTTPException(status_code=404, detail="Connector not found")
    perm = db.add_mcp_permission(agent_id=req.agent_id, connector_id=req.connector_id, tool_id=req.tool_id)
    return {"status": "success", "permission": perm}



@router.post("/permissions/revoke")
def revoke_permission(
    req: PermissionRevokeRequest,
    request: Request,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Revoke an agent's access to an MCP connector."""
    org_id = get_current_org_id(request)
    if org_id:
        ag = db.get_agent(req.agent_id)
        if ag and getattr(ag, "organization_id", None) and ag.organization_id != org_id:
            raise HTTPException(status_code=404, detail="Agent not found")
        conn = db.get_mcp_connector(req.connector_id)
        if conn and getattr(conn, "organization_id", None) and conn.organization_id != org_id:
            raise HTTPException(status_code=404, detail="Connector not found")
    success = db.revoke_mcp_permission(agent_id=req.agent_id, connector_id=req.connector_id, tool_id=req.tool_id)
    return {"status": "success" if success else "not_found"}

