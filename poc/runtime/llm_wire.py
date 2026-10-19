"""
Provider wire-format helpers and per-model pricing for `DirectHTTPLLMRuntimeAdapter`.

Kept separate so the adapter stays focused on the control flow (auth -> meter -> call -> gate tools).
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

# USD per 1M tokens: (input, output). Unknown models fall back to the conservative default.
MODEL_PRICING_PER_MTOK: Dict[str, Tuple[float, float]] = {
    "claude-3-5-sonnet-latest": (3.0, 15.0), "claude-3-5-sonnet-20241022": (3.0, 15.0),
    "claude-3-7-sonnet-latest": (3.0, 15.0), "claude-sonnet-4-20250514": (3.0, 15.0),
    "claude-3-5-haiku-latest": (0.8, 4.0),
    "gpt-4o": (2.5, 10.0), "gpt-4o-mini": (0.15, 0.6), "gpt-4.1": (2.0, 8.0), "gpt-4.1-mini": (0.4, 1.6),
    "meta/llama-3.1-70b-instruct": (0.35, 0.4), "meta/llama-3.1-8b-instruct": (0.05, 0.08),
    "meta/llama-3.3-70b-instruct": (0.35, 0.4), "nvidia/llama-3.1-nemotron-70b-instruct": (0.35, 0.4),
}
DEFAULT_PRICING_PER_MTOK: Tuple[float, float] = (5.0, 20.0)  # conservative: over-estimate, never under


def compute_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    """Actual USD cost for token usage using the per-model table (conservative default if unknown)."""
    p_in, p_out = MODEL_PRICING_PER_MTOK.get((model or "").lower(), DEFAULT_PRICING_PER_MTOK)
    return round((input_tokens * p_in + output_tokens * p_out) / 1_000_000, 6)


def format_tools(
    provider: str, tools: Optional[List[Dict[str, Any]]]
) -> Tuple[List[Dict[str, Any]], Dict[str, Tuple[str, str]]]:
    """Format tool definitions for Anthropic vs OpenAI/NVIDIA and build a name -> (connector, tool) map."""
    if not tools:
        return [], {}
    formatted: List[Dict[str, Any]] = []
    tool_map: Dict[str, Tuple[str, str]] = {}
    for t in tools:
        fn = t.get("function", t)
        raw_name = str(fn.get("name") or t.get("tool_name") or "").strip()
        conn_id = str(t.get("connector_id") or fn.get("connector_id") or "").strip().lower()
        if not conn_id and "." in raw_name:
            conn_id, short_name = raw_name.split(".", 1)
        elif not conn_id and "__" in raw_name:
            conn_id, short_name = raw_name.split("__", 1)
        else:
            short_name, conn_id = raw_name, (conn_id or "default")
        api_name = (
            f"{conn_id}__{short_name}"
            if "." not in raw_name and "__" not in raw_name and t.get("connector_id")
            else raw_name
        )
        for key in (api_name, raw_name, short_name, f"{conn_id}.{short_name}"):
            tool_map[key] = (conn_id, short_name)
        desc = str(fn.get("description") or f"Execute {conn_id}.{short_name}")
        schema = fn.get("parameters") or fn.get("input_schema") or {"type": "object", "properties": {}}
        if provider == "anthropic":
            formatted.append({"name": api_name, "description": desc, "input_schema": schema})
        else:
            formatted.append({"type": "function", "function": {"name": api_name, "description": desc, "parameters": schema}})
    return formatted, tool_map


def parse_tool_identity(
    call_item: Dict[str, Any], raw_name: str, tool_map: Dict[str, Tuple[str, str]]
) -> Tuple[str, str]:
    """Resolve `(connector_id, tool_name)` from a model tool invocation."""
    explicit_conn = str(call_item.get("connector_id") or "").strip().lower()
    if explicit_conn:
        return explicit_conn, raw_name.split(".", 1)[-1].split("__", 1)[-1]
    if raw_name in tool_map:
        return tool_map[raw_name]
    for sep in (".", "__"):
        if sep in raw_name:
            c, n = raw_name.split(sep, 1)
            return c.strip().lower(), n.strip()
    return "default", raw_name.strip()


def parse_tool_arguments(raw_val: Any) -> Tuple[Dict[str, Any], Optional[str]]:
    """Parse model-produced tool arguments; returns `(args, error)` instead of raising on bad JSON."""
    if isinstance(raw_val, dict):
        return raw_val, None
    if raw_val is None or (isinstance(raw_val, str) and not raw_val.strip()):
        return {}, None
    try:
        parsed = json.loads(raw_val) if isinstance(raw_val, str) else None
    except (ValueError, TypeError):
        return {}, "tool arguments are not valid JSON"
    if not isinstance(parsed, dict):
        return {}, "tool arguments must be a JSON object"
    return parsed, None
