"""
Step-Level Log Correlation Service for Workflow Executions.
Correlates `workflow_step_runs` with `event_log`, `mcp_tool_calls`, and `audit_logs`
so every individual workflow step has full observability and security audit trails.
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


def _fetch_correlated_events(
    conn: Any,
    execution_id: str,
    task_run_id: Optional[str],
    other_task_ids: Set[str],
) -> List[Dict[str, Any]]:
    """Fetch event_log entries matching task_run_id or execution_id."""
    if task_run_id:
        rows = conn.execute(
            """
            SELECT * FROM event_log
            WHERE task_id = ? OR execution_id = ?
            ORDER BY sequence_number ASC, timestamp ASC
            """,
            (task_run_id, execution_id),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT * FROM event_log
            WHERE execution_id = ?
            ORDER BY sequence_number ASC, timestamp ASC
            """,
            (execution_id,),
        ).fetchall()

    events: List[Dict[str, Any]] = []
    for r in rows:
        item = dict(r)
        ev_task_id = item.get("task_id")
        if ev_task_id and ev_task_id in other_task_ids and ev_task_id != task_run_id:
            continue
        item["payload"] = _parse_json_safe(item.get("payload"))
        events.append(item)
    return events


def _fetch_correlated_mcp_calls(
    conn: Any,
    execution_id: str,
    task_run_id: Optional[str],
    other_task_ids: Set[str],
) -> List[Dict[str, Any]]:
    """Fetch mcp_tool_calls entries matching task_run_id or run_id == execution_id."""
    if task_run_id:
        rows = conn.execute(
            """
            SELECT * FROM mcp_tool_calls
            WHERE task_id = ? OR run_id = ?
            ORDER BY started_at ASC
            """,
            (task_run_id, execution_id),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT * FROM mcp_tool_calls
            WHERE run_id = ?
            ORDER BY started_at ASC
            """,
            (execution_id,),
        ).fetchall()

    calls: List[Dict[str, Any]] = []
    for r in rows:
        item = dict(r)
        call_task_id = item.get("task_id")
        if call_task_id and call_task_id in other_task_ids and call_task_id != task_run_id:
            continue
        item["arguments"] = _parse_json_safe(item.get("arguments"))
        calls.append(item)
    return calls


def _fetch_correlated_security_audits(
    conn: Any,
    execution_id: str,
    current_step_key: str,
) -> List[Dict[str, Any]]:
    """
    Fetch audit_logs where correlation_id LIKE '%{execution_id}%' and filter by
    step_key (if present in details JSON) or include run-level events.
    """
    rows = conn.execute(
        """
        SELECT * FROM audit_logs
        WHERE correlation_id LIKE ?
        ORDER BY timestamp ASC
        """,
        (f"%{execution_id}%",),
    ).fetchall()

    audits: List[Dict[str, Any]] = []
    for r in rows:
        item = dict(r)
        parsed_details = _parse_json_safe(item.get("details"))
        log_step_key = _extract_audit_step_key(parsed_details)
        if log_step_key is not None and log_step_key != current_step_key:
            continue
        item["details"] = parsed_details
        audits.append(item)
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
            """
            SELECT * FROM workflow_step_runs
            WHERE execution_id = ?
            ORDER BY started_at ASC, rowid ASC
            """,
            (execution_id,),
        ).fetchall()

        all_task_ids: Set[str] = {
            str(r["task_run_id"])
            for r in all_step_rows
            if r["task_run_id"]
        }

        if step_key is not None:
            step_rows = [r for r in all_step_rows if r["step_key"] == step_key]
        else:
            step_rows = list(all_step_rows)

        steps: List[Dict[str, Any]] = []
        for row in step_rows:
            d = dict(row)
            s_key = str(d.get("step_key") or "")
            t_id = d.get("task_run_id")
            other_task_ids = {tid for tid in all_task_ids if tid != t_id}

            events = _fetch_correlated_events(conn, execution_id, t_id, other_task_ids)
            mcp_calls = _fetch_correlated_mcp_calls(conn, execution_id, t_id, other_task_ids)
            security_logs = _fetch_correlated_security_audits(conn, execution_id, s_key)

            steps.append({
                "id": d.get("id"),
                "step_key": s_key,
                "agent_id": d.get("agent_id"),
                "status": d.get("status") or "PENDING",
                "task_run_id": t_id,
                "input_data": d.get("input_data"),
                "output_data": d.get("output_data"),
                "input_tokens": int(d.get("input_tokens") or 0),
                "output_tokens": int(d.get("output_tokens") or 0),
                "cost_usd": float(d.get("cost_usd") or 0.0),
                "started_at": d.get("started_at"),
                "completed_at": d.get("completed_at"),
                "error_message": d.get("error_message"),
                "events": events,
                "mcp_tool_calls": mcp_calls,
                "security_audit_logs": security_logs,
            })

    return {
        "execution_id": execution_id,
        "total_steps": len(steps),
        "steps": steps,
    }
