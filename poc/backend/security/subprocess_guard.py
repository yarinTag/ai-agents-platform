"""
Subprocess environment sanitization and execution permission guard.

Prevents accidental leakage of host/control-plane secrets into agent subprocesses
and enforces fail-closed microVM isolation checks before allowing permission bypass flags.
"""

from __future__ import annotations

import os
from typing import Dict, Optional, Sequence, Set

# Safe operating system fundamentals permitted in subprocess environments
_SAFE_OS_ENV_KEYS: Set[str] = {
    "PATH",
    "SYSTEMROOT",
    "TEMP",
    "TMP",
    "HOME",
    "LANG",
}

# Explicitly permitted non-secret runtime variables for sandboxed agent execution
_ALLOWED_RUNTIME_ENV_KEYS: Set[str] = {
    "run_token",
    "SANDBOX_RUN_TOKEN",
    "LLM_PROXY_URL",
    "MCP_GATEWAY_URL",
    "EGRESS_PROXY_URL",
}

# Substrings that mark an environment variable name as sensitive/secret
_FORBIDDEN_KEY_SUBSTRINGS: tuple[str, ...] = (
    "SECRET",
    "TOKEN",
    "KEY",
    "PASSWORD",
    "DATABASE_URL",
    "PLATFORM_API_KEY",
)

# Explicit exceptions to the `TOKEN` substring filter
_ALLOWED_TOKEN_EXCEPTIONS: Set[str] = {
    "SANDBOX_RUN_TOKEN",
    "run_token",
}


def _is_forbidden_secret_var(var_name: str) -> bool:
    """
    Return True if `var_name` matches any forbidden secret pattern.

    Strips any variable containing SECRET, TOKEN (except SANDBOX_RUN_TOKEN / run_token),
    KEY, PASSWORD, DATABASE_URL, or PLATFORM_API_KEY.
    """
    if not var_name or not isinstance(var_name, str):
        return True

    clean_name = var_name.strip()
    if clean_name in _ALLOWED_TOKEN_EXCEPTIONS:
        return False

    upper_name = clean_name.upper()
    if upper_name == "SANDBOX_RUN_TOKEN":
        return False

    return any(marker in upper_name for marker in _FORBIDDEN_KEY_SUBSTRINGS)


def build_sanitized_subprocess_env(
    extra_env: Optional[Dict[str, str]] = None,
    allowlist: Optional[Sequence[str]] = None,
) -> Dict[str, str]:
    """
    Construct a minimal, secret-scrubbed environment dictionary for subprocess execution.

    Never passes `os.environ` directly. Copies only safe OS fundamentals (`PATH`,
    `SYSTEMROOT`, `TEMP`, `TMP`, `HOME`, `LANG`) and explicitly allowed non-secret
    runtime variables (`run_token`, `SANDBOX_RUN_TOKEN`, `LLM_PROXY_URL`,
    `MCP_GATEWAY_URL`, `EGRESS_PROXY_URL`, plus any non-secret keys in `allowlist`).
    """
    permitted_keys: Set[str] = set(_SAFE_OS_ENV_KEYS) | set(_ALLOWED_RUNTIME_ENV_KEYS)
    if allowlist:
        for key in allowlist:
            if isinstance(key, str) and key.strip() and not _is_forbidden_secret_var(key):
                permitted_keys.add(key.strip())

    sanitized_env: Dict[str, str] = {}

    # Copy only permitted keys from host os.environ that pass the secret filter
    for env_key, env_val in os.environ.items():
        if env_key in permitted_keys and not _is_forbidden_secret_var(env_key):
            sanitized_env[env_key] = str(env_val)

    # Merge caller-provided extra_env, stripping any forbidden secret keys
    if extra_env:
        for extra_key, extra_val in extra_env.items():
            if not isinstance(extra_key, str) or extra_val is None:
                continue
            clean_key = extra_key.strip()
            if not clean_key or _is_forbidden_secret_var(clean_key):
                continue
            if allowlist is not None and clean_key not in permitted_keys:
                continue
            sanitized_env[clean_key] = str(extra_val)

    return sanitized_env


def validate_agent_execution_flags(
    dangerously_skip_permissions: bool,
    inside_isolated_sandbox: bool = False,
) -> bool:
    """
    Validate agent CLI execution flags against sandbox isolation posture.

    Fails closed by raising `PermissionError` if `dangerously_skip_permissions=True`
    is requested outside a hardware/kernel-isolated sandbox (`inside_isolated_sandbox=False`).
    """
    if bool(dangerously_skip_permissions) and not bool(inside_isolated_sandbox):
        raise PermissionError(
            "Fail-closed: dangerously_skip_permissions=True is forbidden outside an isolated microVM sandbox"
        )
    return True
