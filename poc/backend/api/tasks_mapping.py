"""Tasks: mapping ownership."""

from datetime import datetime
from ..dependencies import AgentRun


def task_run_to_response(run: AgentRun) -> dict:
    """Convert AgentRun to API response format."""
    return {
        "id": run.run_id,
        "run_id": run.run_id,
        "agent_id": run.agent_id,
        "project_id": run.project_id,
        "organization_id": getattr(run, "organization_id", None),
        "prompt": run.prompt,
        "input_data": {"task": run.prompt, "prompt": run.prompt},
        "output_data": {"result": run.result} if run.result else None,
        "status": run.status.value if hasattr(run.status, "value") else str(run.status),
        "created_at": run.created_at.isoformat() if run.created_at else datetime.now().isoformat(),
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "ended_at": run.ended_at.isoformat() if run.ended_at else None,
        "result": run.result,
        "error": run.error,
        "exit_code": run.exit_code,
        "parent_task_id": getattr(run, "parent_task_id", None),
        "root_task_id": getattr(run, "root_task_id", None),
        "assigned_by": getattr(run, "assigned_by", None),
        "events": getattr(run, "events", None) or [],
        "dependencies": getattr(run, "dependencies", None) or [],
        "structured_result": getattr(run, "structured_result", None),
        "acceptance_criteria": getattr(run, "acceptance_criteria", None),
        "retry_count": getattr(run, "retry_count", 0),
        "input_tokens": getattr(run, "input_tokens", 0) or 0,
        "output_tokens": getattr(run, "output_tokens", 0) or 0,
        "cache_read_tokens": getattr(run, "cache_read_tokens", 0) or 0,
        "cache_write_tokens": getattr(run, "cache_write_tokens", 0) or 0,
        "cost_usd": float(getattr(run, "cost_usd", 0.0) or 0.0),
        "cost_source": getattr(run, "cost_source", "UNKNOWN"),
        "model": getattr(run, "model", None),
    }

