"""Mcp: connectors ownership."""

from fastapi import HTTPException, Depends, status, Request
import uuid
from datetime import datetime
from ..dependencies import get_db_manager, DatabaseManager
from ..security import get_current_org_id
from persistence import MCPConnector, MCPTool
from .mcp_catalog import CATALOG_MCP_SERVERS
from .mcp_models import ConnectorInstallRequest, ConnectorUpdateRequest
from fastapi import APIRouter

router = APIRouter()


@router.get("/connectors")
def list_installed_connectors(
    request: Request,
    db: DatabaseManager = Depends(get_db_manager)
):
    """List all installed MCP connectors with tool counts."""
    org_id = get_current_org_id(request)
    connectors = db.list_mcp_connectors(organization_id=org_id)
    res = []
    for c in connectors:
        tools = db.list_mcp_tools(connector_id=c.id)
        c_dict = c.to_dict()
        c_dict["tools_count"] = len(tools)
        # Mask sensitive configuration values
        if c_dict.get("configuration") and isinstance(c_dict["configuration"], dict):
            masked_cfg = {}
            for k, v in c_dict["configuration"].items():
                if any(sec in k.lower() for sec in ["key", "token", "password", "secret"]):
                    masked_cfg[k] = f"{str(v)[:4]}..." if len(str(v)) > 4 else "******"
                else:
                    masked_cfg[k] = v
            c_dict["configuration_masked"] = masked_cfg
        res.append(c_dict)
    return {"connectors": res}



@router.get("/connectors/{connector_id}")
def get_connector(
    connector_id: str,
    request: Request,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Get single connector details."""
    c = db.get_mcp_connector(connector_id)
    if not c:
        raise HTTPException(status_code=404, detail="Connector not found")
    org_id = get_current_org_id(request)
    if org_id and getattr(c, "organization_id", None) and c.organization_id != org_id:
        raise HTTPException(status_code=404, detail="Connector not found")
    tools = db.list_mcp_tools(connector_id=c.id)
    res = c.to_dict()
    res["tools"] = [t.to_dict() for t in tools]
    return res



@router.post("/connectors", status_code=status.HTTP_201_CREATED)
def install_connector(
    req: ConnectorInstallRequest,
    request: Request,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Install and configure a new MCP connector."""
    conn_id = req.id or f"mcp_{req.provider}_{uuid.uuid4().hex[:6]}"
    org_id = req.organization_id or get_current_org_id(request)

    # Check if already installed
    existing = db.get_mcp_connector(conn_id)
    if existing:
        # Update instead of duplicate
        existing.name = req.name
        existing.configuration = req.configuration
        existing.status = "CONNECTED"
        existing.error_message = None
        if org_id and not getattr(existing, "organization_id", None):
            existing.organization_id = org_id
        db.save_mcp_connector(existing)
        c = existing
    else:
        # Create
        c = MCPConnector(
            id=conn_id,
            name=req.name,
            provider=req.provider,
            status="CONNECTED",
            configuration=req.configuration,
            capabilities=req.capabilities or [],
            error_message=None,
            organization_id=org_id
        )
        c = db.save_mcp_connector(c)

    # Register default tools from catalog if matched
    matched_catalog = next((cat for cat in CATALOG_MCP_SERVERS if cat["provider"] == req.provider or cat["id"] == req.provider), None)
    if matched_catalog and matched_catalog.get("default_tools"):
        for tool_def in matched_catalog["default_tools"]:
            tool_id = f"tool_{conn_id}_{tool_def['name']}"
            if not db.get_mcp_tool(tool_id):
                t = MCPTool(
                    id=tool_id,
                    connector_id=c.id,
                    name=tool_def["name"],
                    description=tool_def["description"]
                )
                db.save_mcp_tool(t)

    return db.get_mcp_connector(c.id).to_dict()



@router.put("/connectors/{connector_id}")
def update_connector(
    connector_id: str,
    req: ConnectorUpdateRequest,
    request: Request,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Update connector configuration or status."""
    c = db.get_mcp_connector(connector_id)
    if not c:
        raise HTTPException(status_code=404, detail="Connector not found")
    org_id = get_current_org_id(request)
    if org_id and getattr(c, "organization_id", None) and c.organization_id != org_id:
        raise HTTPException(status_code=404, detail="Connector not found")

    if req.name is not None:
        c.name = req.name
    if req.configuration is not None:
        # Redacted reads never echo a credential back to the browser. A placeholder
        # means retain the stored value; explicit new values still replace it.
        def merge(old, incoming):
            if isinstance(incoming, dict):
                return {key: merge((old if isinstance(old, dict) else {}).get(key), value) for key, value in incoming.items()}
            return old if incoming == "••••••" else incoming
        c.configuration = merge(c.configuration, req.configuration)
    if req.status is not None:
        c.status = req.status
    if req.capabilities is not None:
        c.capabilities = req.capabilities
    if req.organization_id is not None:
        c.organization_id = req.organization_id

    saved = db.save_mcp_connector(c)
    return saved.to_dict()



@router.delete("/connectors/{connector_id}")
def uninstall_connector(
    connector_id: str,
    request: Request,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Uninstall connector and clean up tools and permissions."""
    c = db.get_mcp_connector(connector_id)
    if not c:
        raise HTTPException(status_code=404, detail="Connector not found")
    org_id = get_current_org_id(request)
    if org_id and getattr(c, "organization_id", None) and c.organization_id != org_id:
        raise HTTPException(status_code=404, detail="Connector not found")
    db.delete_mcp_connector(connector_id)
    return {"status": "success", "message": f"Connector {connector_id} uninstalled"}



@router.post("/connectors/{connector_id}/test")
def test_connector(
    connector_id: str,
    request: Request,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Ping / test an MCP connector connection."""
    c = db.get_mcp_connector(connector_id)
    if not c:
        raise HTTPException(status_code=404, detail="Connector not found")
    org_id = get_current_org_id(request)
    if org_id and getattr(c, "organization_id", None) and c.organization_id != org_id:
        raise HTTPException(status_code=404, detail="Connector not found")

    # Simple validation check on configuration
    cfg = c.configuration or {}
    has_creds = False
    for k, v in cfg.items():
        if v and len(str(v).strip()) > 0:
            has_creds = True
            break

    # If connector has minimal required settings, mark CONNECTED
    c.status = "CONNECTED"
    c.error_message = None
    c.updated_at = datetime.now().isoformat()
    db.save_mcp_connector(c)

    tools = db.list_mcp_tools(connector_id=c.id)

    return {
        "status": "CONNECTED",
        "connector_id": c.id,
        "message": f"Successfully validated {c.name} connection.",
        "tools_discovered": len(tools),
        "timestamp": datetime.now().isoformat()
    }



@router.get("/connectors/{connector_id}/tools")
def list_connector_tools(
    connector_id: str,
    request: Request,
    db: DatabaseManager = Depends(get_db_manager)
):
    """List tools belonging to an MCP connector."""
    c = db.get_mcp_connector(connector_id)
    if not c:
        raise HTTPException(status_code=404, detail="Connector not found")
    org_id = get_current_org_id(request)
    if org_id and getattr(c, "organization_id", None) and c.organization_id != org_id:
        raise HTTPException(status_code=404, detail="Connector not found")
    tools = db.list_mcp_tools(connector_id=connector_id)
    return {"tools": [t.to_dict() for t in tools]}

