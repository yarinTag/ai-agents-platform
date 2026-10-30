"""Agents: models ownership."""

from typing import List, Optional
from pydantic import BaseModel, Field, field_validator
from ..dependencies import runtime_providers as providers


def _check_runtime_provider(value: Optional[str]) -> Optional[str]:
    """Reject unknown provider IDs at the boundary; None means inherit the default."""
    if value is None or not value.strip():
        return None
    candidate = value.strip()
    if candidate not in providers.ALL_PROVIDER_IDS:
        raise ValueError(
            f"Unknown runtime provider '{candidate}'. "
            f"Expected one of: {', '.join(providers.ALL_PROVIDER_IDS)}."
        )
    return candidate



class AgentBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    system_prompt: str = Field(..., min_length=1)
    skills: List[str] = Field(default_factory=list)
    model: str = Field(default="default")
    effort: str = Field(default="medium")
    max_tokens: int = Field(default=8000, gt=0)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    repo_path: Optional[str] = None
    github_url: Optional[str] = None
    department: Optional[str] = "Engineering"
    avatar: Optional[str] = None

    # Organizational hierarchy fields
    parent_id: Optional[str] = None
    role_type: str = Field(default="WORKER")
    max_concurrent_children: int = Field(default=3, ge=1, le=20)
    delegation_strategy: str = Field(default="hierarchical")
    allowed_child_ids: List[str] = Field(default_factory=list)
    allowed_tools: List[str] = Field(default_factory=list)
    template_id: Optional[str] = None
    allow_sibling_communication: bool = Field(default=True)
    allowed_peer_ids: List[str] = Field(default_factory=list)
    mcp_permissions: List[str] = Field(default_factory=list)
    # None = inherit the platform-default runtime provider
    runtime_provider: Optional[str] = None
    is_workflow_agent: bool = Field(default=False)
    workflow_id: Optional[str] = None
    organization_id: Optional[str] = None
    department_id: Optional[str] = None

    _validate_provider = field_validator('runtime_provider')(_check_runtime_provider)



class AgentCreate(AgentBase):
    pass



class AgentUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    system_prompt: Optional[str] = Field(None, min_length=1)
    skills: Optional[List[str]] = None
    model: Optional[str] = None
    effort: Optional[str] = None
    max_tokens: Optional[int] = Field(None, gt=0)
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    repo_path: Optional[str] = None
    github_url: Optional[str] = None
    department: Optional[str] = None
    avatar: Optional[str] = None

    # Organizational hierarchy fields
    parent_id: Optional[str] = None
    role_type: Optional[str] = None
    max_concurrent_children: Optional[int] = Field(None, ge=1, le=20)
    delegation_strategy: Optional[str] = None
    allowed_child_ids: Optional[List[str]] = None
    allowed_tools: Optional[List[str]] = None
    template_id: Optional[str] = None
    allow_sibling_communication: Optional[bool] = None
    allowed_peer_ids: Optional[List[str]] = None
    mcp_permissions: Optional[List[str]] = None
    runtime_provider: Optional[str] = None
    is_workflow_agent: Optional[bool] = False
    workflow_id: Optional[str] = None
    organization_id: Optional[str] = None
    department_id: Optional[str] = None

    _validate_provider = field_validator('runtime_provider')(_check_runtime_provider)



class AgentResponse(AgentBase):
    id: str
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True

