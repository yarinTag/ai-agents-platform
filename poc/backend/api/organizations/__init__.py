"""
Modular Organizations, Departments, MCP Governance, and Enterprise Auth API Package.
Aggregates focused domain sub-routers into a single unified APIRouter.
"""

from fastapi import APIRouter
from .schemas import (
    OrganizationCreateRequest,
    OrganizationUpdateRequest,
    OrganizationResponse,
    DepartmentCreateRequest,
    DepartmentUpdateRequest,
    DepartmentResponse,
    DepartmentMCPAccessRequest,
    DepartmentMCPAccessResponse,
    OrgRegisterRequest,
    LoginRequest,
    AuthResponse,
    UserResponse,
    DepartmentMemberResponse,
    BulkInviteRequest,
    BulkInviteResponse,
    AcceptInviteRequest,
    format_access_response,
)
from .org_routes import router as org_router
from .dept_routes import router as dept_router
from .governance_routes import router as governance_router
from .auth_routes import router as auth_router

router = APIRouter()
router.include_router(org_router)
router.include_router(dept_router)
router.include_router(governance_router)
router.include_router(auth_router)

__all__ = [
    "router",
    "OrganizationCreateRequest",
    "OrganizationUpdateRequest",
    "OrganizationResponse",
    "DepartmentCreateRequest",
    "DepartmentUpdateRequest",
    "DepartmentResponse",
    "DepartmentMCPAccessRequest",
    "DepartmentMCPAccessResponse",
    "OrgRegisterRequest",
    "LoginRequest",
    "AuthResponse",
    "UserResponse",
    "DepartmentMemberResponse",
    "BulkInviteRequest",
    "BulkInviteResponse",
    "AcceptInviteRequest",
    "format_access_response",
]
