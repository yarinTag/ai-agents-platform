"""Provider event summaries and API progress snapshots."""

from datetime import datetime
from typing import Any, Dict, Optional
from .models import AgentRun

def summarize_runtime_event(event: Optional[Dict[str, Any]]) -> Optional[str]:
    """Human-readable one-liner for the latest Claude stream-json event."""
    if not event:
        return None
    event_type = event.get("type", "event")
    if event_type == 'usage':
        return f"Model usage: {event.get('input_tokens', 0)} input / {event.get('output_tokens', 0)} output tokens"
    if event_type == 'reasoning_summary':
        content = (event.get('content') or '').strip()
        return ('Reasoning summary: ' + content[:120]) if content else 'Provider did not return a reasoning summary'
    if event_type == "assistant":
        msg = event.get("message", {})
        content = msg.get("content", []) if isinstance(msg, dict) else []
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("type") == "tool_use":
                    return f"Using tool: {item.get('name', 'unknown')}"
                if isinstance(item, dict) and item.get("type") == "text":
                    text = (item.get("text") or "").strip()
                    if text:
                        return text[:120] + ("..." if len(text) > 120 else "")
        return "Assistant response"
    if event_type == "tool_use":
        return f"Using tool: {event.get('name', 'unknown')}"
    if event_type == "tool_result":
        return "Tool result received"
    if event_type == "result":
        result = (event.get("result") or "").strip()
        return result[:120] + ("..." if len(result) > 120 else "") if result else "Task finished"
    if event_type == "error":
        err = event.get("error", {})
        return f"Error: {err.get('message', 'unknown')}" if isinstance(err, dict) else "Error"
    if event_type == "raw":
        content = (event.get("content") or "").strip()
        return content[:80] + ("..." if len(content) > 80 else "") if content else "Raw output"
    return event_type.replace("_", " ").title()


def build_task_progress_payload(run: "AgentRun") -> Dict[str, Any]:
    """Compact progress snapshot for API responses and SSE events."""
    events = run.events or []
    last = events[-1] if events else None
    elapsed = None
    if run.started_at:
        end = run.ended_at or datetime.now()
        elapsed = max(0, int((end - run.started_at).total_seconds()))
    type_counts: Dict[str, int] = {}
    for ev in events:
        t = ev.get("type", "unknown")
        type_counts[t] = type_counts.get(t, 0) + 1
    return {
        "run_id": run.run_id,
        "agent_id": run.agent_id,
        "project_id": run.project_id,
        "status": run.status.value if hasattr(run.status, "value") else str(run.status),
        "event_count": len(events),
        "event_types": type_counts,
        "last_event_type": last.get("type") if last else None,
        "last_event_summary": summarize_runtime_event(last),
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "elapsed_seconds": elapsed,
        "session_id": run.session_id,
        "result_preview": (run.result[:160] + "...") if run.result and len(run.result) > 160 else run.result,
    }
