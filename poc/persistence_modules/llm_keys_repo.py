"""Multi-Provider BYOK LLM Credentials Vault Repository Mixin.
Per-tenant AES-256-GCM envelope encryption (`shared.envelope_crypto`).
"""
from __future__ import annotations
import json, os, uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

try:
    from shared.envelope_crypto import decrypt_secret_config, encrypt_secret_config
except ImportError:
    from poc.shared.envelope_crypto import decrypt_secret_config, encrypt_secret_config

SUPPORTED_LLM_PROVIDERS: tuple[str, ...] = ("anthropic", "openai", "nvidia")
DEFAULT_PROVIDER_MODELS: Dict[str, str] = {
    "anthropic": "claude-3-5-sonnet-latest", "openai": "gpt-4o", "nvidia": "meta/llama-3.1-70b-instruct",
}
DEFAULT_PROVIDER_BASE_URLS: Dict[str, str] = {
    "anthropic": "https://api.anthropic.com/v1/messages",
    "openai": "https://api.openai.com/v1/chat/completions",
    "nvidia": "https://integrate.api.nvidia.com/v1/chat/completions",
}
PROVIDER_ENV_VARS: Dict[str, str] = {
    "anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY", "nvidia": "NVIDIA_API_KEY",
}


def mask_api_key(raw_key: str) -> str:
    """Compute non-reversible masked representation of an API key (e.g. sk-ant...9a2f)."""
    clean = (raw_key or "").strip()
    if len(clean) > 10:
        return f"{clean[:6]}...{clean[-4:]}"
    return f"{clean[:2]}...{clean[-2:]}" if len(clean) > 4 else "***"


def validate_provider_base_url(url: str) -> str:
    """Reject endpoints exfiltrating keys or reaching internal services (SSRF)."""
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


class LLMKeysRepositoryMixin:
    """Mixin providing encrypted BYOK LLM credential persistence and resolution."""

    def ensure_llm_keys_table(self) -> None:
        """Ensure the `org_llm_credentials` table and indexes exist in SQLite."""
        with self._get_connection() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS org_llm_credentials ("
                "id TEXT PRIMARY KEY, organization_id TEXT NOT NULL, department_id TEXT, "
                "provider TEXT NOT NULL, key_alias TEXT, encrypted_envelope_json TEXT NOT NULL, "
                "masked_key TEXT NOT NULL, default_model TEXT, base_url TEXT, "
                "is_active INTEGER DEFAULT 1, created_at TEXT, updated_at TEXT, "
                "UNIQUE(organization_id, department_id, provider))"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_org_llm_creds_org_prov "
                "ON org_llm_credentials(organization_id, provider)"
            )
            conn.commit()

    @staticmethod
    def _row_to_credential(row: Any) -> OrgLLMCredential:
        """Map a SQLite row to an `OrgLLMCredential` instance."""
        d = dict(row)
        prov = str(d["provider"]).lower()
        return OrgLLMCredential(
            id=str(d["id"]), organization_id=str(d["organization_id"]), department_id=d.get("department_id"),
            provider=prov, key_alias=str(d.get("key_alias") or f"{prov}-key"), masked_key=str(d["masked_key"]),
            default_model=str(d.get("default_model") or DEFAULT_PROVIDER_MODELS.get(prov, "default")),
            base_url=d.get("base_url"), is_active=bool(d.get("is_active", 1)),
            created_at=str(d.get("created_at") or ""), updated_at=str(d.get("updated_at") or ""),
        )

    def save_org_llm_credential(
        self, organization_id: str, provider: str, api_key: str,
        department_id: Optional[str] = None, key_alias: Optional[str] = None,
        default_model: Optional[str] = None, base_url: Optional[str] = None,
    ) -> OrgLLMCredential:
        """Validate, envelope-encrypt, and persist (or rotate in place) a BYOK LLM API key."""
        clean_org, norm_provider, clean_key = (organization_id or "").strip(), (provider or "").strip().lower(), (api_key or "").strip()
        if not clean_org or not clean_key:
            raise ValueError("Fail-closed: organization_id and api_key are required")
        if norm_provider not in SUPPORTED_LLM_PROVIDERS:
            raise ValueError(f"Unsupported LLM provider '{provider}'. Must be in {SUPPORTED_LLM_PROVIDERS}")

        clean_dept = department_id.strip() if isinstance(department_id, str) and department_id.strip() else None
        alias = (key_alias or "").strip() or f"{norm_provider}-default"
        model = (default_model or "").strip() or DEFAULT_PROVIDER_MODELS[norm_provider]
        clean_url = validate_provider_base_url((base_url or "").strip() or DEFAULT_PROVIDER_BASE_URLS[norm_provider])

        envelope = encrypt_secret_config({"api_key": clean_key, "provider": norm_provider}, org_id=clean_org)
        envelope_json = json.dumps(envelope, sort_keys=True, separators=(",", ":"))
        masked, now = mask_api_key(clean_key), datetime.now(timezone.utc).isoformat()

        self.ensure_llm_keys_table()
        with self._get_connection() as conn:
            q = ("SELECT id, created_at FROM org_llm_credentials WHERE organization_id = ? AND department_id IS NULL AND provider = ?"
                 if clean_dept is None else "SELECT id, created_at FROM org_llm_credentials WHERE organization_id = ? AND department_id = ? AND provider = ?")
            params = (clean_org, norm_provider) if clean_dept is None else (clean_org, clean_dept, norm_provider)
            existing = conn.execute(q, params).fetchone()
            if existing:
                cred_id, created_at = str(existing["id"]), str(existing["created_at"] or now)
                conn.execute(
                    "UPDATE org_llm_credentials SET key_alias = ?, encrypted_envelope_json = ?, masked_key = ?, default_model = ?, base_url = ?, is_active = 1, updated_at = ? WHERE id = ? AND organization_id = ?",
                    (alias, envelope_json, masked, model, clean_url, now, cred_id, clean_org),
                )
            else:
                cred_id, created_at = f"llmkey_{uuid.uuid4().hex[:12]}", now
                conn.execute(
                    "INSERT INTO org_llm_credentials (id, organization_id, department_id, provider, key_alias, encrypted_envelope_json, masked_key, default_model, base_url, is_active, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)",
                    (cred_id, clean_org, clean_dept, norm_provider, alias, envelope_json, masked, model, clean_url, created_at, now),
                )
            conn.commit()

        return OrgLLMCredential(
            id=cred_id, organization_id=clean_org, department_id=clean_dept, provider=norm_provider,
            key_alias=alias, masked_key=masked, default_model=model, base_url=clean_url,
            is_active=True, created_at=created_at, updated_at=now,
        )

    def list_org_llm_credentials(self, organization_id: str, department_id: Optional[str] = None) -> List[OrgLLMCredential]:
        """List stored LLM credentials for an organization with `masked_key` only."""
        clean_org = (organization_id or "").strip()
        if not clean_org:
            return []
        self.ensure_llm_keys_table()
        with self._get_connection() as conn:
            if department_id is not None:
                rows = conn.execute(
                    "SELECT * FROM org_llm_credentials WHERE organization_id = ? AND (department_id = ? OR department_id IS NULL) ORDER BY provider ASC",
                    (clean_org, department_id.strip()),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM org_llm_credentials WHERE organization_id = ? ORDER BY provider ASC",
                    (clean_org,),
                ).fetchall()
            return [self._row_to_credential(r) for r in rows]

    def resolve_org_llm_api_key(
        self, organization_id: str, provider: str, department_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Resolve and decrypt active key (dept -> org -> env var fallback) or raise `PermissionError`."""
        clean_org, norm_provider = (organization_id or "").strip(), (provider or "").strip().lower()
        if not clean_org or norm_provider not in SUPPORTED_LLM_PROVIDERS:
            raise PermissionError(f"Fail-closed: Invalid organization '{clean_org}' or provider '{provider}'")

        self.ensure_llm_keys_table()
        row, source = None, "org_vault"
        clean_dept = department_id.strip() if isinstance(department_id, str) and department_id.strip() else None

        with self._get_connection() as conn:
            if clean_dept:
                row = conn.execute(
                    "SELECT * FROM org_llm_credentials WHERE organization_id = ? AND department_id = ? AND provider = ? AND is_active = 1",
                    (clean_org, clean_dept, norm_provider),
                ).fetchone()
                if row:
                    source = "department_vault"
            if row is None:
                row = conn.execute(
                    "SELECT * FROM org_llm_credentials WHERE organization_id = ? AND department_id IS NULL AND provider = ? AND is_active = 1",
                    (clean_org, norm_provider),
                ).fetchone()

        if row is not None:
            try:
                decrypted = decrypt_secret_config(json.loads(row["encrypted_envelope_json"]), org_id=clean_org)
                api_key = str(decrypted.get("api_key") or "").strip()
            except Exception as exc:
                raise PermissionError(f"Fail-closed: Unable to decrypt LLM credential: {exc}") from exc
            if not api_key:
                raise PermissionError("Fail-closed: Decrypted LLM credential has empty api_key")
            return {
                "credential_id": str(row["id"]), "organization_id": clean_org, "department_id": row["department_id"],
                "provider": norm_provider, "api_key": api_key,
                "default_model": str(row["default_model"] or DEFAULT_PROVIDER_MODELS[norm_provider]),
                "base_url": str(row["base_url"] or DEFAULT_PROVIDER_BASE_URLS[norm_provider]), "source": source,
            }

        env_key = os.getenv(PROVIDER_ENV_VARS[norm_provider], "").strip()
        if env_key:
            return {
                "credential_id": None, "organization_id": clean_org, "department_id": clean_dept,
                "provider": norm_provider, "api_key": env_key,
                "default_model": DEFAULT_PROVIDER_MODELS[norm_provider],
                "base_url": DEFAULT_PROVIDER_BASE_URLS[norm_provider], "source": "environment",
            }
        raise PermissionError(f"Fail-closed: No LLM API key configured for provider '{norm_provider}' in organization '{clean_org}'")

    def delete_org_llm_credential(self, credential_id: str, organization_id: str) -> bool:
        """Delete a stored LLM credential scoped strictly to `organization_id`."""
        clean_id, clean_org = (credential_id or "").strip(), (organization_id or "").strip()
        if not clean_id or not clean_org:
            return False
        self.ensure_llm_keys_table()
        with self._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM org_llm_credentials WHERE id = ? AND organization_id = ?", (clean_id, clean_org)
            )
            conn.commit()
            return cursor.rowcount > 0
