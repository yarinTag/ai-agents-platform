"""Compatibility exports and router composition for organizations."""

from fastapi import APIRouter
# Bootstrap the single legacy import bridge before domain compatibility exports.
from ..dependencies import get_db_manager
from .organizations_models import (OrganizationCreateRequest, OrganizationUpdateRequest, OrganizationResponse, DepartmentCreateRequest, DepartmentUpdateRequest, DepartmentResponse, DepartmentMCPAccessRequest, DepartmentMCPAccessResponse, OrgRegisterRequest, LoginRequest, AuthResponse, UserResponse, DepartmentMemberResponse, BulkInviteRequest, BulkInviteResponse, AcceptInviteRequest)
from .organizations_governance import (_format_access_response, grant_department_mcp_access, list_department_mcp_access, get_department_mcp_access, revoke_department_mcp_access, check_department_mcp_permission)
from .organizations_crud import (create_organization, list_organizations, get_organization, update_organization, create_department, list_departments, get_department, update_department, check_department_budget)
from .organizations_auth import (register_organization, login_user, get_current_user_profile)
from .organizations_members import (bulk_invite_department_members, list_department_members, remove_department_member, accept_department_invitation, list_organization_users)

router = APIRouter()
from .organizations_governance import router as governance_router
router.include_router(governance_router)
from .organizations_crud import router as crud_router
router.include_router(crud_router)
from .organizations_auth import router as auth_router
router.include_router(auth_router)
from .organizations_members import router as members_router
router.include_router(members_router)
