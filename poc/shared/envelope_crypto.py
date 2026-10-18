"""
Per-tenant Envelope Encryption for secrets at rest and invite token hashing.

Provides AES-256-GCM authenticated encryption (with a zero-dependency standard
library CTR + HMAC-SHA256 Encrypt-then-MAC fallback) and per-organization
Data Encryption Key (DEK) derivation/wrapping under a rotatable Master Key.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
from typing import Any, Dict, Optional

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # type: ignore
    _HAS_AESGCM = True
except ImportError:  # pragma: no cover
    AESGCM = None  # type: ignore
    _HAS_AESGCM = False

_DEV_FALLBACK_MASTER_SEED = b"dev-only-platform-kms-master-seed-do-not-use-in-prod"
_NONCE_BYTES = 12
_TAG_BYTES = 32


def _is_production() -> bool:
    """Return True when running in a production environment."""
    return os.getenv("ENV", os.getenv("PLATFORM_ENV", "dev")).strip().lower() in ("prod", "production")


def _normalize_key_bytes(raw_key: str | bytes) -> bytes:
    """Normalize arbitrary key material into a 256-bit (32-byte) key."""
    if isinstance(raw_key, str):
        raw_bytes = raw_key.encode("utf-8")
    elif isinstance(raw_key, (bytes, bytearray)):
        raw_bytes = bytes(raw_key)
    else:
        raise TypeError("Key material must be str or bytes")
    if not raw_bytes:
        raise ValueError("Key material must not be empty")
    return hashlib.sha256(raw_bytes).digest()


def _ctr_keystream(enc_key: bytes, nonce: bytes, length: int) -> bytes:
    """Generate a pseudo-random keystream using HMAC-SHA256 in counter mode."""
    blocks, counter, produced = [], 0, 0
    while produced < length:
        block = hmac.new(enc_key, nonce + counter.to_bytes(8, "big"), hashlib.sha256).digest()
        blocks.append(block)
        produced += len(block)
        counter += 1
    return b"".join(blocks)[:length]


def _stdlib_aead_encrypt(dek: bytes, nonce: bytes, plaintext: bytes, aad: bytes) -> bytes:
    """Authenticated Encrypt-then-MAC using HMAC-SHA256 CTR stream + HMAC tag."""
    enc_key = hmac.new(dek, b"enc", hashlib.sha256).digest()
    mac_key = hmac.new(dek, b"mac", hashlib.sha256).digest()
    stream = _ctr_keystream(enc_key, nonce, len(plaintext))
    ciphertext = bytes(a ^ b for a, b in zip(plaintext, stream))
    tag = hmac.new(mac_key, aad + nonce + ciphertext, hashlib.sha256).digest()
    return ciphertext + tag


def _stdlib_aead_decrypt(dek: bytes, nonce: bytes, data: bytes, aad: bytes) -> bytes:
    """Verify HMAC-SHA256 tag in constant time and decrypt CTR stream."""
    if len(data) < _TAG_BYTES:
        raise ValueError("Ciphertext truncated or missing authentication tag")
    ciphertext, provided_tag = data[:-_TAG_BYTES], data[-_TAG_BYTES:]
    enc_key = hmac.new(dek, b"enc", hashlib.sha256).digest()
    mac_key = hmac.new(dek, b"mac", hashlib.sha256).digest()
    expected_tag = hmac.new(mac_key, aad + nonce + ciphertext, hashlib.sha256).digest()
    if not hmac.compare_digest(provided_tag, expected_tag):
        raise ValueError("AEAD authentication tag verification failed")
    stream = _ctr_keystream(enc_key, nonce, len(ciphertext))
    return bytes(a ^ b for a, b in zip(ciphertext, stream))


def _aead_encrypt(dek: bytes, nonce: bytes, plaintext: bytes, aad: bytes) -> bytes:
    """Encrypt and authenticate bytes using AES-GCM or stdlib AEAD fallback."""
    if _HAS_AESGCM and AESGCM is not None:
        return AESGCM(dek).encrypt(nonce, plaintext, aad)
    return _stdlib_aead_encrypt(dek, nonce, plaintext, aad)


def _aead_decrypt(dek: bytes, nonce: bytes, ciphertext: bytes, aad: bytes) -> bytes:
    """Authenticate and decrypt bytes using AES-GCM or stdlib AEAD fallback."""
    if _HAS_AESGCM and AESGCM is not None:
        try:
            return AESGCM(dek).decrypt(nonce, ciphertext, aad)
        except Exception as exc:
            raise ValueError("AES-GCM authentication failed") from exc
    return _stdlib_aead_decrypt(dek, nonce, ciphertext, aad)


class EnvelopeCryptoManager:
    """Per-tenant Envelope Encryption manager supporting master key rotation."""

    def __init__(
        self,
        master_key: Optional[str | bytes] = None,
        key_id: Optional[str] = None,
    ) -> None:
        env_key = os.getenv("PLATFORM_KMS_MASTER_KEY", "").strip()
        effective_raw: Optional[str | bytes] = master_key if master_key is not None else (env_key or None)
        if effective_raw is None:
            if _is_production():
                raise RuntimeError(
                    "Fail-closed: PLATFORM_KMS_MASTER_KEY environment variable is required in production"
                )
            effective_raw = _DEV_FALLBACK_MASTER_SEED

        initial_key_id = (key_id or os.getenv("PLATFORM_KMS_KEY_ID", "v1")).strip() or "v1"
        self._master_keys: Dict[str, bytes] = {initial_key_id: _normalize_key_bytes(effective_raw)}
        self._current_key_id: str = initial_key_id

    @property
    def current_key_id(self) -> str:
        """Return the active master key version identifier."""
        return self._current_key_id

    def rotate_master_key(self, new_master_key: str | bytes, new_key_id: Optional[str] = None) -> str:
        """Rotate to a new Master Key while retaining previous keys for decryption."""
        normalized = _normalize_key_bytes(new_master_key)
        target_id = (new_key_id or f"v{len(self._master_keys) + 1}").strip()
        if not target_id:
            raise ValueError("new_key_id must not be empty")
        self._master_keys[target_id] = normalized
        self._current_key_id = target_id
        return self._current_key_id

    def derive_org_dek(self, org_id: str, key_id: Optional[str] = None) -> bytes:
        """Derive a tenant-specific 256-bit DEK bound to `org_id` and `key_id`."""
        clean_org = (org_id or "").strip()
        if not clean_org:
            raise ValueError("org_id must be a non-empty string")
        target_key_id = key_id or self._current_key_id
        if target_key_id not in self._master_keys:
            raise ValueError(f"Unknown master key_id: {target_key_id}")
        context = f"envelope-dek:{target_key_id}:{clean_org}".encode("utf-8")
        return hmac.new(self._master_keys[target_key_id], context, hashlib.sha256).digest()

    def wrap_dek(self, dek: bytes, org_id: str, key_id: Optional[str] = None) -> str:
        """Wrap an explicit DEK under the tenant KEK using AEAD."""
        target_key_id = key_id or self._current_key_id
        kek = self.derive_org_dek(org_id=org_id, key_id=target_key_id)
        nonce = secrets.token_bytes(_NONCE_BYTES)
        ct = _aead_encrypt(kek, nonce, dek, f"wrap:{target_key_id}:{org_id}".encode("utf-8"))
        return base64.b64encode(nonce + ct).decode("ascii")

    def unwrap_dek(self, wrapped_dek: str, org_id: str, key_id: str) -> bytes:
        """Unwrap a previously wrapped DEK under the tenant KEK."""
        kek = self.derive_org_dek(org_id=org_id, key_id=key_id)
        raw = base64.b64decode(wrapped_dek.encode("ascii"))
        return _aead_decrypt(kek, raw[:_NONCE_BYTES], raw[_NONCE_BYTES:], f"wrap:{key_id}:{org_id}".encode("utf-8"))

    def encrypt_config(self, config_dict: Dict[str, Any], org_id: str = "global") -> Dict[str, Any]:
        """Encrypt a configuration dictionary for a specific tenant `org_id`."""
        if not isinstance(config_dict, dict):
            raise TypeError("config_dict must be a dictionary")
        clean_org = (org_id or "").strip()
        if not clean_org:
            raise ValueError("org_id must not be empty")

        key_id = self._current_key_id
        dek = self.derive_org_dek(org_id=clean_org, key_id=key_id)
        nonce = secrets.token_bytes(_NONCE_BYTES)
        aad = f"{key_id}:{clean_org}".encode("utf-8")
        plaintext = json.dumps(config_dict, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ciphertext = _aead_encrypt(dek, nonce, plaintext, aad)
        return {
            "__encrypted__": True,
            "key_id": key_id,
            "org_id": clean_org,
            "nonce": base64.b64encode(nonce).decode("ascii"),
            "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
        }

    def decrypt_config(self, stored_dict: Dict[str, Any], org_id: str = "global") -> Dict[str, Any]:
        """Authenticate and decrypt an encrypted configuration dictionary."""
        if not isinstance(stored_dict, dict) or stored_dict.get("__encrypted__") is not True:
            raise ValueError("Invalid or unencrypted secret envelope")

        clean_org = (org_id or "").strip()
        envelope_org = stored_dict.get("org_id")
        key_id = stored_dict.get("key_id")
        nonce_b64 = stored_dict.get("nonce")
        ciphertext_b64 = stored_dict.get("ciphertext")
        if not clean_org or not envelope_org or not key_id or not nonce_b64 or not ciphertext_b64:
            raise ValueError("Malformed encrypted envelope: missing required fields")
        if envelope_org != clean_org:
            raise ValueError(f"Tenant isolation violation: '{envelope_org}' != '{clean_org}'")

        dek = self.derive_org_dek(org_id=clean_org, key_id=key_id)
        nonce = base64.b64decode(nonce_b64.encode("ascii"))
        ciphertext = base64.b64decode(ciphertext_b64.encode("ascii"))
        plaintext = _aead_decrypt(dek, nonce, ciphertext, f"{key_id}:{clean_org}".encode("utf-8"))
        decoded = json.loads(plaintext.decode("utf-8"))
        if not isinstance(decoded, dict):
            raise ValueError("Decrypted secret payload is not a JSON object")
        return decoded

    def reencrypt_config(self, stored_dict: Dict[str, Any], org_id: str = "global") -> Dict[str, Any]:
        """Decrypt with historical `key_id` and re-encrypt under `current_key_id`."""
        return self.encrypt_config(self.decrypt_config(stored_dict, org_id=org_id), org_id=org_id)

    encrypt_secret_config = encrypt_config
    decrypt_secret_config = decrypt_config


_DEFAULT_MANAGER: Optional[EnvelopeCryptoManager] = None
_DEFAULT_ENV_SNAPSHOT: Optional[tuple[str, str, str]] = None


def _get_default_manager() -> EnvelopeCryptoManager:
    """Return or initialize the default module-level crypto manager, refreshing on env change."""
    global _DEFAULT_MANAGER, _DEFAULT_ENV_SNAPSHOT
    snapshot = (os.getenv("ENV", ""), os.getenv("PLATFORM_ENV", ""), os.getenv("PLATFORM_KMS_MASTER_KEY", ""))
    if _DEFAULT_MANAGER is None or _DEFAULT_ENV_SNAPSHOT != snapshot:
        _DEFAULT_MANAGER = EnvelopeCryptoManager()
        _DEFAULT_ENV_SNAPSHOT = snapshot
    return _DEFAULT_MANAGER


def encrypt_secret_config(config_dict: Dict[str, Any], org_id: str = "global") -> Dict[str, Any]:
    """Encrypt a secret configuration dictionary using per-tenant envelope encryption."""
    return _get_default_manager().encrypt_config(config_dict, org_id=org_id)


def decrypt_secret_config(stored_dict: Dict[str, Any], org_id: str = "global") -> Dict[str, Any]:
    """Decrypt a secret configuration dictionary using per-tenant envelope encryption."""
    return _get_default_manager().decrypt_config(stored_dict, org_id=org_id)


def hash_invite_token(raw_token: str) -> str:
    """Hash an invitation token using SHA-256 so raw tokens are never stored at rest."""
    if not isinstance(raw_token, str) or not raw_token.strip():
        raise ValueError("Invitation token must be a non-empty string")
    return hashlib.sha256(raw_token.strip().encode("utf-8")).hexdigest()
