"""
JWT and Password Hashing Security Provider.
Pure standard-library implementation (HMAC-SHA256 + PBKDF2) for maximum reliability,
zero dependency risks, and standard HS256 JWT interoperability.
"""

import os
import hmac
import hashlib
import base64
import json
import logging
import time
import secrets
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

MIN_SECRET_LENGTH = 32
_DEV_SECRET: Optional[bytes] = None


def dev_mode_enabled() -> bool:
    return os.getenv("PLATFORM_DEV_MODE", "").strip().lower() in ("1", "true")


def _get_jwt_secret() -> bytes:
    """JWT_SECRET_KEY is required. Dev mode uses a random per-process key, never a known one."""
    global _DEV_SECRET
    key = os.getenv("JWT_SECRET_KEY", "").strip()
    if len(key) >= MIN_SECRET_LENGTH:
        return key.encode("utf-8")
    if dev_mode_enabled():
        if _DEV_SECRET is None:
            logger.warning("JWT_SECRET_KEY is unset or short; PLATFORM_DEV_MODE uses a random key. "
                           "Tokens stop working on restart and across worker processes.")
            _DEV_SECRET = secrets.token_bytes(32)
        return _DEV_SECRET
    raise RuntimeError(f"JWT_SECRET_KEY must be set to at least {MIN_SECRET_LENGTH} characters "
                       "(or set PLATFORM_DEV_MODE=1 for local development).")


def validate_token_configuration() -> None:
    """Fail application startup instead of signing tokens with a missing or weak secret."""
    _get_jwt_secret()


def _b64url_encode(data: bytes) -> str:
    """Encode bytes to Base64URL string without padding."""
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('ascii')


def _b64url_decode(s: str) -> bytes:
    """Decode Base64URL string with proper padding."""
    rem = len(s) % 4
    if rem > 0:
        s += '=' * (4 - rem)
    return base64.urlsafe_b64decode(s.encode('ascii'))


def create_access_token(payload: Dict[str, Any], expires_in_seconds: int = 86400) -> str:
    """
    Create a signed HS256 JWT token.
    Default expiry: 24 hours.
    """
    header = {"alg": "HS256", "typ": "JWT"}
    now = int(time.time())

    full_payload = dict(payload)
    if "iat" not in full_payload:
        full_payload["iat"] = now
    if "exp" not in full_payload:
        full_payload["exp"] = now + expires_in_seconds

    header_b64 = _b64url_encode(json.dumps(header, separators=(',', ':')).encode('utf-8'))
    payload_b64 = _b64url_encode(json.dumps(full_payload, separators=(',', ':')).encode('utf-8'))

    signing_input = f"{header_b64}.{payload_b64}".encode('ascii')
    signature = hmac.new(_get_jwt_secret(), signing_input, hashlib.sha256).digest()
    sig_b64 = _b64url_encode(signature)

    return f"{header_b64}.{payload_b64}.{sig_b64}"


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decode and verify a signed HS256 JWT token.
    Returns None if signature is invalid or token is expired.
    """
    parts = token.split('.')
    if len(parts) != 3:
        return None

    header_b64, payload_b64, sig_b64 = parts

    try:
        signing_input = f"{header_b64}.{payload_b64}".encode('ascii')
        actual_sig = _b64url_decode(sig_b64)
        header = json.loads(_b64url_decode(header_b64).decode('utf-8'))
    except (ValueError, UnicodeError):
        return None  # Malformed token: reject instead of raising a 500.
    if not isinstance(header, dict) or header.get("alg") != "HS256":
        return None
    expected_sig = hmac.new(_get_jwt_secret(), signing_input, hashlib.sha256).digest()

    if not hmac.compare_digest(expected_sig, actual_sig):
        return None

    try:
        payload_bytes = _b64url_decode(payload_b64)
        payload = json.loads(payload_bytes.decode('utf-8'))
    except Exception:
        return None

    if not isinstance(payload, dict):
        return None
    # Tokens without a numeric expiry are rejected rather than treated as eternal.
    exp = payload.get("exp")
    if isinstance(exp, bool) or not isinstance(exp, (int, float)) or int(time.time()) > exp:
        return None

    return payload


def hash_password(password: str) -> str:
    """Hash password using PBKDF2-HMAC-SHA256 with 100,000 iterations."""
    salt = secrets.token_bytes(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
    salt_b64 = base64.b64encode(salt).decode("ascii")
    key_b64 = base64.b64encode(key).decode("ascii")
    return f"pbkdf2_sha256$100000${salt_b64}${key_b64}"


def verify_password(password: str, hashed_str: str) -> bool:
    """Verify password against pbkdf2_sha256 hash."""
    try:
        parts = hashed_str.split("$")
        if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
            return False
        iterations = int(parts[1])
        salt = base64.b64decode(parts[2].encode("ascii"))
        expected_key = base64.b64decode(parts[3].encode("ascii"))
        computed_key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(expected_key, computed_key)
    except Exception:
        return False
