"""Tenant-scoped operational reliability from persisted production executions."""
from collections import Counter
from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request

from ..dependencies import get_db_manager

router = APIRouter()
HOURS = {"24h": 24, "7d": 168, "30d": 720}
SUGGESTIONS = {
    "connector_auth": "Check the connector credentials and repository or channel grants in MCP Hub.",
    "budget": "Review this department's spend and budget policy in Org & Teams.",
    "timeout": "Review the step timeout and consider splitting long work into parallel steps.",
    "output_validation": "Inspect the failing step output and align it with the expected response schema.",
    "unknown": "Inspect the latest failed run and its step events.",
}
FAILURE_MARKERS = {
    "connector_auth": ("401", "403", "unauthorized", "forbidden", "invalid api key", "authentication"),
    "budget": ("budget", "quota", "spending limit"),
    "timeout": ("timeout", "timed out", "deadline exceeded"),
    "output_validation": ("output validation", "schema validation", "malformed output", "invalid output"),
}


def _category(error):
    value = (error or "").lower()
    return next((key for key, markers in FAILURE_MARKERS.items() if any(word in value for word in markers)), "unknown")


@router.get("/metrics/reliability")
def get_workflow_reliability(request: Request, window: Literal["24h", "7d", "30d"] = "7d",
                             db=Depends(get_db_manager)):
    actor = request.state.access_actor
    if not actor.organization_id or not actor.allows():
        raise HTTPException(403, "Workflow metrics require access to an organization.")
    end = datetime.now()
    start = end - timedelta(hours=HOURS[window])
    with db._get_connection() as conn:
        rows = conn.execute("""
            SELECT e.id, e.workflow_id, w.name, w.department_id AS workflow_department,
                e.department_id, e.status, e.created_at, e.total_cost_usd,
                e.total_input_tokens, e.total_output_tokens,
                (julianday(e.completed_at) - julianday(e.started_at)) * 86400 AS duration_seconds,
                e.error_message,
                (SELECT s.error_message FROM workflow_step_runs s
                    WHERE s.execution_id=e.id AND s.status='FAILED' AND s.error_message IS NOT NULL
                    ORDER BY s.completed_at, s.step_key LIMIT 1) AS step_error
            FROM workflow_executions e JOIN workflows w ON w.id=e.workflow_id
            WHERE w.organization_id=? AND julianday(e.created_at)>=julianday(?)
                AND julianday(e.created_at)<=julianday(?)
                AND e.trigger_type!='PLAYGROUND' AND e.status IN ('COMPLETED', 'FAILED')
            ORDER BY julianday(e.created_at) DESC, e.id
        """, (actor.organization_id, start.isoformat(), end.isoformat())).fetchall()

    bucket_format = "%Y-%m-%dT%H:00" if window == "24h" else "%Y-%m-%d"
    step = timedelta(hours=1) if window == "24h" else timedelta(days=1)
    trend = {}
    bucket_start = start.replace(minute=0, second=0, microsecond=0)
    if window != "24h":
        bucket_start = bucket_start.replace(hour=0)
    while bucket_start <= end:
        label = bucket_start.strftime(bucket_format)
        trend[label] = {"bucket": label, "completed": 0, "failed": 0}
        bucket_start += step
    by_workflow = {}
    for row in rows:
        if not actor.allows(row["workflow_department"]) or not actor.allows(row["department_id"]):
            continue
        group = by_workflow.setdefault(row["workflow_id"], {
            "workflow_id": row["workflow_id"], "name": row["name"], "completed": 0, "failed": 0,
            "duration_sum": 0.0, "duration_count": 0, "known_cost_usd": 0.0, "unknown_cost_runs": 0,
            "last_failed_execution_id": None, "failure_counts": Counter(),
        })
        status = "failed" if row["status"] == "FAILED" else "completed"
        # Legacy execution timestamps use the server clock without a UTC offset.
        timestamp = datetime.fromisoformat(row["created_at"])
        if timestamp.tzinfo is not None:
            timestamp = timestamp.astimezone().replace(tzinfo=None)
        bucket = timestamp.strftime(bucket_format)
        if bucket in trend:
            trend[bucket][status] += 1
        group[status] += 1
        if row["duration_seconds"] is not None and row["duration_seconds"] >= 0:
            group["duration_count"] += 1
            group["duration_sum"] += row["duration_seconds"]
        cost = row["total_cost_usd"] or 0
        group["known_cost_usd"] += cost
        if not cost and (row["total_input_tokens"] or row["total_output_tokens"]):
            group["unknown_cost_runs"] += 1
        if status == "failed":
            if not group["last_failed_execution_id"]:
                group["last_failed_execution_id"] = row["id"]
            group["failure_counts"][_category(row["step_error"] or row["error_message"])] += 1

    for group in by_workflow.values():
        count = group["completed"] + group["failed"]
        duration_count = group.pop("duration_count")
        duration_sum = group.pop("duration_sum")
        group["average_duration_seconds"] = round(duration_sum / duration_count, 1) if duration_count else None
        group["failure_rate"] = group["failed"] / count
        group["success_rate"] = group["completed"] / count
        group["average_cost_usd"] = None if group["unknown_cost_runs"] else group["known_cost_usd"] / count
        group["suggestions"] = [{"category": key, "message": SUGGESTIONS[key]} for key, failures
                                in group["failure_counts"].most_common() if failures >= 2]
    return {"window": window, "trend": [trend[key] for key in sorted(trend)],
            "workflows": sorted(by_workflow.values(), key=lambda item: (-item["failed"], item["name"], item["workflow_id"]))}
