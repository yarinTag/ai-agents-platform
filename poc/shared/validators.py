"""
Shared Validators & Normalization Utilities.
Centralizes reusable domain validation, email normalization, slug generation,
and tool-list parsing used across persistence, governance, and API routers.
"""

import json
import re
from typing import List, Optional, Tuple, Union


def normalize_email(email: str) -> str:
    """Normalize an email address to lowercase and trimmed format."""
    if not email:
        return ""
    return email.strip().lower()


def validate_email_domain(email: str, allowed_domain: Optional[str]) -> bool:
    """
    Validate that an email belongs to the organization's allowed corporate domain.
    Returns True if no domain restriction is set or if email matches @domain / .domain.
    """
    if not allowed_domain or not allowed_domain.strip():
        return True
    clean_email = normalize_email(email)
    clean_domain = allowed_domain.strip().lower().lstrip("@")
    return clean_email.endswith(f"@{clean_domain}") or clean_email.endswith(f".{clean_domain}")


def parse_allowed_tools(allowed_tools: Union[str, List[str], None]) -> Tuple[str, List[str]]:
    """
    Normalize and parse an MCP allowed_tools specification into:
    1. Storage string ('*' or JSON array string)
    2. Parsed Python list of tool names (['*'] or ['tool_a', 'tool_b'])
    """
    if allowed_tools is None:
        return "*", ["*"]

    if isinstance(allowed_tools, list):
        cleaned = [str(t).strip() for t in allowed_tools if str(t).strip()]
        if not cleaned or "*" in cleaned:
            return "*", ["*"]
        return json.dumps(cleaned), cleaned

    raw = str(allowed_tools).strip()
    if not raw or raw == "*":
        return "*", ["*"]

    if raw.startswith("["):
        try:
            parsed = [str(t).strip() for t in json.loads(raw) if str(t).strip()]
            if "*" in parsed:
                return "*", ["*"]
            return json.dumps(parsed), parsed
        except Exception:
            pass

    parsed_csv = [t.strip() for t in raw.split(",") if t.strip()]
    if not parsed_csv or "*" in parsed_csv:
        return "*", ["*"]
    return json.dumps(parsed_csv), parsed_csv


def slugify_identifier(text: str) -> str:
    """Convert arbitrary text to a clean lowercase URL/identifier slug."""
    if not text:
        return ""
    s = text.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_]+", "-", s)
    return s.strip("-")
