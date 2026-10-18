"""
Real-Time Runtime MCP & Tool Interception Gateway.

Enforces:
1. Cryptographic `ScopedRunToken` validation via `SecretsBroker`.
2. Strict identity binding: `org_id`, `department_id`, `run_id`, and `user_id` are resolved
   exclusively from the validated token — model-supplied identity fields in `arguments`
   are never trusted and are stripped/flagged.
3. Real-time database permission check via `db.check_department_mcp_permission(department_id, connector_id, tool_name)`
   combined with token-level MCP/tool scope enforcement.
4. Destructive tool blocking (`delete_repo`, etc.), target validation, and Human-in-the-Loop (HITL)
   gating for external write operations (`create_pull_request`, `send_message`, `merge_pull_request`, etc.).
5. Append-only security audit logging with SHA-256 `params_hash` (never logging raw secrets).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

try:
    from gateways.secrets_broker import SecretsBroker, ScopedRunToken, secrets_broker
    from persistence_modules.postgres_rls import compute_params_hash, record_security_audit_event
except ImportError:
    from poc.gateways.secrets_broker import SecretsBroker, ScopedRunToken, secrets_broker
    from poc.persistence_modules.postgres_rls import compute_params_hash, record_security_audit_event

UNTRUSTED_IDENTITY_ARG_KEYS: Set[str] = {
    "org_id", "organization_id", "department_id", "run_id", "user_id", "run_token",
}

HARD_BLOCKED_DESTRUCTIVE_TOOLS: Set[str] = {
    "delete_repo", "delete_repository", "delete_organization", "drop_database", "destroy_infrastructure",
}

EXTERNAL_WRITE_TOOLS: Set[str] = {
    "create_pull_request", "merge_pull_request", "push_files", "create_or_update_file",
    "delete_file", "delete_branch", "create_issue", "update_issue", "send_message",
    "post_message", "send_email", "create_release", "trigger_webhook",
}


class RuntimeToolGateway:
    """
    Out-of-process / control-plane interceptor for every MCP and tool invocation.
    Fails closed on any token, department permission, destructive tool, or HITL policy violation.
    """

    def __init__(
        self,
        secrets_broker_instance: Optional[SecretsBroker] = None,
        allowed_write_targets: Optional[Dict[str, List[str]]] = None,
    ) -> None:
        self.secrets_broker: SecretsBroker = secrets_broker_instance or secrets_broker
        # Optional map of connector_id -> allowed target identifiers (e.g. repo names or chat IDs)
        self.allowed_write_targets: Dict[str, List[str]] = allowed_write_targets or {}
        self.audit_trail: List[Dict[str, Any]] = []

    def _audit(
        self,
        db: Any,
        scoped: Optional[ScopedRunToken],
        connector_id: str,
        tool_name: str,
        arguments: Optional[Dict[str, Any]],
        decision: str,
        reason: str,
        spoofed_fields: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Record an append-only audit entry with SHA-256 `params_hash` (never raw secrets)."""
        org_id = scoped.org_id if scoped else "unknown_org"
        department_id = scoped.department_id if scoped else None
        run_id = scoped.run_id if scoped else None
        actor = f"run:{run_id}" if run_id else "unauthenticated_sandbox"

        metadata: Dict[str, Any] = {
            "connector_id": connector_id,
            "tool_name": tool_name,
            "is_external_write": tool_name.lower() in EXTERNAL_WRITE_TOOLS,
        }
        if spoofed_fields:
            metadata["spoofed_identity_fields_stripped"] = spoofed_fields

        entry = record_security_audit_event(
            db=db,
            action=f"MCP_TOOL_{decision}",
            actor=actor,
            entity_type="mcp_tool",
            entity_id=f"{connector_id}.{tool_name}",
            org_id=org_id,
            department_id=department_id,
            run_id=run_id,
            parameters=arguments or {},
            metadata=metadata,
            decision=decision,
            reason=reason,
        )
        self.audit_trail.append(entry)
        return entry

    def intercept_tool_call(
        self,
        db: Any,
        run_token: str,
        connector_id: str,
        tool_name: str,
        arguments: Optional[Dict[str, Any]] = None,
        require_human_approval_for_external_write: bool = False,
    ) -> Dict[str, Any]:
        """
        Intercept and authorize an MCP tool call in real time.
        Raises `PermissionError` immediately if any check fails.
        """
        raw_args: Dict[str, Any] = dict(arguments or {})
        norm_connector = (connector_id or "").strip().lower()
        norm_tool = (tool_name or "").strip()

        # 1. Validate run_token and extract authoritative identity context
        try:
            scoped = self.secrets_broker.validate_run_token(run_token)
        except PermissionError as exc:
            self._audit(db, None, norm_connector, norm_tool, raw_args, "DENIED", str(exc))
            raise

        if not norm_connector or not norm_tool:
            reason = "Fail-closed: connector_id and tool_name are required"
            self._audit(db, scoped, norm_connector, norm_tool, raw_args, "DENIED", reason)
            raise PermissionError(reason)

        # 2. Strip any model-supplied identity fields so downstream tools only use token-bound context
        spoofed_fields: List[str] = []
        sanitized_args: Dict[str, Any] = {}
        for k, v in raw_args.items():
            if k.lower() in UNTRUSTED_IDENTITY_ARG_KEYS:
                spoofed_fields.append(k)
            else:
                sanitized_args[k] = v

        # 3. Hard-block destructive tools (e.g. delete_repo)
        if norm_tool.lower() in HARD_BLOCKED_DESTRUCTIVE_TOOLS:
            reason = f"Fail-closed: Destructive tool '{norm_tool}' is permanently prohibited by runtime policy"
            self._audit(db, scoped, norm_connector, norm_tool, raw_args, "DENIED", reason, spoofed_fields)
            raise PermissionError(reason)

        # 4. Enforce token-scoped MCP and tool allowlists
        if scoped.allowed_mcps and "*" not in scoped.allowed_mcps:
            if norm_connector not in scoped.allowed_mcps:
                reason = (
                    f"Fail-closed: Run token is not scoped for MCP connector '{norm_connector}' "
                    f"(allowed: {scoped.allowed_mcps})"
                )
                self._audit(db, scoped, norm_connector, norm_tool, raw_args, "DENIED", reason, spoofed_fields)
                raise PermissionError(reason)

        if norm_connector in scoped.allowed_tools_by_mcp:
            token_tools = scoped.allowed_tools_by_mcp[norm_connector]
            if "*" not in token_tools and norm_tool not in token_tools:
                reason = (
                    f"Fail-closed: Run token does not permit tool '{norm_tool}' on connector '{norm_connector}'"
                )
                self._audit(db, scoped, norm_connector, norm_tool, raw_args, "DENIED", reason, spoofed_fields)
                raise PermissionError(reason)

        # 5. Real-time DB governance check for department MCP & tool permission
        if db is None or not hasattr(db, "check_department_mcp_permission"):
            reason = "Fail-closed: Database governance verifier is unavailable"
            self._audit(db, scoped, norm_connector, norm_tool, raw_args, "DENIED", reason, spoofed_fields)
            raise PermissionError(reason)

        perm = db.check_department_mcp_permission(scoped.department_id, norm_connector, norm_tool)
        if not perm.get("allowed", False):
            reason = f"Fail-closed: {perm.get('reason', 'Department MCP permission denied')}"
            self._audit(db, scoped, norm_connector, norm_tool, raw_args, "DENIED", reason, spoofed_fields)
            raise PermissionError(reason)

        # 6. Validate external write operations (targets + Human-in-the-Loop approval gate)
        is_write = norm_tool.lower() in EXTERNAL_WRITE_TOOLS
        if is_write:
            allowed_targets = self.allowed_write_targets.get(norm_connector)
            target_val = (
                sanitized_args.get("repo")
                or sanitized_args.get("repository")
                or sanitized_args.get("chat_id")
                or sanitized_args.get("channel")
            )
            if allowed_targets and target_val and str(target_val) not in allowed_targets:
                reason = (
                    f"Fail-closed: Write target '{target_val}' is not in allowed targets "
                    f"for connector '{norm_connector}'"
                )
                self._audit(db, scoped, norm_connector, norm_tool, raw_args, "DENIED", reason, spoofed_fields)
                raise PermissionError(reason)

            human_approved = bool(sanitized_args.pop("_human_approved", False))
            if require_human_approval_for_external_write and not human_approved:
                reason = (
                    f"Fail-closed: Human-in-the-loop approval required before executing "
                    f"external write tool '{norm_connector}.{norm_tool}'"
                )
                self._audit(
                    db, scoped, norm_connector, norm_tool, raw_args, "APPROVAL_REQUIRED", reason, spoofed_fields
                )
                raise PermissionError(reason)

        audit_entry = self._audit(
            db,
            scoped,
            norm_connector,
            norm_tool,
            raw_args,
            "ALLOWED",
            f"Authorized '{norm_connector}.{norm_tool}' for department '{scoped.department_id}'",
            spoofed_fields,
        )

        return {
            "allowed": True,
            "decision": "ALLOWED",
            "org_id": scoped.org_id,
            "department_id": scoped.department_id,
            "run_id": scoped.run_id,
            "user_id": scoped.user_id,
            "connector_id": norm_connector,
            "tool_name": norm_tool,
            "sanitized_arguments": sanitized_args,
            "spoofed_identity_fields_stripped": spoofed_fields,
            "params_hash": compute_params_hash(raw_args),
            "audit_id": audit_entry["id"],
        }


# Default singleton instance shared across runtime gateways
tool_gateway = RuntimeToolGateway(secrets_broker_instance=secrets_broker)
