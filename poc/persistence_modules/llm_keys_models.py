"""
Domain models, constants, and validation helpers for BYOK LLM credentials.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional
from urllib.parse import urlparse

SUPPORTED_LLM_PROVIDERS: tuple[str, ...] = ("anthropic", "openai", "nvidia")

DEFAULT_PROVIDER_MODELS: Dict[str, str] = {
    "anthropic": "claude-3-5-sonnet-latest",
    "openai": "gpt-4o",
    "nvidia": "meta/llama-3.1-70b-instruct",
}

DEFAULT_PROVIDER_BASE_URLS: Dict[str, str] = {
    "anthropic": "https://api.anthropic.com/v1/messages",
    "openai": "https://api.openai.com/v1/chat/completions",
    "nvidia": "https://integrate.api.nvidia.com/v1/chat/completions",
}

PROVIDER_ENV_VARS: Dict[str, str] = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "nvidia": "NVIDIA_API_KEY",
}


def mask_api_key(raw_key: str) -> str:
    """Compute non-reversible masked representation of an API key (e.g. sk-ant...9a2f)."""
    clean = (raw_key or "").strip()
    if len(clean) > 10:
        return f"{clean[:6]}...{clean[-4:]}"
    return f"{clean[:2]}...{clean[-2:]}" if len(clean) > 4 else "***"


def validate_provider_base_url(url: str) -> str:
    """Reject endpoints exfiltrating keys or reaching internal services (SSRF).

    Production: https only and no loopback/private/link-local/metadata hosts.
    Non-production: plain http is permitted for loopback only (local test servers).
    """
    parsed = urlparse((url or "").strip())
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in ("http", "https") or not host:
        raise ValueError("Fail-closed: base_url must be an absolute http(s) URL")
    if parsed.username or parsed.password:
        raise ValueError("Fail-closed: base_url must not embed credentials")

    is_prod = os.getenv("ENV", os.getenv("PLATFORM_ENV", "dev")).strip().lower() in ("prod", "production")
    if is_prod:
        if parsed.scheme != "https":
            raise ValueError("Fail-closed: base_url must use https in production")
        try:
            from gateways.egress_proxy import EgressProxy
        except ImportError:
            from poc.gateways.egress_proxy import EgressProxy
        reason = EgressProxy._is_blocked_ip_or_host(host)
        if reason:
            raise ValueError(f"Fail-closed: base_url host rejected ({reason})")
    elif parsed.scheme == "http" and host not in ("127.0.0.1", "localhost", "::1"):
        raise ValueError("Fail-closed: plain http base_url is only allowed for loopback hosts")
    return url.strip()


@dataclass
class OrgLLMCredential:
    """Metadata and masked representation of a tenant BYOK LLM credential."""

    id: str
    organization_id: str
    department_id: Optional[str]
    provider: str
    key_alias: str
    masked_key: str
    default_model: str
    base_url: Optional[str]
    is_active: bool
    created_at: str
    updated_at: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert credential metadata to a JSON-serializable dictionary (never includes raw key)."""
        return asdict(self)
