"""
Safe text construction for outbound channel notifications.

Workflow names, step names and step outputs are untrusted (they can contain LLM output or
attacker-controlled content), so everything interpolated into a message is redacted, stripped of
control characters, defused against broadcast mentions and Slack link/mention markup, and bounded.
Ordinary markdown/code is left intact (code-review summaries need it).
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional

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


def format_glanceable_summary(
    workflow_name: str,
    execution_id: str,
    status: str,
    trigger_type: Optional[str] = None,
    total_tokens: int = 0,
    total_cost_usd: float = 0.0,
    step_outputs: Optional[Dict[str, str]] = None,
    failure_error: Optional[str] = None,
    max_bullets: int = 4,
    limit: int = 1500,
) -> str:
    """Construct an executive, glanceable summary of a workflow run for Telegram / Slack.

    Produces a high-signal notification readable in seconds:
    - Status emoji + clean workflow title
    - Execution metadata (ID, trigger, tokens, cost)
    - 3-5 concise bullet points or clean executive findings
    - Clean error reporting on failure
    """
    norm_status = (status or "UNKNOWN").upper()
    icons = {"COMPLETED": "✅", "FAILED": "❌", "RUNNING": "🚀", "CANCELLED": "⏹️"}
    icon = icons.get(norm_status, "ℹ️")

    safe_name = sanitize_notification_text(workflow_name, 200)
    lines: list[str] = [f"{icon} *Workflow: {safe_name}* — *{norm_status}*"]

    meta_parts: list[str] = []
    if execution_id:
        meta_parts.append(f"Run: `{execution_id}`")
    if trigger_type:
        meta_parts.append(f"Trigger: `{sanitize_notification_text(trigger_type, 30)}`")
    if total_tokens > 0 or total_cost_usd > 0:
        meta_parts.append(f"Tokens: {total_tokens} (${total_cost_usd:.4f})")
    if meta_parts:
        lines.append("• " + " | ".join(meta_parts))

    last_output = ""
    if step_outputs:
        last_output = list(step_outputs.values())[-1] or ""

    bullets: list[str] = []
    if last_output:
        parsed_dict = None
        try:
            from workflows.prompt_contracts import parse_structured_output
        except ImportError:
            try:
                from poc.workflows.prompt_contracts import parse_structured_output
            except ImportError:
                parse_structured_output = None

        if parse_structured_output:
            _, parsed_dict = parse_structured_output(last_output)

        if isinstance(parsed_dict, dict):
            summary_val = parsed_dict.get("summary") or parsed_dict.get("message")
            if summary_val:
                bullets.append(f"*Summary:* {str(summary_val).strip()}")
            verdict_val = parsed_dict.get("verdict") or parsed_dict.get("status")
            if verdict_val and str(verdict_val).upper() != norm_status:
                bullets.append(f"*Verdict:* {str(verdict_val).strip()}")
            raw_items = parsed_dict.get("bullets") or parsed_dict.get("key_findings") or parsed_dict.get("action_items")
            if isinstance(raw_items, list):
                for item in raw_items[:max_bullets]:
                    bullets.append(f"• {str(item).strip()}")
        else:
            raw_lines = [ln.strip() for ln in last_output.splitlines() if ln.strip()]
            list_lines = [ln for ln in raw_lines if re.match(r"^[-*•\d\.]+\s+", ln)]
            if list_lines:
                for ln in list_lines[:max_bullets]:
                    clean_ln = re.sub(r"^[-*•\d\.]+\s*", "", ln).strip()
                    bullets.append(f"• {clean_ln}")
            elif raw_lines:
                first_chunk = " ".join(raw_lines[:3])
                if len(first_chunk) > 300:
                    first_chunk = first_chunk[:297] + "..."
                bullets.append(first_chunk)

    if bullets:
        lines.append("\n📋 *Glanceable Summary:*")
        lines.extend(bullets[: max_bullets + 2])

    if failure_error:
        lines.append(f"\n❌ *Failure Reason:* {sanitize_notification_text(failure_error, 400)}")

    full_text = "\n".join(lines)
    return sanitize_notification_text(full_text, limit=limit)

