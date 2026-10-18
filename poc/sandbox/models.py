"""Data models and security exceptions for Phase 1 Sandbox & Execution Isolation."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Tuple


class TrustLevel(str, Enum):
    """Execution trust tiers for isolated agent workflow steps."""

    UNTRUSTED = "UNTRUSTED"
    RESTRICTED = "RESTRICTED"
    PRIVILEGED = "PRIVILEGED"


class SandboxSecurityError(Exception):
    """Base exception for all sandbox security and isolation violations."""


class SandboxEscapeAttemptError(SandboxSecurityError):
    """Raised when a step attempts path traversal, privilege escalation, or unauthorized access."""


class SandboxTimeoutError(SandboxSecurityError):
    """Raised when a sandbox exceeds its configured execution timeout or TTL."""


class TrustBoundaryViolationError(SandboxSecurityError):
    """Raised when the Rule of Three / trust-boundary splitting policy is violated."""


@dataclass(frozen=True)
class SandboxSpec:
    """Immutable specification for an ephemeral execution sandbox."""

    org_id: str
    department_id: str
    run_id: str
    image: str = "agy-sandbox-base:sha256-verified"
    cpu: int = 2
    mem_mb: int = 2048
    disk_mb: int = 2048
    ttl_seconds: int = 900
    egress_allowlist: Tuple[str, ...] = ()
    trust_level: TrustLevel = TrustLevel.RESTRICTED
    env: Dict[str, str] = field(default_factory=dict)
    read_only_root: bool = True
    non_root_user: str = "sandbox_runner"

    def __post_init__(self) -> None:
        """Validate fail-closed security invariants on sandbox specification."""
        if not self.org_id or not self.org_id.strip():
            raise SandboxSecurityError("SandboxSpec requires a non-empty org_id.")
        if not self.department_id or not self.department_id.strip():
            raise SandboxSecurityError("SandboxSpec requires a non-empty department_id.")
        if not self.run_id or not self.run_id.strip():
            raise SandboxSecurityError("SandboxSpec requires a non-empty run_id.")
        if self.cpu <= 0 or self.mem_mb <= 0 or self.disk_mb <= 0:
            raise SandboxSecurityError("Resource limits (cpu, mem_mb, disk_mb) must be positive.")
        if self.ttl_seconds <= 0:
            raise SandboxSecurityError("ttl_seconds must be strictly positive.")
        if not self.non_root_user or self.non_root_user.strip().lower() == "root":
            raise SandboxSecurityError("Sandbox must run as a non-root user.")
        if isinstance(self.egress_allowlist, list):
            object.__setattr__(self, "egress_allowlist", tuple(self.egress_allowlist))
        if isinstance(self.trust_level, str) and not isinstance(self.trust_level, TrustLevel):
            object.__setattr__(self, "trust_level", TrustLevel(self.trust_level))


@dataclass
class ExecResult:
    """Result of executing a command inside an isolated sandbox."""

    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool
    duration_ms: float = 0.0
    sandbox_cost_usd: float = 0.0
