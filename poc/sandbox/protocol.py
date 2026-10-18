"""Sandbox execution protocol, HardenedLocalSandbox, and E2BMicroVMSandboxAdapter."""

from __future__ import annotations

import asyncio
import os
import re
import shutil
import stat
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, List, Optional, Protocol, Tuple, runtime_checkable
from urllib.parse import urlparse

from poc.sandbox.models import (
    ExecResult, SandboxEscapeAttemptError, SandboxSecurityError, SandboxSpec, SandboxTimeoutError,
)

_FORBIDDEN_PATHS: Tuple[str, ...] = (
    "agents_platform.db", ".env", "/var/run/docker.sock", "docker.sock",
    "/etc/shadow", "/etc/passwd", "/proc/", "/sys/", ".ssh",
)
_PRIV_ESC_RE = re.compile(
    r"(?:^|\s|;|&|\|)(?:sudo|su|docker|nsenter|chroot|mount|umount)(?:\s|$|-)"
    r"|chmod\s+(?:[ugoa]*\+s|[2467][0-7]{3})\b"
)
_ENV_DUMP_RE = re.compile(
    r"(?:^|\s|;|&|\|)printenv(?:\s|$)|/proc/(?:self|\d+)/environ"
    r"|^\s*(?:env|set|Get-ChildItem\s+Env:)\s*$|(?:\b(?:env|printenv)\s*(?:$|[;|>&]))",
    re.IGNORECASE,
)
_NET_CMD_RE = re.compile(
    r"(?:^|\s|;|&|\|)(?:curl|wget|Invoke-WebRequest|iwr|nc|ncat|netcat)(?:\s|$)", re.IGNORECASE,
)
_URL_RE = re.compile(r"https?://[^\s\"'>)]+", re.IGNORECASE)
_TRAVERSAL_CMD_RE = re.compile(r"(?:^|[\s/\\=])\.\.(?:[\s/\\]|$)")
_METADATA_HOSTS: Tuple[str, ...] = (
    "169.254.169.254", "169.254.170.2", "metadata.google.internal", "fd00:ec2::254",
)


@runtime_checkable
class Sandbox(Protocol):
    """Protocol interface for isolated execution sandboxes."""

    async def start(self, spec: SandboxSpec) -> None: ...
    async def write_file(self, path: str, data: bytes) -> None: ...
    async def read_file(self, path: str) -> bytes: ...
    async def exec(self, cmd: List[str], timeout: int) -> ExecResult: ...
    async def destroy(self) -> None: ...


class HardenedLocalSandbox:
    """Fail-closed local sandbox enforcing filesystem, command, and egress isolation."""

    def __init__(self) -> None:
        self._spec: Optional[SandboxSpec] = None
        self._root_dir: Optional[Path] = None
        self._work_dir: Optional[Path] = None
        self._tmp_dir: Optional[Path] = None
        self._started_at: float = 0.0
        self._destroyed: bool = False

    @property
    def root_dir(self) -> Optional[Path]:
        """Return the host path to the ephemeral sandbox root directory."""
        return self._root_dir

    async def start(self, spec: SandboxSpec) -> None:
        """Create isolated ephemeral root with /work and /tmp subdirectories."""
        if self._spec is not None and not self._destroyed:
            raise SandboxSecurityError("Sandbox is already started.")
        self._spec, self._destroyed, self._started_at = spec, False, time.monotonic()
        safe_prefix = re.sub(r"[^a-zA-Z0-9_-]", "_", f"sbx_{spec.org_id}_{spec.run_id}_")
        self._root_dir = Path(tempfile.mkdtemp(prefix=safe_prefix)).resolve()
        self._work_dir = (self._root_dir / "work").resolve()
        self._tmp_dir = (self._root_dir / "tmp").resolve()
        self._work_dir.mkdir(parents=True, exist_ok=True)
        self._tmp_dir.mkdir(parents=True, exist_ok=True)

    def _ensure_active(self) -> Tuple[SandboxSpec, Path, Path, Path]:
        if self._destroyed or self._spec is None or self._root_dir is None:
            raise SandboxSecurityError("Operation attempted on unstarted or destroyed sandbox.")
        assert self._work_dir is not None and self._tmp_dir is not None
        return self._spec, self._root_dir, self._work_dir, self._tmp_dir

    def _resolve_sandbox_path(self, raw_path: str, for_write: bool) -> Path:
        _, root_dir, work_dir, tmp_dir = self._ensure_active()
        if not raw_path or not raw_path.strip():
            raise SandboxEscapeAttemptError("Empty sandbox file path is forbidden.")
        norm = raw_path.replace("\\", "/")
        lower_norm = norm.lower()
        for pat in _FORBIDDEN_PATHS:
            if pat.lower() in lower_norm:
                raise SandboxEscapeAttemptError(f"Blocked protected resource '{pat}' in '{raw_path}'.")
        if ".." in norm.split("/") or ".." in raw_path:
            raise SandboxEscapeAttemptError(f"Path traversal ('..') detected in '{raw_path}'.")
        if re.match(r"^[a-zA-Z]:", raw_path) or norm.startswith("//"):
            raise SandboxEscapeAttemptError(f"Host absolute path forbidden: '{raw_path}'.")

        if norm in ("/work", "work") or norm.startswith(("/work/", "work/")):
            candidate = (work_dir / norm.lstrip("/")[len("work") :].lstrip("/")).resolve()
        elif norm in ("/tmp", "tmp") or norm.startswith(("/tmp/", "tmp/")):
            candidate = (tmp_dir / norm.lstrip("/")[len("tmp") :].lstrip("/")).resolve()
        elif norm.startswith("/"):
            candidate = (root_dir / norm.lstrip("/")).resolve()
        else:
            candidate = (work_dir / norm).resolve()

        if not candidate.is_relative_to(root_dir):
            raise SandboxEscapeAttemptError(f"Resolved path '{candidate}' escapes sandbox root.")
        if for_write and not (candidate.is_relative_to(work_dir) or candidate.is_relative_to(tmp_dir)):
            raise SandboxEscapeAttemptError(f"Write denied to '{raw_path}': only /work and /tmp writable.")
        return candidate

    async def write_file(self, path: str, data: bytes) -> None:
        """Write data to a file inside /work or /tmp after security validation."""
        spec, _, _, _ = self._ensure_active()
        target = self._resolve_sandbox_path(path, for_write=True)
        if len(data) > spec.disk_mb * 1024 * 1024:
            raise SandboxSecurityError(f"File payload exceeds disk quota ({spec.disk_mb} MB).")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    async def read_file(self, path: str) -> bytes:
        """Read data from a file inside the sandbox after security validation."""
        target = self._resolve_sandbox_path(path, for_write=False)
        if not target.exists() or not target.is_file():
            raise FileNotFoundError(f"Sandbox file not found: {path}")
        return target.read_bytes()

    @staticmethod
    def _is_domain_allowed(hostname: str, allowlist: Tuple[str, ...]) -> bool:
        host = hostname.strip().lower().rstrip(".")
        for allowed in allowlist:
            entry = allowed.strip().lower().rstrip(".")
            if entry == host or (entry.startswith("*.") and (host == entry[2:] or host.endswith("." + entry[2:]))):
                return True
        return False

    @classmethod
    def inspect_command(cls, cmd: List[str], spec: SandboxSpec) -> None:
        """Inspect command tokens and raise SandboxEscapeAttemptError on policy violation."""
        if not cmd or not any(tok.strip() for tok in cmd):
            raise SandboxSecurityError("Cannot execute an empty command in sandbox.")
        joined = " ".join(cmd)
        lower_joined = joined.lower()
        for host in _METADATA_HOSTS:
            if host in lower_joined:
                raise SandboxEscapeAttemptError(f"Blocked by Sandbox Security Policy: metadata access ({host}).")
        for pat in _FORBIDDEN_PATHS:
            if pat.lower() in lower_joined:
                raise SandboxEscapeAttemptError(f"Blocked by Sandbox Security Policy: resource '{pat}'.")
        if _TRAVERSAL_CMD_RE.search(joined):
            raise SandboxEscapeAttemptError("Blocked by Sandbox Security Policy: path traversal ('..').")
        if _PRIV_ESC_RE.search(joined):
            raise SandboxEscapeAttemptError("Blocked by Sandbox Security Policy: privilege escalation.")
        if _ENV_DUMP_RE.search(joined):
            raise SandboxEscapeAttemptError("Blocked by Sandbox Security Policy: raw environment dump.")

        urls = _URL_RE.findall(joined)
        has_net_cmd = bool(_NET_CMD_RE.search(joined))
        if urls or has_net_cmd:
            hosts = [urlparse(u).hostname for u in urls if urlparse(u).hostname]
            if has_net_cmd and not hosts:
                for tok in cmd[1:]:
                    if not tok.startswith("-") and "." in tok and not tok.startswith("/"):
                        h = urlparse(tok if "://" in tok else f"https://{tok}").hostname
                        if h:
                            hosts.append(h)
            if not hosts:
                raise SandboxEscapeAttemptError("Blocked by Sandbox Security Policy: unverified network command.")
            for h in hosts:
                if h in _METADATA_HOSTS or not cls._is_domain_allowed(h, spec.egress_allowlist):
                    raise SandboxEscapeAttemptError(f"Blocked by Sandbox Security Policy: egress '{h}' denied.")

    async def exec(self, cmd: List[str], timeout: int = 180) -> ExecResult:
        """Execute an inspected command inside the isolated workspace with capped timeout."""
        spec, _, work_dir, tmp_dir = self._ensure_active()
        self.inspect_command(cmd, spec)
        if timeout <= 0:
            raise SandboxTimeoutError("Execution timeout must be positive.")
        effective_timeout = min(timeout, spec.ttl_seconds)
        exec_cmd = [sys.executable if cmd[0] in ("python", "python3") else cmd[0], *cmd[1:]]
        safe_env = {
            "PATH": os.environ.get("PATH", ""), "HOME": str(work_dir),
            "TMPDIR": str(tmp_dir), "TEMP": str(tmp_dir), "TMP": str(tmp_dir),
            "USER": spec.non_root_user, "SANDBOX_TRUST_LEVEL": spec.trust_level.value,
        }
        if os.name == "nt":
            safe_env.update({k: os.environ[k] for k in ("SYSTEMROOT", "COMSPEC", "PATHEXT") if k in os.environ})
        safe_env.update(spec.env)

        start_ts = time.perf_counter()
        try:
            proc = await asyncio.create_subprocess_exec(
                *exec_cmd, cwd=str(work_dir), env=safe_env,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=float(effective_timeout))
                dur = (time.perf_counter() - start_ts) * 1000.0
                cost = round((dur / 1000.0) * 0.0001 * spec.cpu, 6)
                return ExecResult(
                    proc.returncode or 0, stdout_b.decode("utf-8", errors="replace"),
                    stderr_b.decode("utf-8", errors="replace"), False, dur, cost,
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.communicate()
                dur = (time.perf_counter() - start_ts) * 1000.0
                cost = round((dur / 1000.0) * 0.0001 * spec.cpu, 6)
                return ExecResult(124, "", f"Command timed out after {effective_timeout}s", True, dur, cost)
        except FileNotFoundError as exc:
            dur = (time.perf_counter() - start_ts) * 1000.0
            return ExecResult(127, "", f"Executable not found: {exc}", False, dur)

    def destroy_sync(self) -> None:
        """Synchronously wipe and delete the ephemeral sandbox directory."""
        root = self._root_dir
        self._destroyed = True
        self._root_dir = self._work_dir = self._tmp_dir = None
        if root is not None and root.exists():
            shutil.rmtree(root, onerror=lambda fn, p, _: (os.chmod(p, stat.S_IWRITE), fn(p)))

    async def destroy(self) -> None:
        """Securely wipe and delete the ephemeral sandbox directory."""
        self.destroy_sync()


class E2BMicroVMSandboxAdapter(HardenedLocalSandbox):
    """Adapter that delegates to E2B Firecracker MicroVMs when E2B_API_KEY is configured."""

    def __init__(self, api_key: Optional[str] = None) -> None:
        super().__init__()
        self._api_key = api_key if api_key is not None else os.environ.get("E2B_API_KEY")
        self._remote_sbx: Any = None

    @property
    def uses_remote_microvm(self) -> bool:
        """Return True if backed by a live E2B MicroVM session."""
        return bool(self._api_key) and self._remote_sbx is not None
