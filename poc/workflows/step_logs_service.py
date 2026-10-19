"""
Step-Level Log Correlation Service for Workflow Executions.
Correlates `workflow_step_runs` with `event_log`, `mcp_tool_calls`, and `audit_logs`
so every individual workflow step has full observability and security audit trails.

Each source table is queried once per execution (not once per step) and rows are then
attributed to steps in memory.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


def _parse_json_safe(raw_value: Any) -> Any:
    """Parse a JSON string into a Python object if possible, otherwise return the original value."""
    if not isinstance(raw_value, str) or not raw_value.strip():
        return raw_value
    try:
        return json.loads(raw_value)
    except Exception:
        return raw_value


def _extract_audit_step_key(details_obj: Any) -> Optional[str]:
    """Extract step_key from parsed audit_logs.details if present."""
    if not isinstance(details_obj, dict):
        return None
    direct_key = details_obj.get("step_key")
    if direct_key:
        return str(direct_key)
    meta = details_obj.get("metadata")
    if isinstance(meta, dict) and meta.get("step_key"):
        return str(meta.get("step_key"))
    return None


def _belongs_to_step(row_task_id: Optional[str], step_task_id: Optional[str], all_task_ids: Set[str]) -> bool:
    """A row belongs to a step if tagged with its task id, or is run-level (not tagged with another step's task)."""
    return row_task_id == step_task_id if row_task_id in all_task_ids else True


def _escape_like(value: str) -> str:
    """Escape LIKE wildcards so ids are matched literally."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _task_id_clause(column: str, task_ids: Set[str]) -> tuple[str, list]:
    """Build an `OR column IN (...)` clause for the given task ids (empty if none)."""
    if not task_ids:
        return "", []
    return f" OR {column} IN ({','.join('?' * len(task_ids))})", sorted(task_ids)


def _fetch_events(conn: Any, execution_id: str, task_ids: Set[str]) -> List[Dict[str, Any]]:
    """All event_log rows for the execution or any of its step tasks, in order."""
    extra, params = _task_id_clause("task_id", task_ids)
    rows = conn.execute(
        f"SELECT * FROM event_log WHERE execution_id = ?{extra} ORDER BY sequence_number ASC, timestamp ASC",
        [execution_id, *params],
    ).fetchall()
    events = [dict(r) for r in rows]
    for item in events:
        item["payload"] = _parse_json_safe(item.get("payload"))
    return events


def _fetch_mcp_calls(conn: Any, execution_id: str, task_ids: Set[str]) -> List[Dict[str, Any]]:
    """All mcp_tool_calls rows for the execution (run_id) or any of its step tasks, in order."""
    extra, params = _task_id_clause("task_id", task_ids)
    rows = conn.execute(
        f"SELECT * FROM mcp_tool_calls WHERE run_id = ?{extra} ORDER BY started_at ASC",
        [execution_id, *params],
    ).fetchall()
    calls = [dict(r) for r in rows]
    for item in calls:
        item["arguments"] = _parse_json_safe(item.get("arguments"))
    return calls


def _fetch_security_audits(conn: Any, execution_id: str) -> List[Dict[str, Any]]:
    """audit_logs whose correlation_id is exactly `<org>:<execution_id>` (or the bare id), wildcards escaped."""
    esc = _escape_like(execution_id)
    rows = conn.execute(
        "SELECT * FROM audit_logs WHERE correlation_id = ? OR correlation_id LIKE ? ESCAPE '\\' "
        "ORDER BY timestamp ASC",
        (execution_id, f"%:{esc}"),
    ).fetchall()
    audits = [dict(r) for r in rows]
    for item in audits:
        item["details"] = _parse_json_safe(item.get("details"))
    return audits


def get_execution_step_logs(
    db: Any,
    execution_id: str,
    step_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Retrieve step-level execution records and correlated events, MCP tool calls,
    and security audit logs for a given workflow execution.
    """
    if not execution_id or not str(execution_id).strip():
        raise ValueError("execution_id is required")

    with db._get_connection() as conn:
        all_step_rows = conn.execute(
            "SELECT * FROM workflow_step_runs WHERE execution_id = ? ORDER BY started_at ASC, rowid ASC",
            (execution_id,),
        ).fetchall()
        all_task_ids: Set[str] = {str(r["task_run_id"]) for r in all_step_rows if r["task_run_id"]}
        step_rows = [r for r in all_step_rows if step_key is None or r["step_key"] == step_key]

        events = _fetch_events(conn, execution_id, all_task_ids) if step_rows else []
        mcp_calls = _fetch_mcp_calls(conn, execution_id, all_task_ids) if step_rows else []
        audits = _fetch_security_audits(conn, execution_id) if step_rows else []

    try:
        from workflows.prompt_contracts import parse_structured_output
    except ImportError:
        try:
            from poc.workflows.prompt_contracts import parse_structured_output
        except ImportError:
            parse_structured_output = None

    steps: List[Dict[str, Any]] = []
    for row in step_rows:
        d = dict(row)
        s_key = str(d.get("step_key") or "")
        t_id = d.get("task_run_id")
        out_raw = d.get("output_data") or ""
        clean_summary, parsed_struct = "", None
        if parse_structured_output and out_raw:
            clean_summary, parsed_struct = parse_structured_output(out_raw)

        steps.append({
            "id": d.get("id"),
            "step_key": s_key,
            "agent_id": d.get("agent_id"),
            "status": d.get("status") or "PENDING",
            "task_run_id": t_id,
            "input_data": d.get("input_data"),
            "output_data": d.get("output_data"),
            "output_summary": clean_summary or (out_raw[:300] if out_raw else ""),
            "structured_output": parsed_struct,
            "input_tokens": int(d.get("input_tokens") or 0),
            "output_tokens": int(d.get("output_tokens") or 0),
            "cost_usd": float(d.get("cost_usd") or 0.0),
            "started_at": d.get("started_at"),
            "completed_at": d.get("completed_at"),
            "error_message": d.get("error_message"),
            "events": [e for e in events if _belongs_to_step(e.get("task_id"), t_id, all_task_ids)],
            "mcp_tool_calls": [c for c in mcp_calls if _belongs_to_step(c.get("task_id"), t_id, all_task_ids)],
            "security_audit_logs": [
                a for a in audits
                if _extract_audit_step_key(a["details"]) in (None, s_key)
            ],
        })

    return {
        "execution_id": execution_id,
        "total_steps": len(steps),
        "steps": steps,
    }
