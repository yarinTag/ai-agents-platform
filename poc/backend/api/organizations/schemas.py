"""
Pydantic Request / Response Schemas for Organizations, Departments,
MCP Governance, Enterprise Authentication, and Invitations.
"""

from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field
from persistence import DepartmentMCPAccess
from shared.validators import parse_allowed_tools


class OrganizationCreateRequest(BaseModel):
    id: Optional[str] = None
    name: str = Field(..., min_length=1)
    slug: str = Field(..., min_length=1)
    domain: Optional[str] = None
    settings_json: Optional[str] = "{}"


class OrganizationUpdateRequest(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    domain: Optional[str] = None
    settings_json: Optional[str] = None


class OrganizationResponse(BaseModel):
    id: str
    name: str
    slug: str
    domain: Optional[str] = None
    settings_json: str = "{}"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class DepartmentCreateRequest(BaseModel):
    id: Optional[str] = None
    name: str = Field(..., min_length=1)
    description: Optional[str] = None
    monthly_budget_usd: float = 100.0
    budget_action: str = "HARD_STOP"
    alert_threshold_pct: float = 80.0
    organization_id: Optional[str] = None


class DepartmentUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    monthly_budget_usd: Optional[float] = None
    budget_action: Optional[str] = None
    alert_threshold_pct: Optional[float] = None
    organization_id: Optional[str] = None


class DepartmentResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    monthly_budget_usd: float
    current_spend_usd: float
    budget_action: str
    alert_threshold_pct: float
    organization_id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class DepartmentMCPAccessRequest(BaseModel):
    connector_id: str
    allowed_tools: Union[str, List[str]] = "*"
    organization_id: Optional[str] = None
    granted_by_user_id: Optional[str] = None


class DepartmentMCPAccessResponse(BaseModel):
    id: str
    department_id: str
    connector_id: str
    allowed_tools: str
    parsed_allowed_tools: List[str]
    organization_id: Optional[str] = None
    is_active: bool
    granted_by_user_id: Optional[str] = None
    granted_at: Optional[str] = None


class OrgRegisterRequest(BaseModel):
    name: str = Field(..., min_length=1)
    slug: str = Field(..., min_length=1)
    domain: Optional[str] = None
    admin_email: str = Field(..., min_length=3)
    admin_name: str = Field(..., min_length=1)
    admin_password: str = Field(..., min_length=6)


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=3)
    password: Optional[str] = None
    sso_token: Optional[str] = None


class AuthResponse(BaseModel):
    token: str
    user: Dict[str, Any]
    organization: Dict[str, Any]
    departments: List[Dict[str, Any]]


class UserResponse(BaseModel):
    id: str
    organization_id: str
    email: str
    full_name: str
    role: str
    status: str
    created_at: Optional[str] = None
    last_login_at: Optional[str] = None


class DepartmentMemberResponse(BaseModel):
    id: str
    department_id: str
    user_id: str
    email: str
    full_name: str
    role: str
    joined_at: Optional[str] = None
    status: Optional[str] = "ACTIVE"


class BulkInviteRequest(BaseModel):
    emails: List[str] = Field(..., min_length=1)
    role: str = "OPERATOR"
    expires_in_days: int = 7


class BulkInviteResponse(BaseModel):
    department_id: str
    invited_count: int
    invitations: List[Dict[str, Any]]


class AcceptInviteRequest(BaseModel):
    invite_token: str
    full_name: Optional[str] = None
    password: Optional[str] = None


def format_access_response(access: DepartmentMCPAccess) -> DepartmentMCPAccessResponse:
    """Format a DepartmentMCPAccess record using shared tool parsing logic."""
    _, parsed = parse_allowed_tools(access.allowed_tools or "*")
    return DepartmentMCPAccessResponse(
        id=access.id,
        department_id=access.department_id,
        connector_id=access.connector_id,
        allowed_tools=access.allowed_tools,
        parsed_allowed_tools=parsed,
        organization_id=access.organization_id,
        is_active=access.is_active,
        granted_by_user_id=access.granted_by_user_id,
        granted_at=access.granted_at,
    )
