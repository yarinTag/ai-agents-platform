"""
Audit logs and authentication status API endpoints.
Provides visibility into security events, task triggers, and access controls.
"""

from fastapi import APIRouter, Depends, Query, Request
from typing import List, Optional, Dict, Any
from pydantic import BaseModel

from backend.dependencies import get_db_manager
from backend.security.auth import authenticate_request, get_configured_api_key

router = APIRouter()


class AuditLogResponse(BaseModel):
    id: str
    action: str
    actor: str
    entity_type: str
    entity_id: str
    details: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    correlation_id: Optional[str] = None
    timestamp: str


class AuthStatusResponse(BaseModel):
    configured: bool
    mode: str
    active_key_prefix: Optional[str] = None


@router.get("/status", response_model=AuthStatusResponse)
async def get_auth_status():
    """Check platform authentication configuration mode."""
    key = get_configured_api_key()
    return AuthStatusResponse(
        configured=bool(key),
        mode="api_key_enforced" if key else "open_development",
        active_key_prefix=f"{key[:4]}..." if key and len(key) >= 4 else None
    )


@router.get("/logs", response_model=List[AuditLogResponse])
async def list_audit_logs(
    limit: int = Query(100, ge=1, le=500),
    entity_type: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    actor: Optional[str] = Query(None),
    db_manager = Depends(get_db_manager),
    auth = Depends(authenticate_request)
):
    """Retrieve system audit logs for administrative review and security monitoring."""
    logs = db_manager.get_audit_logs(
        limit=limit,
        entity_type=entity_type,
        action=action,
        actor=actor
    )
    return logs
