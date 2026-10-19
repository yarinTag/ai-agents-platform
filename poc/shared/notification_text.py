"""
Safe text construction for outbound channel notifications.

Workflow names, step names and step outputs are untrusted (they can contain LLM output or
attacker-controlled content), so everything interpolated into a message is redacted, stripped of
control characters, defused against broadcast mentions and Slack link/mention markup, and bounded.
Ordinary markdown/code is left intact (code-review summaries need it).
"""

from __future__ import annotations

import re
from typing import Dict

try:
    from shared.redaction import redact_pii_and_secrets
except ImportError:
    from poc.shared.redaction import redact_pii_and_secrets

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_BROADCAST_MENTION = re.compile(r"@(channel|here|everyone|all)\b", re.IGNORECASE)
_TEMPLATE_VAR = re.compile(r"\{\{(workflow_name|status|output)\}\}")
_ZWSP = "\u200b"


def sanitize_notification_text(text: object, limit: int = 1200) -> str:
    """Redact secrets/PII, strip control chars, defuse mentions and markup, and truncate to `limit`."""
    cleaned, _ = redact_pii_and_secrets(str(text if text is not None else ""))
    cleaned = _CONTROL_CHARS.sub("", cleaned)
    cleaned = cleaned.replace("<!", f"<{_ZWSP}!").replace("<@", f"<{_ZWSP}@").replace("<#", f"<{_ZWSP}#")
    cleaned = _BROADCAST_MENTION.sub(lambda m: f"@{_ZWSP}{m.group(1)}", cleaned)
    if len(cleaned) > limit:
        cleaned = cleaned[: max(0, limit - 15)] + "...\n(truncated)"
    return cleaned


def render_template(template: str, values: Dict[str, str]) -> str:
    """Single-pass `{{var}}` substitution so substituted text is never re-expanded as a template."""
    return _TEMPLATE_VAR.sub(lambda m: values.get(m.group(1), ""), template)
