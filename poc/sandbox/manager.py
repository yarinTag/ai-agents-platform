"""Sandbox lifecycle manager, Rule of Three enforcement, and TTL watchdog."""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

from poc.sandbox.models import (
    ExecResult, SandboxSpec, TrustBoundaryViolationError, TrustLevel,
)
from poc.sandbox.protocol import HardenedLocalSandbox, Sandbox

_SANDBOX_STEP_TOKENS: Tuple[str, ...] = (
    "cli", "subprocess", "bash", "shell", "sh", "write", "edit", "write_file",
    "edit_file", "web_fetch", "webfetch", "fetch", "browser", "scrape",
    "code_exec", "exec", "python", "sandbox", "untrusted",
)
_SANDBOX_RUNTIME_TOKENS: Tuple[str, ...] = (
    "cli", "subprocess", "local_cli", "bash", "shell", "docker", "e2b", "sandbox", "microvm",
)
_CUSTOM_MCP_TOKENS: Tuple[str, ...] = (
    "npx", "python", "python3", "uvx", "node", "bash", "sh", "stdio", "custom", ".py", ".js",
)
_SENSITIVE_ENV_TOKENS: Tuple[str, ...] = (
    "SECRET", "TOKEN", "PASSWORD", "API_KEY", "PRIVATE_KEY", "DATABASE_URL", "DB_PASS", "AWS_SECRET",
)


@dataclass
class ActiveSandboxRecord:
    """Tracking record for an active sandbox managed by SandboxManager."""

    sandbox_id: str
    sandbox: Sandbox
    spec: SandboxSpec
    started_at: float
    ttl_seconds: int


class SandboxManager:
    """Manages ephemeral sandboxes, trust-boundary transitions, and TTL cleanup."""

    def __init__(self, sandbox_factory: Optional[Callable[[], Sandbox]] = None) -> None:
        self._sandbox_factory: Callable[[], Sandbox] = sandbox_factory or HardenedLocalSandbox
        self._active_sandboxes: Dict[str, ActiveSandboxRecord] = {}
        self._last_trust_level_by_run: Dict[str, TrustLevel] = {}

    @property
    def active_sandboxes(self) -> Dict[str, ActiveSandboxRecord]:
        """Return a snapshot dictionary of currently active sandboxes."""
        return dict(self._active_sandboxes)

    def register_sandbox(
        self,
        sandbox: Sandbox,
        spec: SandboxSpec,
        started_at: Optional[float] = None,
        sandbox_id: Optional[str] = None,
    ) -> str:
        """Register an active sandbox with start timestamp and TTL for watchdog tracking."""
        sb_id = sandbox_id or f"sbx-{spec.run_id}-{uuid.uuid4().hex[:8]}"
        self._active_sandboxes[sb_id] = ActiveSandboxRecord(
            sandbox_id=sb_id,
            sandbox=sandbox,
            spec=spec,
            started_at=started_at if started_at is not None else time.monotonic(),
            ttl_seconds=spec.ttl_seconds,
        )
        return sb_id

    @staticmethod
    def needs_sandbox(
        step_type: str,
        runtime_provider: Optional[str] = None,
        mcp_servers: Optional[List[str]] = None,
        custom_mcp: bool = False,
    ) -> bool:
        """Determine whether a workflow step requires isolated sandbox execution."""
        if custom_mcp:
            return True

        norm_step = (step_type or "").strip().lower()
        if any(token == norm_step or token in norm_step for token in _SANDBOX_STEP_TOKENS):
            return True

        if runtime_provider:
            norm_runtime = runtime_provider.strip().lower()
            if any(token == norm_runtime or token in norm_runtime for token in _SANDBOX_RUNTIME_TOKENS):
                return True

        if mcp_servers:
            for server in mcp_servers:
                lower_srv = server.strip().lower()
                if any(tok in lower_srv for tok in _CUSTOM_MCP_TOKENS):
                    return True

        return False

    @staticmethod
    def verify_step_trust_transition(
        prev_tainted_by_untrusted: bool,
        step_requires_secrets_or_db: bool,
        step_has_raw_untrusted_input: bool,
        prev_trust_level: Optional[TrustLevel] = None,
        current_trust_level: Optional[TrustLevel] = None,
    ) -> bool:
        """Enforce Rule of Three / Trust-Boundary Splitting across workflow steps.

        A step with access to secrets or database state MUST NEVER receive raw
        unsanitized untrusted input, and steps across trust boundaries must execute
        in separate ephemeral sandboxes with structured JSON sanitization.
        """
        if (
            prev_tainted_by_untrusted
            and step_requires_secrets_or_db
            and step_has_raw_untrusted_input
        ):
            raise TrustBoundaryViolationError(
                "Trust boundary violation: tainted step output must be sanitized into structured JSON "
                "before entering a privileged/DB step."
            )

        if step_requires_secrets_or_db and step_has_raw_untrusted_input:
            raise TrustBoundaryViolationError(
                "Rule of Three violation: step requiring secrets/DB cannot receive raw untrusted input."
            )

        if current_trust_level == TrustLevel.UNTRUSTED and step_requires_secrets_or_db:
            raise TrustBoundaryViolationError(
                "Trust boundary violation: UNTRUSTED sandbox cannot access secrets or database."
            )

        if (
            prev_trust_level == TrustLevel.UNTRUSTED
            and current_trust_level == TrustLevel.PRIVILEGED
            and step_has_raw_untrusted_input
        ):
            raise TrustBoundaryViolationError(
                "Trust boundary violation: direct UNTRUSTED to PRIVILEGED transition with raw input."
            )

        return True

    @staticmethod
    def _validate_spec_trust_policy(spec: SandboxSpec) -> None:
        """Ensure UNTRUSTED sandboxes never receive sensitive credentials in env."""
        if spec.trust_level == TrustLevel.UNTRUSTED:
            for env_key in spec.env:
                upper_key = env_key.upper()
                if any(tok in upper_key for tok in _SENSITIVE_ENV_TOKENS):
                    raise TrustBoundaryViolationError(
                        f"UNTRUSTED sandbox forbidden from receiving credential env '{env_key}'."
                    )

    async def run_step(
        self,
        spec: SandboxSpec,
        cmd: List[str],
        timeout: int = 180,
        input_files: Optional[Dict[str, bytes]] = None,
    ) -> ExecResult:
        """Execute a single workflow step inside a fresh ephemeral sandbox.

        Guarantees `await sb.destroy()` is always called in `finally:`, even on
        exception, policy violation, or command timeout.
        """
        self._validate_spec_trust_policy(spec)
        sb = self._sandbox_factory()
        sb_id = self.register_sandbox(sb, spec)
        self._last_trust_level_by_run[spec.run_id] = spec.trust_level

        try:
            await sb.start(spec)
            if input_files:
                for rel_path, content in input_files.items():
                    await sb.write_file(rel_path, content)
            return await sb.exec(cmd, timeout=timeout)
        finally:
            try:
                await sb.destroy()
            finally:
                self._active_sandboxes.pop(sb_id, None)

    def cleanup_expired_sandboxes(self, now: Optional[float] = None) -> int:
        """Destroy any active orphan sandboxes that have exceeded their TTL."""
        current_time = now if now is not None else time.monotonic()
        expired_ids: List[str] = [
            sb_id
            for sb_id, record in self._active_sandboxes.items()
            if (current_time - record.started_at) > float(record.ttl_seconds)
        ]

        destroyed_count = 0
        for sb_id in expired_ids:
            record = self._active_sandboxes.pop(sb_id, None)
            if record is None:
                continue
            sb = record.sandbox
            if hasattr(sb, "destroy_sync"):
                sb.destroy_sync()
            else:
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(sb.destroy())
                except RuntimeError:
                    asyncio.run(sb.destroy())
            destroyed_count += 1

        return destroyed_count
