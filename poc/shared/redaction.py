"""
Shared PII / credential redaction (single source of truth, Rule of 2).

Used by `gateways.llm_proxy` (prompts leaving the platform) and `shared.notification_text`
(messages leaving to external channels).
"""

from __future__ import annotations

import re
from typing import Tuple

EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
SECRET_TOKEN_PATTERN = re.compile(
    r"\b(?:ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{16,}"
    r"|xox[baprs]-[A-Za-z0-9-]{10,}|rtk_[A-Za-z0-9_-]{16,})\b"
)


def redact_pii_and_secrets(text: str) -> Tuple[str, int]:
    """Redact email addresses and credential tokens. Returns `(sanitized_text, total_redactions)`."""
    if not text:
        return "", 0
    sanitized, emails = EMAIL_PATTERN.subn("[REDACTED_EMAIL]", text)
    sanitized, tokens = SECRET_TOKEN_PATTERN.subn("[REDACTED_TOKEN]", sanitized)
    return sanitized, emails + tokens
