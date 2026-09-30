"""
Runtime provider registry.

The platform always executes work through the `claude` CLI, but that CLI can be
pointed at different backends. A "runtime provider" captures which backend a run
should use and, critically, which environment variables must be set *or removed*
to get there.

The removal half matters: the subprocess env starts as a copy of the platform's
own environment, so a stale ANTHROPIC_BASE_URL inherited from the shell would
silently hijack a run that asked for native CLI auth.

Provider selection is resolved per run (see runtime_adapter), with detection used
only to populate the first-run choice — never to silently switch a saved default.
"""

import os
import socket
import shutil
import logging
import subprocess
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Provider IDs
PROVIDER_CLAUDE_CODE_NATIVE = "claude_code_native"
PROVIDER_FREE_CLAUDE_CODE = "free_claude_code"
PROVIDER_ANTHROPIC_API = "anthropic_api"
PROVIDER_CUSTOM_GATEWAY = "custom_gateway"

# Env vars that steer the CLI at a non-default backend. Any provider that does
# not own these must actively strip them so an inherited value cannot leak in.
_BACKEND_STEERING_VARS = (
    "ANTHROPIC_BASE_URL",
    "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_API_KEY",
    "CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY",
)

# Keys under which the first-run setup stores the platform-wide provider choice.
SETTING_PROVIDER = "runtime_provider"
SETTING_GATEWAY_URL = "runtime_gateway_base_url"
SETTING_SETUP_COMPLETED = "runtime_setup_completed"

FREE_CLAUDE_CODE_DEFAULT_URL = "http://127.0.0.1:8082"
FREE_CLAUDE_CODE_DEFAULT_TOKEN = "freecc"


class ProviderConfigurationError(ValueError):
    """Raised when a provider is selected but its required configuration is absent or invalid."""


@dataclass
class ProviderStatus:
    """Result of probing one provider's availability on this machine."""
    id: str
    name: str
    description: str
    available: bool
    detail: str
    requires_config: bool = False
    # Non-secret config echoed back to the UI. Tokens are never included.
    config: Dict[str, Any] = field(default_factory=dict)


def _strip_steering_vars(env: Dict[str, str]) -> None:
    """Remove every backend-steering var so the caller starts from a clean slate."""
    for var in _BACKEND_STEERING_VARS:
        env.pop(var, None)


def _port_is_open(url: str, timeout: float = 0.6) -> bool:
    """Best-effort TCP reachability probe for a gateway URL."""
    try:
        parsed = urlparse(url)
        host = parsed.hostname
        if not host:
            return False
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, ValueError):
        return False


def validate_gateway_url(url: str) -> str:
    """
    Validate a user-supplied gateway URL.

    Only http/https with an explicit host is accepted, so a malformed or
    non-HTTP scheme cannot be handed to the CLI as a base URL.
    """
    candidate = (url or "").strip()
    if not candidate:
        raise ProviderConfigurationError("Gateway base URL is required.")
    parsed = urlparse(candidate)
    if parsed.scheme not in ("http", "https"):
        raise ProviderConfigurationError(
            f"Gateway base URL must use http or https (got '{parsed.scheme or 'no scheme'}')."
        )
    if not parsed.hostname:
        raise ProviderConfigurationError("Gateway base URL must include a host.")
    return candidate.rstrip("/")


def _native_credentials_detail() -> tuple[bool, str]:
    """
    Check whether the local `claude` CLI has credentials, without reading them.

    Existence is probed three ways because the CLI stores auth differently per
    platform: macOS keychain, a credentials file, or an OAuth token in the env.
    The secret itself is never read or logged.
    """
    if os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "").strip():
        return True, "Authenticated via CLAUDE_CODE_OAUTH_TOKEN."

    creds_file = Path.home() / ".claude" / ".credentials.json"
    if creds_file.exists():
        return True, "Authenticated via ~/.claude/.credentials.json."

    try:
        # -w is deliberately omitted: this checks for the entry's existence and
        # never prints the secret.
        result = subprocess.run(
            ["security", "find-generic-password", "-s", "Claude Code-credentials"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
        if result.returncode == 0:
            return True, "Authenticated via macOS keychain."
    except (OSError, subprocess.SubprocessError):
        pass

    return False, "CLI found but no credentials detected — run `claude` once to log in."


def _detect_native() -> ProviderStatus:
    cli_path = shutil.which("claude")
    if not cli_path:
        return ProviderStatus(
            id=PROVIDER_CLAUDE_CODE_NATIVE,
            name="Claude Code (this machine)",
            description="Runs through the `claude` CLI using your own login. No proxy.",
            available=False,
            detail="`claude` was not found on PATH.",
        )
    authed, detail = _native_credentials_detail()
    return ProviderStatus(
        id=PROVIDER_CLAUDE_CODE_NATIVE,
        name="Claude Code (this machine)",
        description="Runs through the `claude` CLI using your own login. No proxy.",
        available=authed,
        detail=detail,
        config={"cli_path": cli_path},
    )


def _detect_free_claude_code() -> ProviderStatus:
    url = os.environ.get("FCC_PROXY_URL", FREE_CLAUDE_CODE_DEFAULT_URL).strip() or FREE_CLAUDE_CODE_DEFAULT_URL
    reachable = _port_is_open(url)
    return ProviderStatus(
        id=PROVIDER_FREE_CLAUDE_CODE,
        name="Free Claude Code proxy",
        description="Routes the CLI through a local Free Claude Code gateway.",
        available=reachable,
        detail=(
            f"Proxy reachable at {url}."
            if reachable
            else f"No proxy listening at {url}."
        ),
        config={"base_url": url},
    )


def _detect_anthropic_api() -> ProviderStatus:
    has_key = bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())
    return ProviderStatus(
        id=PROVIDER_ANTHROPIC_API,
        name="Anthropic API key",
        description="Billed directly against an Anthropic API key from the environment.",
        available=has_key,
        detail=(
            "ANTHROPIC_API_KEY is set."
            if has_key
            else "ANTHROPIC_API_KEY is not set in the platform environment."
        ),
    )


def _detect_custom_gateway() -> ProviderStatus:
    raw_url = os.environ.get("PLATFORM_GATEWAY_BASE_URL", "").strip()
    configured = bool(raw_url)
    detail = "No PLATFORM_GATEWAY_BASE_URL configured."
    reachable = False
    if configured:
        try:
            raw_url = validate_gateway_url(raw_url)
            reachable = _port_is_open(raw_url)
            detail = (
                f"Gateway reachable at {raw_url}."
                if reachable
                else f"Configured at {raw_url} but not reachable."
            )
        except ProviderConfigurationError as exc:
            configured = False
            detail = str(exc)
    return ProviderStatus(
        id=PROVIDER_CUSTOM_GATEWAY,
        name="Custom gateway",
        description=(
            "Any Anthropic-API-compatible gateway (LiteLLM, Bedrock proxy, NVIDIA NIM). "
            "This is also how non-Anthropic models such as OpenAI are reached."
        ),
        available=configured and reachable,
        detail=detail,
        requires_config=True,
        config={"base_url": raw_url} if configured else {},
    )


_DETECTORS = {
    PROVIDER_CLAUDE_CODE_NATIVE: _detect_native,
    PROVIDER_FREE_CLAUDE_CODE: _detect_free_claude_code,
    PROVIDER_ANTHROPIC_API: _detect_anthropic_api,
    PROVIDER_CUSTOM_GATEWAY: _detect_custom_gateway,
}

ALL_PROVIDER_IDS: List[str] = list(_DETECTORS.keys())


def detect_providers() -> List[ProviderStatus]:
    """Probe every known provider on this machine, in preference order."""
    return [detector() for detector in _DETECTORS.values()]


def detect_provider(provider_id: str) -> ProviderStatus:
    """Probe a single provider. Raises ProviderConfigurationError for unknown IDs."""
    detector = _DETECTORS.get(provider_id)
    if not detector:
        raise ProviderConfigurationError(f"Unknown runtime provider '{provider_id}'.")
    return detector()


def suggest_default_provider() -> Optional[str]:
    """
    Suggest which provider to preselect in the first-run prompt.

    Returns the first available provider in preference order, or None when the
    machine has nothing usable configured. This only ever *suggests* — the saved
    default is whatever the user picks.
    """
    for status in detect_providers():
        if status.available:
            return status.id
    return None


def build_provider_env(
    provider_id: str,
    base_env: Dict[str, str],
    gateway_base_url: Optional[str] = None,
) -> Dict[str, str]:
    """
    Apply a provider's backend routing to a copied environment.

    Every provider first strips the steering vars, then sets only what it owns.
    Secrets are read from the live environment at call time and are never
    persisted or logged.
    """
    env = dict(base_env)
    _strip_steering_vars(env)

    if provider_id == PROVIDER_CLAUDE_CODE_NATIVE:
        # Deliberately sets nothing: the CLI must fall back to its own stored
        # credentials. Any inherited override was stripped above.
        return env

    if provider_id == PROVIDER_FREE_CLAUDE_CODE:
        url = (
            gateway_base_url
            or os.environ.get("FCC_PROXY_URL", "").strip()
            or FREE_CLAUDE_CODE_DEFAULT_URL
        )
        env["ANTHROPIC_BASE_URL"] = validate_gateway_url(url)
        env["ANTHROPIC_AUTH_TOKEN"] = (
            os.environ.get("FCC_AUTH_TOKEN", "").strip() or FREE_CLAUDE_CODE_DEFAULT_TOKEN
        )
        env["CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY"] = "1"
        return env

    if provider_id == PROVIDER_ANTHROPIC_API:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        if not api_key:
            raise ProviderConfigurationError(
                "Provider 'anthropic_api' selected but ANTHROPIC_API_KEY is not set."
            )
        env["ANTHROPIC_API_KEY"] = api_key
        return env

    if provider_id == PROVIDER_CUSTOM_GATEWAY:
        url = gateway_base_url or os.environ.get("PLATFORM_GATEWAY_BASE_URL", "").strip()
        if not url:
            raise ProviderConfigurationError(
                "Provider 'custom_gateway' selected but no gateway base URL is configured."
            )
        env["ANTHROPIC_BASE_URL"] = validate_gateway_url(url)
        token = os.environ.get("PLATFORM_GATEWAY_AUTH_TOKEN", "").strip()
        if token:
            env["ANTHROPIC_AUTH_TOKEN"] = token
        env["CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY"] = "1"
        return env

    raise ProviderConfigurationError(f"Unknown runtime provider '{provider_id}'.")
