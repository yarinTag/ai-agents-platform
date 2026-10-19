"""
Prompt Contracts, Granular Path Substitution, and Structured Output Enforcement.

Optimizes prompts across workflow steps:
1. Granular JSON path resolution (e.g., `{{review_step.summary}}` instead of ingesting 4,000 tokens of raw prose).
2. Strict output contracts (`[OUTPUT CONTRACT]`) for deterministic, machine-readable step outputs.
3. Few-shot output parsing and extraction from markdown-fenced responses.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional, Tuple

_PATH_PATTERN = re.compile(r"\{\{([a-zA-Z0-9_\-\.]+)\}\}|\$\{([a-zA-Z0-9_\-\.]+)\}")


def _resolve_nested_value(data: Any, path: str) -> Optional[Any]:
    """Resolve a dot-separated path within a nested dict/list structure."""
    current = data
    parts = path.split(".")
    for part in parts:
        if isinstance(current, dict):
            if part in current:
                current = current[part]
            else:
                return None
        elif isinstance(current, (list, tuple)) and part.isdigit():
            idx = int(part)
            if 0 <= idx < len(current):
                current = current[idx]
            else:
                return None
        else:
            return None
    return current


def parse_structured_output(raw_output: str) -> Tuple[str, Optional[Dict[str, Any]]]:
    """
    Extract structured JSON from step output if present.
    Returns `(clean_text, parsed_json_dict)`.
    """
    if not raw_output or not isinstance(raw_output, str):
        return "", None

    trimmed = raw_output.strip()
    # 1. Direct JSON parse
    if (trimmed.startswith("{") and trimmed.endswith("}")) or (trimmed.startswith("[") and trimmed.endswith("]")):
        try:
            parsed = json.loads(trimmed)
            if isinstance(parsed, dict):
                summary = str(parsed.get("summary") or parsed.get("message") or trimmed)
                return summary, parsed
        except Exception:
            pass

    # 2. Extract ```json ... ``` blocks
    fenced_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw_output, re.IGNORECASE)
    if fenced_match:
        fenced_content = fenced_match.group(1).strip()
        try:
            parsed = json.loads(fenced_content)
            if isinstance(parsed, dict):
                summary = str(parsed.get("summary") or parsed.get("message") or raw_output)
                return summary, parsed
        except Exception:
            pass

    return raw_output, None


def render_step_prompt(
    prompt_template: str,
    step_outputs: Dict[str, str],
    trigger_payload: Optional[Dict[str, Any]] = None,
    output_schema: Optional[Dict[str, Any]] = None,
    output_format: Optional[str] = None,
) -> str:
    """
    Render step prompt with granular path resolution and optional output contract.
    Avoids context bloat by enabling downstream steps to reference only needed attributes.
    """
    if not prompt_template:
        return ""

    # Parse any structured outputs from prior steps
    structured_step_data: Dict[str, Any] = {}
    for step_k, out_v in step_outputs.items():
        _, parsed = parse_structured_output(out_v)
        if parsed is not None:
            structured_step_data[step_k] = parsed

    def _replace_match(m: re.Match[str]) -> str:
        key = m.group(1) or m.group(2)
        if not key:
            return m.group(0)

        # 1. Check trigger payload first
        if trigger_payload and key in trigger_payload:
            val = trigger_payload[key]
            return json.dumps(val) if isinstance(val, (dict, list)) else str(val)

        # 2. Check granular trigger_payload paths (e.g. repo.name)
        if trigger_payload and "." in key:
            resolved = _resolve_nested_value(trigger_payload, key)
            if resolved is not None:
                return json.dumps(resolved) if isinstance(resolved, (dict, list)) else str(resolved)

        # 3. Check direct step output (${step_key.output})
        if key.endswith(".output"):
            step_name = key[:-7]
            if step_name in step_outputs:
                return step_outputs[step_name] or ""

        # 4. Check structured granular path (${step_key.field.subfield})
        if "." in key:
            parts = key.split(".", 1)
            step_name, field_path = parts[0], parts[1]
            if step_name in structured_step_data:
                resolved = _resolve_nested_value(structured_step_data[step_name], field_path)
                if resolved is not None:
                    return json.dumps(resolved) if isinstance(resolved, (dict, list)) else str(resolved)

        # 5. Fallback to raw string substitution if matching whole step key
        if key in step_outputs:
            return step_outputs[key] or ""

        return m.group(0)

    rendered = _PATH_PATTERN.sub(_replace_match, prompt_template)

    # 6. Append strict output contract if requested
    fmt_clean = (output_format or "").strip().lower()
    if output_schema:
        schema_str = json.dumps(output_schema, indent=2)
        contract = (
            f"\n\n[OUTPUT CONTRACT]\n"
            f"You MUST respond ONLY with a valid, parseable JSON object matching this schema. "
            f"Do not include conversational filler, markdown formatting, or text outside the JSON:\n"
            f"{schema_str}"
        )
        rendered += contract
    elif fmt_clean == "json":
        contract = (
            f"\n\n[OUTPUT CONTRACT]\n"
            f"You MUST respond ONLY with a valid, parseable JSON object. "
            f"Do not include conversational filler or text outside the JSON."
        )
        rendered += contract

    return rendered
