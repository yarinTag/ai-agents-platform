"""
FastAPI Router for Phase 2 & 3 Runtime Security Gateways (`/api/v1/gateways`).

Endpoints:
- `POST /tokens/issue` — Issue a short-lived cryptographic `ScopedRunToken`
- `POST /mcp/invoke` — Real-time runtime MCP & tool call interception
- `POST /egress/check` — Default-deny outbound network & payload size check
- `POST /llm/authorize` — Real-time LLM model allowlist, HARD_STOP budget, and PII check
- `POST /kill-switch` — Emergency revocation of run/org tokens and active sandbox destruction
- `GET /rls-policies` — Inspect generated PostgreSQL Row-Level Security (RLS) DDL policies
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

try:
    from persistence import DatabaseManager
    from gateways.secrets_broker import secrets_broker
    from gateways.egress_proxy import egress_proxy
    from gateways.tool_gateway import tool_gateway
    from gateways.llm_proxy import llm_proxy
    from persistence_modules.postgres_rls import (
        RLS_MANAGED_TABLES,
        generate_postgres_rls_migrations,
        record_security_audit_event,
    )
except ImportError:
    from poc.persistence import DatabaseManager
    from poc.gateways.secrets_broker import secrets_broker
    from poc.gateways.egress_proxy import egress_proxy
    from poc.gateways.tool_gateway import tool_gateway
    from poc.gateways.llm_proxy import llm_proxy
    from poc.persistence_modules.postgres_rls import (
        RLS_MANAGED_TABLES,
        generate_postgres_rls_migrations,
        record_security_audit_event,
    )

db_manager = DatabaseManager()
router = APIRouter(tags=["Runtime Security Gateways"])


class IssueRunTokenRequest(BaseModel):
    """Request payload for issuing a short-lived `ScopedRunToken`."""

    org_id: str
    department_id: str
    run_id: str
    user_id: Optional[str] = None
    allowed_mcps: List[str] = Field(default_factory=list)
    allowed_tools_by_mcp: Dict[str, List[str]] = Field(default_factory=dict)
    egress_allowlist: List[str] = Field(default_factory=list)
    ttl_seconds: int = 900


class MCPInvokeInterceptRequest(BaseModel):
    """Request payload for intercepting an MCP tool invocation."""

    run_token: str
    connector_id: str
    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    require_human_approval_for_external_write: bool = False


class EgressCheckRequest(BaseModel):
    """Request payload for validating an outbound network egress request."""

    run_token: str
    target_url: str
    payload_size_bytes: int = 0


class LLMAuthorizeRequest(BaseModel):
    """Request payload for authorizing and metering an LLM inference request."""

    run_token: str
    model: str = "default"
    prompt_text: str
    estimated_cost_usd: float = 0.01
    redact_pii: bool = True


class KillSwitchRequest(BaseModel):
    """Request payload for emergency token revocation and sandbox destruction."""

    token: Optional[str] = None
    run_id: Optional[str] = None
    org_id: Optional[str] = None
    reason: str = "Emergency kill-switch triggered"


@router.post("/tokens/issue")
def issue_run_token_endpoint(req: IssueRunTokenRequest) -> Dict[str, Any]:
    """Issue a short-lived cryptographic `ScopedRunToken` for a workflow execution."""
    try:
        scoped = secrets_broker.issue_run_token(
            org_id=req.org_id,
            department_id=req.department_id,
            run_id=req.run_id,
            user_id=req.user_id,
            allowed_mcps=req.allowed_mcps,
            allowed_tools_by_mcp=req.allowed_tools_by_mcp,
            egress_allowlist=req.egress_allowlist,
            ttl_seconds=req.ttl_seconds,
        )
        return scoped.to_dict()
    except (ValueError, PermissionError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/mcp/invoke")
def intercept_mcp_invoke_endpoint(req: MCPInvokeInterceptRequest) -> Dict[str, Any]:
    """Intercept and authorize an MCP tool call in real time."""
    try:
        return tool_gateway.intercept_tool_call(
            db=db_manager,
            run_token=req.run_token,
            connector_id=req.connector_id,
            tool_name=req.tool_name,
            arguments=req.arguments,
            require_human_approval_for_external_write=req.require_human_approval_for_external_write,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post("/egress/check")
def check_egress_endpoint(req: EgressCheckRequest) -> Dict[str, Any]:
    """Validate an outbound network request against the default-deny egress proxy."""
    try:
        return egress_proxy.check_egress_request(
            run_token=req.run_token,
            target_url=req.target_url,
            payload_size_bytes=req.payload_size_bytes,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post("/llm/authorize")
def authorize_llm_endpoint(req: LLMAuthorizeRequest) -> Dict[str, Any]:
    """Authorize and meter an LLM call against model allowlist and department HARD_STOP budget."""
    try:
        return llm_proxy.authorize_and_meter_llm_call(
            db=db_manager,
            run_token=req.run_token,
            model=req.model,
            prompt_text=req.prompt_text,
            estimated_cost_usd=req.estimated_cost_usd,
            redact_pii=req.redact_pii,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post("/kill-switch")
def trigger_kill_switch_endpoint(req: KillSwitchRequest) -> Dict[str, Any]:
    """
    Emergency Kill Switch: immediately revokes run/organization tokens and destroys active sandboxes.
    Fails closed if no target (`token`, `run_id`, or `org_id`) is specified.
    """
    if not req.token and not req.run_id and not req.org_id:
        raise HTTPException(
            status_code=400,
            detail="Fail-closed: At least one of 'token', 'run_id', or 'org_id' must be provided",
        )

    revoked_count = 0
    if req.token:
        if secrets_broker.revoke_run_token(req.token, reason=req.reason):
            revoked_count += 1
    if req.run_id:
        revoked_count += secrets_broker.revoke_all_for_run(req.run_id, reason=req.reason)
    if req.org_id:
        revoked_count += secrets_broker.revoke_all_for_org(req.org_id, reason=req.reason)

    destroyed_sandboxes: List[str] = []
    # Attempt to destroy any active container sandboxes if sandbox_runner is loaded
    try:
        try:
            from runtime import sandbox_runner  # type: ignore[attr-defined]
        except ImportError:
            from poc.runtime import sandbox_runner  # type: ignore[attr-defined]
        manager = getattr(sandbox_runner, "sandbox_manager", None) or getattr(
            sandbox_runner, "default_sandbox_runner", None
        )
        if manager is not None:
            if req.run_id and hasattr(manager, "destroy_sandbox"):
                manager.destroy_sandbox(req.run_id)
                destroyed_sandboxes.append(req.run_id)
            elif req.org_id and hasattr(manager, "destroy_all_for_org"):
                destroyed = manager.destroy_all_for_org(req.org_id)
                if isinstance(destroyed, list):
                    destroyed_sandboxes.extend(destroyed)
    except Exception:
        pass

    audit = record_security_audit_event(
        db=db_manager,
        action="KILL_SWITCH_ACTIVATED",
        actor="security_control_plane",
        entity_type="kill_switch",
        entity_id=req.run_id or req.org_id or "single_token",
        org_id=req.org_id or "global",
        run_id=req.run_id,
        parameters={"run_id": req.run_id, "org_id": req.org_id, "reason": req.reason},
        metadata={"revoked_tokens": revoked_count, "destroyed_sandboxes": destroyed_sandboxes},
        decision="REVOKED",
        reason=req.reason,
    )

    return {
        "status": "KILL_SWITCH_EXECUTED",
        "revoked_tokens": revoked_count,
        "destroyed_sandboxes": destroyed_sandboxes,
        "reason": req.reason,
        "audit_id": audit["id"],
    }


@router.get("/rls-policies")
def get_rls_policies_endpoint() -> Dict[str, Any]:
    """Return generated PostgreSQL Row-Level Security (RLS) DDL statements."""
    statements = generate_postgres_rls_migrations()
    return {
        "tenant_setting_key": "app.org_id",
        "managed_tables": list(RLS_MANAGED_TABLES),
        "statement_count": len(statements),
        "ddl_statements": statements,
    }
