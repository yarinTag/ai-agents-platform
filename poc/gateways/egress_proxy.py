"""
Default-Deny Outbound Network Egress Proxy & Anti-Exfiltration Gateway.

Enforces:
1. Real-time `ScopedRunToken` validation via `SecretsBroker`.
2. Hard-block of cloud metadata endpoints (`169.254.169.254`, `fd00:ec2::254`, `metadata.google.internal`)
   and loopback/RFC1918 internal networks (`127.0.0.1`, `localhost`, `0.0.0.0`, `10.*`, `192.168.*`, `172.16-31.*`).
3. Strict domain allowlist enforcement from `ScopedRunToken.egress_allowlist`.
4. Outbound payload size ceiling (default `1_048_576` bytes / 1 MiB) to prevent bulk data exfiltration.
5. Append-only audit recording of every allowed and blocked egress attempt.
"""

from __future__ import annotations

import ipaddress
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlparse

try:
    from gateways.secrets_broker import SecretsBroker, ScopedRunToken, secrets_broker
except ImportError:
    from poc.gateways.secrets_broker import SecretsBroker, ScopedRunToken, secrets_broker

DEFAULT_MAX_PAYLOAD_BYTES: int = 1_048_576  # 1 MiB

BLOCKED_METADATA_HOSTS = {
    "169.254.169.254",
    "fd00:ec2::254",
    "[fd00:ec2::254]",
    "metadata.google.internal",
    "metadata.internal",
    "100.100.100.200",
}

BLOCKED_INTERNAL_HOSTNAMES = {
    "localhost",
    "localhost.localdomain",
    "0.0.0.0",
    "127.0.0.1",
    "::1",
    "[::1]",
    "broadcasthost",
    "ip6-localhost",
    "ip6-loopback",
}


class EgressProxy:
    """
    Default-deny outbound network proxy for agent sandboxes.
    All outbound requests are denied unless explicitly permitted by the run token's allowlist
    and free of SSRF/internal IP or payload size violations.
    """

    def __init__(
        self,
        secrets_broker_instance: Optional[SecretsBroker] = None,
        max_payload_bytes: int = DEFAULT_MAX_PAYLOAD_BYTES,
        audit_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> None:
        self.secrets_broker: SecretsBroker = secrets_broker_instance or secrets_broker
        self.max_payload_bytes: int = max_payload_bytes
        self.audit_callback: Optional[Callable[[Dict[str, Any]], None]] = audit_callback
        self.audit_log: List[Dict[str, Any]] = []

    def _record_attempt(
        self,
        allowed: bool,
        reason: str,
        target_url: str,
        hostname: Optional[str],
        payload_size_bytes: int,
        scoped_token: Optional[ScopedRunToken] = None,
    ) -> Dict[str, Any]:
        """Record an allowed or blocked egress attempt in the audit log and optional callback."""
        entry: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "allowed": allowed,
            "decision": "ALLOWED" if allowed else "BLOCKED",
            "reason": reason,
            "target_url": target_url,
            "hostname": hostname,
            "payload_size_bytes": payload_size_bytes,
            "org_id": scoped_token.org_id if scoped_token else None,
            "department_id": scoped_token.department_id if scoped_token else None,
            "run_id": scoped_token.run_id if scoped_token else None,
            "user_id": scoped_token.user_id if scoped_token else None,
        }
        self.audit_log.append(entry)
        if self.audit_callback is not None:
            self.audit_callback(entry)
        return entry

    @staticmethod
    def _is_blocked_ip_or_host(hostname: str) -> Optional[str]:
        """
        Return a block reason if `hostname` resolves to or matches cloud metadata,
        loopback, link-local, unspecified, or RFC1918 private address ranges.
        """
        clean_host = hostname.strip().lower().strip("[]")
        if not clean_host:
            return "Empty or missing hostname"

        if clean_host in BLOCKED_METADATA_HOSTS or clean_host.startswith("169.254."):
            return f"Hard-blocked cloud metadata endpoint: {clean_host}"

        if clean_host in BLOCKED_INTERNAL_HOSTNAMES or clean_host.endswith(".internal") or clean_host.endswith(".local"):
            return f"Hard-blocked loopback or internal hostname: {clean_host}"

        try:
            ip_obj = ipaddress.ip_address(clean_host)
            if str(ip_obj).lower() in ("169.254.169.254", "fd00:ec2::254"):
                return f"Hard-blocked cloud metadata IP: {ip_obj}"
            if (
                ip_obj.is_loopback
                or ip_obj.is_private
                or ip_obj.is_link_local
                or ip_obj.is_unspecified
                or ip_obj.is_reserved
                or ip_obj.is_multicast
            ):
                return f"Hard-blocked internal/private/loopback IP address: {ip_obj}"
        except ValueError:
            # Not a literal IP; check numeric prefix patterns just in case
            pass

        return None

    @staticmethod
    def _matches_allowlist(hostname: str, allowlist: List[str]) -> bool:
        """
        Check whether `hostname` matches an entry in `allowlist`.
        Supports exact hostname match (e.g. `api.github.com`) and wildcard subdomains (`*.slack.com`).
        Never permits universal `*` wildcard in zero-trust egress mode.
        """
        clean_host = hostname.strip().lower().strip("[]")
        if not clean_host or not allowlist:
            return False

        for pattern in allowlist:
            norm = pattern.strip().lower()
            if not norm or norm == "*":
                continue
            if norm == clean_host:
                return True
            if norm.startswith("*."):
                suffix = norm[2:]
                if suffix and (clean_host == suffix or clean_host.endswith(f".{suffix}")):
                    return True
        return False

    def check_egress_request(
        self,
        run_token: str,
        target_url: str,
        payload_size_bytes: int = 0,
    ) -> Dict[str, Any]:
        """
        Validate an outbound network request against the default-deny policy.
        Raises `PermissionError` immediately on any token, SSRF/IP, allowlist, or payload violation.
        """
        scoped: Optional[ScopedRunToken] = None
        try:
            scoped = self.secrets_broker.validate_run_token(run_token)
        except PermissionError as exc:
            self._record_attempt(
                allowed=False,
                reason=str(exc),
                target_url=target_url,
                hostname=None,
                payload_size_bytes=payload_size_bytes,
                scoped_token=None,
            )
            raise

        if not target_url or not isinstance(target_url, str):
            reason = "Fail-closed: Missing or invalid target_url"
            self._record_attempt(False, reason, str(target_url), None, payload_size_bytes, scoped)
            raise PermissionError(reason)

        parsed = urlparse(target_url.strip())
        if parsed.scheme.lower() not in ("https", "http"):
            reason = f"Fail-closed: Disallowed URL scheme '{parsed.scheme or 'none'}'"
            self._record_attempt(False, reason, target_url, parsed.hostname, payload_size_bytes, scoped)
            raise PermissionError(reason)

        hostname = parsed.hostname
        if not hostname:
            reason = f"Fail-closed: Unable to parse hostname from URL '{target_url}'"
            self._record_attempt(False, reason, target_url, None, payload_size_bytes, scoped)
            raise PermissionError(reason)

        # 1. Hard-block cloud metadata & internal/loopback IPs (even if somehow allowlisted)
        ip_block_reason = self._is_blocked_ip_or_host(hostname)
        if ip_block_reason:
            reason = f"Fail-closed: {ip_block_reason}"
            self._record_attempt(False, reason, target_url, hostname, payload_size_bytes, scoped)
            raise PermissionError(reason)

        # 2. Enforce outbound payload size ceiling
        if payload_size_bytes < 0:
            reason = "Fail-closed: Negative payload_size_bytes is invalid"
            self._record_attempt(False, reason, target_url, hostname, payload_size_bytes, scoped)
            raise PermissionError(reason)

        if payload_size_bytes > self.max_payload_bytes:
            reason = (
                f"Fail-closed: Outbound payload ({payload_size_bytes} bytes) exceeds "
                f"exfiltration ceiling ({self.max_payload_bytes} bytes)"
            )
            self._record_attempt(False, reason, target_url, hostname, payload_size_bytes, scoped)
            raise PermissionError(reason)

        # 3. Default-deny domain allowlist check
        if not self._matches_allowlist(hostname, scoped.egress_allowlist):
            reason = (
                f"Fail-closed: Egress domain '{hostname}' is not in run token allowlist "
                f"({scoped.egress_allowlist})"
            )
            self._record_attempt(False, reason, target_url, hostname, payload_size_bytes, scoped)
            raise PermissionError(reason)

        return self._record_attempt(
            allowed=True,
            reason=f"Egress permitted to allowlisted host '{hostname}'",
            target_url=target_url,
            hostname=hostname.strip().lower(),
            payload_size_bytes=payload_size_bytes,
            scoped_token=scoped,
        )


# Default singleton instance shared across runtime gateways
egress_proxy = EgressProxy(secrets_broker_instance=secrets_broker)
