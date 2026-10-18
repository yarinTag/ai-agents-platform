"""
Zero-Trust Secrets Broker & Short-Lived Scoped Run Tokens.

Ensures sandboxes and agent runtimes never receive raw upstream credentials
(such as GitHub PATs, Telegram bot tokens, or LLM API keys). Instead, each workflow
execution receives a short-lived cryptographic `ScopedRunToken` (`rtk_<random>`)
bound to `org_id`, `department_id`, `run_id`, `user_id`, MCP/tool scopes, and
an explicit egress domain allowlist.
"""

from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ScopedRunToken:
    """Short-lived cryptographic execution token scoped to a single tenant workflow run."""

    token: str
    org_id: str
    department_id: str
    run_id: str
    user_id: Optional[str] = None
    allowed_mcps: List[str] = field(default_factory=list)
    allowed_tools_by_mcp: Dict[str, List[str]] = field(default_factory=dict)
    egress_allowlist: List[str] = field(default_factory=list)
    issued_at: float = field(default_factory=time.time)
    expires_at: float = 0.0
    revoked: bool = False
    revoked_at: Optional[float] = None
    revoked_reason: Optional[str] = None

    def is_expired(self, now: Optional[float] = None) -> bool:
        """Return True if the token TTL has elapsed."""
        check_time = time.time() if now is None else now
        return check_time >= self.expires_at

    def is_valid(self, now: Optional[float] = None) -> bool:
        """Return True only if the token is neither revoked nor expired."""
        return (not self.revoked) and (not self.is_expired(now=now))

    def to_dict(self) -> Dict[str, Any]:
        """Serialize token metadata (safe for control-plane responses)."""
        return {
            "token": self.token,
            "org_id": self.org_id,
            "department_id": self.department_id,
            "run_id": self.run_id,
            "user_id": self.user_id,
            "allowed_mcps": list(self.allowed_mcps),
            "allowed_tools_by_mcp": {k: list(v) for k, v in self.allowed_tools_by_mcp.items()},
            "egress_allowlist": list(self.egress_allowlist),
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "revoked": self.revoked,
            "revoked_at": self.revoked_at,
            "revoked_reason": self.revoked_reason,
        }


class SecretsBroker:
    """
    Issues, validates, and revokes short-lived `ScopedRunToken` instances,
    and brokers upstream secrets exclusively to trusted out-of-process gateways.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._tokens: Dict[str, ScopedRunToken] = {}
        # Vault key: (org_id, connector_id) -> raw secret (never exposed to sandboxes)
        self._secret_vault: Dict[tuple[str, str], str] = {}

    def issue_run_token(
        self,
        org_id: str,
        department_id: str,
        run_id: str,
        user_id: Optional[str] = None,
        allowed_mcps: Optional[List[str]] = None,
        allowed_tools_by_mcp: Optional[Dict[str, List[str]]] = None,
        egress_allowlist: Optional[List[str]] = None,
        ttl_seconds: int = 900,
    ) -> ScopedRunToken:
        """
        Issue a short-lived cryptographic run token (`rtk_<random>`) for a workflow execution.
        Fails closed if tenant/run identity fields are missing or TTL is non-positive.
        """
        if not org_id or not str(org_id).strip():
            raise ValueError("Fail-closed: org_id is required to issue a ScopedRunToken")
        if not department_id or not str(department_id).strip():
            raise ValueError("Fail-closed: department_id is required to issue a ScopedRunToken")
        if not run_id or not str(run_id).strip():
            raise ValueError("Fail-closed: run_id is required to issue a ScopedRunToken")
        if ttl_seconds <= 0:
            raise ValueError("Fail-closed: ttl_seconds must be positive")

        now = time.time()
        token_str = f"rtk_{secrets.token_urlsafe(32)}"

        clean_mcps = [str(m).strip().lower() for m in (allowed_mcps or []) if str(m).strip()]
        clean_tools_by_mcp: Dict[str, List[str]] = {}
        for mcp_id, tools in (allowed_tools_by_mcp or {}).items():
            key = str(mcp_id).strip().lower()
            if key:
                clean_tools_by_mcp[key] = [str(t).strip() for t in (tools or []) if str(t).strip()]

        clean_egress = [
            str(host).strip().lower()
            for host in (egress_allowlist or [])
            if str(host).strip()
        ]

        scoped_token = ScopedRunToken(
            token=token_str,
            org_id=str(org_id).strip(),
            department_id=str(department_id).strip(),
            run_id=str(run_id).strip(),
            user_id=str(user_id).strip() if user_id else None,
            allowed_mcps=clean_mcps,
            allowed_tools_by_mcp=clean_tools_by_mcp,
            egress_allowlist=clean_egress,
            issued_at=now,
            expires_at=now + float(ttl_seconds),
            revoked=False,
        )

        with self._lock:
            self._tokens[token_str] = scoped_token

        return scoped_token

    def validate_run_token(self, token: str) -> ScopedRunToken:
        """
        Validate a run token in real time.
        Fails closed (`PermissionError`) if missing, malformed, unknown, revoked, or expired.
        """
        if not token or not isinstance(token, str) or not token.startswith("rtk_"):
            raise PermissionError("Fail-closed: Missing or malformed run token")

        with self._lock:
            record = self._tokens.get(token)
            if record is None:
                raise PermissionError("Fail-closed: Unknown run token")
            if record.revoked:
                reason = record.revoked_reason or "Token has been revoked"
                raise PermissionError(f"Fail-closed: Revoked run token ({reason})")
            if record.is_expired():
                raise PermissionError("Fail-closed: Expired run token")
            return record

    def revoke_run_token(self, token: str, reason: str = "Explicit token revocation") -> bool:
        """Immediately revoke a single run token."""
        if not token:
            return False
        with self._lock:
            record = self._tokens.get(token)
            if not record:
                return False
            record.revoked = True
            record.revoked_at = time.time()
            record.revoked_reason = reason
            return True

    def revoke_all_for_run(self, run_id: str, reason: str = "Kill-switch: run revoked") -> int:
        """Revoke all tokens associated with a specific `run_id`."""
        if not run_id:
            return 0
        count = 0
        now = time.time()
        with self._lock:
            for record in self._tokens.values():
                if record.run_id == run_id and not record.revoked:
                    record.revoked = True
                    record.revoked_at = now
                    record.revoked_reason = reason
                    count += 1
        return count

    def revoke_all_for_org(self, org_id: str, reason: str = "Kill-switch: organization revoked") -> int:
        """Revoke all tokens associated with an entire `org_id` (Organization Kill Switch)."""
        if not org_id:
            return 0
        count = 0
        now = time.time()
        with self._lock:
            for record in self._tokens.values():
                if record.org_id == org_id and not record.revoked:
                    record.revoked = True
                    record.revoked_at = now
                    record.revoked_reason = reason
                    count += 1
        return count

    def register_connector_secret(self, org_id: str, connector_id: str, secret_value: str) -> None:
        """Store an upstream connector credential in the broker vault (never exposed to sandboxes)."""
        if not org_id or not connector_id or not secret_value:
            raise ValueError("org_id, connector_id, and secret_value are required")
        with self._lock:
            self._secret_vault[(org_id.strip(), connector_id.strip().lower())] = secret_value

    def resolve_secret_for_gateway(self, run_token: str, connector_id: str) -> Optional[str]:
        """
        Resolve an upstream credential strictly for an out-of-process gateway
        after validating the `run_token` and connector scope.
        """
        scoped = self.validate_run_token(run_token)
        norm_conn = connector_id.strip().lower()
        if scoped.allowed_mcps and "*" not in scoped.allowed_mcps and norm_conn not in scoped.allowed_mcps:
            raise PermissionError(
                f"Fail-closed: Token for run '{scoped.run_id}' is not scoped for connector '{connector_id}'"
            )
        with self._lock:
            return self._secret_vault.get((scoped.org_id, norm_conn))

    def list_active_tokens(self, org_id: Optional[str] = None, run_id: Optional[str] = None) -> List[ScopedRunToken]:
        """List currently valid (non-revoked, non-expired) tokens for monitoring."""
        now = time.time()
        with self._lock:
            results = []
            for tok in self._tokens.values():
                if not tok.is_valid(now=now):
                    continue
                if org_id and tok.org_id != org_id:
                    continue
                if run_id and tok.run_id != run_id:
                    continue
                results.append(tok)
            return results


# Default singleton instance shared across runtime gateways
secrets_broker = SecretsBroker()
