"""Organizations: governance ownership."""

from fastapi import HTTPException, Depends, status, Query
from typing import List, Optional
import json
from ..dependencies import get_db_manager, DatabaseManager
from persistence import DepartmentMCPAccess
from .organizations_models import DepartmentMCPAccessRequest, DepartmentMCPAccessResponse
from fastapi import APIRouter

router = APIRouter()


def _format_access_response(access: DepartmentMCPAccess) -> DepartmentMCPAccessResponse:
    raw = access.allowed_tools or "*"
    parsed: List[str] = []
    if raw == "*":
        parsed = ["*"]
    elif raw.startswith("["):
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = [raw]
    else:
        parsed = [t.strip() for t in raw.split(",") if t.strip()]

    return DepartmentMCPAccessResponse(
        id=access.id,
        department_id=access.department_id,
        connector_id=access.connector_id,
        allowed_tools=access.allowed_tools,
        parsed_allowed_tools=parsed,
        organization_id=access.organization_id,
        is_active=access.is_active,
        granted_by_user_id=access.granted_by_user_id,
        granted_at=access.granted_at
    )



@router.post("/departments/{dept_id}/mcp-access", response_model=DepartmentMCPAccessResponse, status_code=status.HTTP_201_CREATED)
def grant_department_mcp_access(
    dept_id: str,
    req: DepartmentMCPAccessRequest,
    db: DatabaseManager = Depends(get_db_manager)
):
    """
    Grant or update MCP connector access for a department with tool-level filtering.
    allowed_tools can be '*' (all tools) or a specific list e.g. ['git_diff', 'list_issues'].
    """
    dept = db.get_department(dept_id)
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")

    access = db.grant_department_mcp_access(
        department_id=dept_id,
        connector_id=req.connector_id,
        allowed_tools=req.allowed_tools,
        organization_id=req.organization_id or dept.organization_id,
        granted_by_user_id=req.granted_by_user_id
    )
    return _format_access_response(access)



@router.get("/departments/{dept_id}/mcp-access", response_model=List[DepartmentMCPAccessResponse])
def list_department_mcp_access(
    dept_id: str,
    db: DatabaseManager = Depends(get_db_manager)
):
    """List all active MCP grants and tool permissions for a department."""
    dept = db.get_department(dept_id)
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")

    grants = db.list_department_mcp_access(dept_id)
    return [_format_access_response(g) for g in grants]



@router.get("/departments/{dept_id}/mcp-access/{connector_id}", response_model=DepartmentMCPAccessResponse)
def get_department_mcp_access(
    dept_id: str,
    connector_id: str,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Get active MCP access record for department and connector."""
    access = db.get_department_mcp_access(dept_id, connector_id)
    if not access:
        raise HTTPException(status_code=404, detail=f"No active access grant for connector '{connector_id}' on department '{dept_id}'")
    return _format_access_response(access)



@router.delete("/departments/{dept_id}/mcp-access/{connector_id}")
def revoke_department_mcp_access(
    dept_id: str,
    connector_id: str,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Revoke a department's access to an MCP connector."""
    revoked = db.revoke_department_mcp_access(dept_id, connector_id)
    if not revoked:
        raise HTTPException(status_code=404, detail=f"No active grant found to revoke for connector '{connector_id}'")
    return {"status": "SUCCESS", "message": f"Revoked access to '{connector_id}' for department '{dept_id}'"}



@router.get("/departments/{dept_id}/mcp-access/{connector_id}/check")
def check_department_mcp_permission(
    dept_id: str,
    connector_id: str,
    tool_name: Optional[str] = Query(None, description="Optional tool name to verify permission"),
    db: DatabaseManager = Depends(get_db_manager)
):
    """
    Check if a department is permitted to access an MCP connector and an optional specific tool.
    Returns: { "allowed": bool, "reason": str, "allowed_tools": List[str] }
    """
    return db.check_department_mcp_permission(
        department_id=dept_id,
        connector_id=connector_id,
        tool_name=tool_name
    )

