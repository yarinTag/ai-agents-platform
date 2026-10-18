"""
Multi-Provider BYOK LLM Keys Vault & Test Completion API Routes.

Provides tenant-isolated endpoints for saving/rotating encrypted API keys
(Anthropic, OpenAI, NVIDIA NIM), listing masked key metadata, deleting keys,
and testing completions with native tool calling through `DirectHTTPLLMRuntimeAdapter`.

Authorization: JWT callers may only access their own organization and only ORG_ADMIN
may write; platform-API-key callers are treated as operators.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from ...dependencies import DatabaseManager, get_db_manager

try:
    from gateways.secrets_broker import secrets_broker
    from persistence_modules.llm_keys_repo import (
        DEFAULT_PROVIDER_MODELS,
        LLMKeysRepositoryMixin,
        OrgLLMCredential,
    )
    from runtime.direct_llm_adapter import DirectHTTPLLMRuntimeAdapter
except ImportError:
    from poc.gateways.secrets_broker import secrets_broker
    from poc.persistence_modules.llm_keys_repo import (
        DEFAULT_PROVIDER_MODELS,
        LLMKeysRepositoryMixin,
        OrgLLMCredential,
    )
    from poc.runtime.direct_llm_adapter import DirectHTTPLLMRuntimeAdapter

router = APIRouter()
default_adapter = DirectHTTPLLMRuntimeAdapter()


def _authorize_org(request: Request, org_id: str, admin: bool = False) -> None:
    """JWT callers may only access their own org; writes require ORG_ADMIN. API-key callers are operators."""
    user = getattr(request.state, "user", None)
    if user is None:
        return
    if user.get("org_id") != org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: not a member of this organization")
    if admin and user.get("role") != "ORG_ADMIN":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: ORG_ADMIN role required")


class SaveLLMKeyRequest(BaseModel):
    """Request payload for saving or rotating an organization/department BYOK LLM key."""

    provider: str = Field(..., min_length=1, description="LLM provider: anthropic, openai, or nvidia")
    api_key: str = Field(..., min_length=1, description="Raw provider API key (encrypted at rest)")
    department_id: Optional[str] = None
    key_alias: Optional[str] = None
    default_model: Optional[str] = None
    base_url: Optional[str] = None


class LLMCredentialResponse(BaseModel):
    """Masked metadata response for a stored BYOK LLM credential (never includes raw key)."""

    id: str
    organization_id: str
    department_id: Optional[str] = None
    provider: str
    key_alias: str
    masked_key: str
    default_model: str
    base_url: Optional[str] = None
    is_active: bool
    created_at: str
    updated_at: str


class TestLLMCompletionRequest(BaseModel):
    """Request payload to test a provider credential and optional tool call."""

    provider: str = Field(..., min_length=1)
    model: Optional[str] = None
    department_id: Optional[str] = None
    system_prompt: str = "You are a secure enterprise AI assistant."
    user_prompt: str = "Confirm connectivity."
    tools: Optional[List[Dict[str, Any]]] = None
    run_token: Optional[str] = None
    max_tool_rounds: int = Field(default=3, ge=0, le=8)
    estimated_cost_usd: float = Field(default=0.01, ge=0, le=5)


def _save_cred(db: DatabaseManager, org_id: str, req: SaveLLMKeyRequest) -> OrgLLMCredential:
    """Invoke `save_org_llm_credential` on `db` or via `LLMKeysRepositoryMixin`."""
    fn = getattr(db, "save_org_llm_credential", None) or (
        lambda **kw: LLMKeysRepositoryMixin.save_org_llm_credential(db, **kw)
    )
    return fn(
        organization_id=org_id, provider=req.provider, api_key=req.api_key,
        department_id=req.department_id, key_alias=req.key_alias,
        default_model=req.default_model, base_url=req.base_url,
    )


def _list_creds(db: DatabaseManager, org_id: str, department_id: Optional[str]) -> List[OrgLLMCredential]:
    """Invoke `list_org_llm_credentials` on `db` or via `LLMKeysRepositoryMixin`."""
    fn = getattr(db, "list_org_llm_credentials", None) or (
        lambda **kw: LLMKeysRepositoryMixin.list_org_llm_credentials(db, **kw)
    )
    return fn(organization_id=org_id, department_id=department_id)


def _delete_cred(db: DatabaseManager, credential_id: str, org_id: str) -> bool:
    """Invoke `delete_org_llm_credential` on `db` or via `LLMKeysRepositoryMixin`."""
    fn = getattr(db, "delete_org_llm_credential", None) or (
        lambda **kw: LLMKeysRepositoryMixin.delete_org_llm_credential(db, **kw)
    )
    return fn(credential_id=credential_id, organization_id=org_id)


@router.post(
    "/organizations/{org_id}/llm-keys",
    response_model=LLMCredentialResponse,
    status_code=status.HTTP_201_CREATED,
)
def save_organization_llm_key(
    org_id: str,
    request: Request,
    req: SaveLLMKeyRequest,
    db: DatabaseManager = Depends(get_db_manager),
) -> LLMCredentialResponse:
    """Save or rotate an envelope-encrypted BYOK API key for `anthropic`, `openai`, or `nvidia`."""
    _authorize_org(request, org_id, admin=True)
    try:
        cred = _save_cred(db, org_id, req)
        return LLMCredentialResponse(**cred.to_dict())
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get(
    "/organizations/{org_id}/llm-keys",
    response_model=List[LLMCredentialResponse],
)
def list_organization_llm_keys(
    org_id: str,
    request: Request,
    department_id: Optional[str] = Query(None, description="Optional department ID filter"),
    db: DatabaseManager = Depends(get_db_manager),
) -> List[LLMCredentialResponse]:
    """List masked BYOK LLM credentials for an organization (and optional department)."""
    _authorize_org(request, org_id)
    creds = _list_creds(db, org_id, department_id)
    return [LLMCredentialResponse(**c.to_dict()) for c in creds]


@router.delete("/organizations/{org_id}/llm-keys/{credential_id}")
def delete_organization_llm_key(
    org_id: str,
    request: Request,
    credential_id: str,
    db: DatabaseManager = Depends(get_db_manager),
) -> Dict[str, Any]:
    """Delete a stored BYOK LLM credential scoped to `org_id`."""
    _authorize_org(request, org_id, admin=True)
    deleted = _delete_cred(db, credential_id=credential_id, org_id=org_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"LLM credential '{credential_id}' not found for organization '{org_id}'",
        )
    return {"status": "SUCCESS", "deleted": True, "credential_id": credential_id, "organization_id": org_id}


@router.post("/organizations/{org_id}/llm-keys/test-completion")
def test_organization_llm_completion(
    org_id: str,
    request: Request,
    req: TestLLMCompletionRequest,
    db: DatabaseManager = Depends(get_db_manager),
) -> Dict[str, Any]:
    """Test a provider BYOK key and optional tool execution via `DirectHTTPLLMRuntimeAdapter`."""
    _authorize_org(request, org_id, admin=True)
    norm_provider = req.provider.strip().lower()
    model = (req.model or "").strip() or DEFAULT_PROVIDER_MODELS.get(norm_provider, "default")
    dept_id = (req.department_id or "").strip() or "dept_default"

    token_str = req.run_token
    if not token_str:
        scoped_tok = secrets_broker.issue_run_token(
            org_id=org_id,
            department_id=dept_id,
            run_id=f"run_test_{uuid.uuid4().hex[:8]}",
            allowed_mcps=["*"],
            ttl_seconds=120,
        )
        token_str = scoped_tok.token

    try:
        return default_adapter.execute_with_tools(
            db=db,
            run_token=token_str,
            provider=norm_provider,
            model=model,
            system_prompt=req.system_prompt,
            user_prompt=req.user_prompt,
            tools=req.tools,
            max_tool_rounds=req.max_tool_rounds,
            estimated_cost_usd=req.estimated_cost_usd,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
