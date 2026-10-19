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
from ...security.tenant_access import authorize_org as _authorize_org, org_of_department

try:
    from gateways.secrets_broker import secrets_broker
    from persistence_modules.llm_keys_repo import DEFAULT_PROVIDER_MODELS, OrgLLMCredential
    from runtime.direct_llm_adapter import DirectHTTPLLMRuntimeAdapter
except ImportError:
    from poc.gateways.secrets_broker import secrets_broker
    from poc.persistence_modules.llm_keys_repo import DEFAULT_PROVIDER_MODELS, OrgLLMCredential
    from poc.runtime.direct_llm_adapter import DirectHTTPLLMRuntimeAdapter

router = APIRouter()
default_adapter = DirectHTTPLLMRuntimeAdapter()


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


class CompletionProbeRequest(BaseModel):
    """Request payload to probe a provider credential (optionally with tools) for one department.

    No caller-supplied `run_token`: the endpoint always mints a short-lived token bound to the
    URL's organization, so a token (or budget/key) of another tenant can never be borrowed.
    """

    provider: str = Field(..., min_length=1)
    model: Optional[str] = None
    department_id: str = Field(..., min_length=1)
    system_prompt: str = "You are a secure enterprise AI assistant."
    user_prompt: str = "Confirm connectivity."
    tools: Optional[List[Dict[str, Any]]] = None
    allowed_mcps: List[str] = Field(default_factory=list, max_length=8)
    max_tool_rounds: int = Field(default=3, ge=0, le=8)
    estimated_cost_usd: float = Field(default=0.01, ge=0, le=5)


def _require_department_in_org(db: DatabaseManager, org_id: str, department_id: Optional[str]) -> None:
    """Reject department ids that do not belong to `org_id` (None means org-wide and is allowed)."""
    if department_id and org_of_department(db, department_id.strip()) != org_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="department_id does not belong to this organization")


def _save_cred(db: DatabaseManager, org_id: str, req: SaveLLMKeyRequest) -> OrgLLMCredential:
    """Persist (or rotate) an encrypted credential for `org_id`."""
    _require_department_in_org(db, org_id, req.department_id)
    return db.save_org_llm_credential(
        organization_id=org_id, provider=req.provider, api_key=req.api_key,
        department_id=req.department_id, key_alias=req.key_alias,
        default_model=req.default_model, base_url=req.base_url,
    )


def _list_creds(db: DatabaseManager, org_id: str, department_id: Optional[str]) -> List[OrgLLMCredential]:
    """List masked credentials for `org_id`."""
    return db.list_org_llm_credentials(organization_id=org_id, department_id=department_id)


def _delete_cred(db: DatabaseManager, credential_id: str, org_id: str) -> bool:
    """Delete a credential scoped strictly to `org_id`."""
    return db.delete_org_llm_credential(credential_id=credential_id, organization_id=org_id)



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
    req: CompletionProbeRequest,
    db: DatabaseManager = Depends(get_db_manager),
) -> Dict[str, Any]:
    """Probe a provider BYOK key (and optional gateway-checked tools) via `DirectHTTPLLMRuntimeAdapter`."""
    _authorize_org(request, org_id, admin=True)
    dept_id = req.department_id.strip()
    _require_department_in_org(db, org_id, dept_id)
    norm_provider = req.provider.strip().lower()
    model = (req.model or "").strip() or DEFAULT_PROVIDER_MODELS.get(norm_provider, "default")

    # Least privilege: no MCP is reachable unless explicitly listed (and still gated by department grants).
    scoped_tok = secrets_broker.issue_run_token(
        org_id=org_id,
        department_id=dept_id,
        run_id=f"run_test_{uuid.uuid4().hex[:8]}",
        allowed_mcps=list(req.allowed_mcps),
        ttl_seconds=120,
    )

    try:
        return default_adapter.execute_with_tools(
            db=db,
            run_token=scoped_tok.token,
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
    finally:
        secrets_broker.revoke_run_token(scoped_tok.token)

