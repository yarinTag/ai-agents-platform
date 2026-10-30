"""
Schedules & Cron Jobs API endpoints.
Provides complete scheduling, monitoring, and execution control for recurring agent jobs.
"""

from fastapi import APIRouter, HTTPException, Depends, status
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

from ..dependencies import get_db_manager, get_runtime_adapter
from .dispatch import dispatch_scheduled_job
from .expressions import calculate_next_run, get_upcoming_runs, validate_cron_expression
from persistence import DatabaseManager
from runtime.protocol import RuntimeAdapter

router = APIRouter()


class ScheduleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    description: Optional[str] = None
    cron_expression: str = Field(..., min_length=5)
    agent_id: str = Field(..., min_length=1)
    project_id: Optional[str] = None
    prompt: str = Field(..., min_length=1)
    input_data: Optional[Dict[str, Any]] = None
    enabled: bool = True
    concurrency_policy: str = Field(default="SKIP", pattern="^(SKIP|COALESCE|ALLOW)$")
    misfire_policy: str = Field(default="RUN_ONCE", pattern="^(RUN_ONCE|SKIP)$")
    timezone: str = "UTC"


class ScheduleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    cron_expression: Optional[str] = None
    agent_id: Optional[str] = None
    project_id: Optional[str] = None
    prompt: Optional[str] = None
    input_data: Optional[Dict[str, Any]] = None
    enabled: Optional[bool] = None
    concurrency_policy: Optional[str] = None
    misfire_policy: Optional[str] = None
    timezone: Optional[str] = None


class ToggleRequest(BaseModel):
    enabled: bool


class CronValidationRequest(BaseModel):
    cron_expression: str


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_schedule(
    payload: ScheduleCreate,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Create a new recurring scheduled job."""
    if not validate_cron_expression(payload.cron_expression):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid cron expression: '{payload.cron_expression}'"
        )

    # Validate agent existence
    agent = db.get_agent(payload.agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{payload.agent_id}' does not exist"
        )

    try:
        next_run = calculate_next_run(payload.cron_expression)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error calculating next run time: {e}"
        )

    job_data = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
    job_data['next_run_at'] = next_run

    job = db.create_cron_job(job_data)
    return job


@router.get("/")
async def list_schedules(
    agent_id: Optional[str] = None,
    project_id: Optional[str] = None,
    enabled: Optional[bool] = None,
    db: DatabaseManager = Depends(get_db_manager)
):
    """List all scheduled cron jobs with optional filters."""
    jobs = db.list_cron_jobs(agent_id=agent_id, project_id=project_id, enabled=enabled)
    return jobs


@router.get("/{job_id}")
async def get_schedule(
    job_id: str,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Get details of a specific scheduled job."""
    job = db.get_cron_job(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")
    return job


@router.put("/{job_id}")
async def update_schedule(
    job_id: str,
    payload: ScheduleUpdate,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Update an existing scheduled job."""
    existing = db.get_cron_job(job_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")

    p_dict = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
    updates = {k: v for k, v in p_dict.items() if v is not None}

    if "cron_expression" in updates:
        if not validate_cron_expression(updates["cron_expression"]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid cron expression: '{updates['cron_expression']}'"
            )
        updates["next_run_at"] = calculate_next_run(updates["cron_expression"])

    updated = db.update_cron_job(job_id, updates)
    return updated


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule(
    job_id: str,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Delete a scheduled cron job."""
    success = db.delete_cron_job(job_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")
    return None


@router.post("/{job_id}/toggle")
async def toggle_schedule(
    job_id: str,
    payload: ToggleRequest,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Enable or disable a scheduled job."""
    job = db.get_cron_job(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")

    updates = {"enabled": payload.enabled}
    if payload.enabled:
        updates["next_run_at"] = calculate_next_run(job["cron_expression"])

    updated = db.update_cron_job(job_id, updates)
    return updated


@router.post("/{job_id}/trigger")
async def trigger_schedule_now(
    job_id: str,
    db: DatabaseManager = Depends(get_db_manager),
    runtime: RuntimeAdapter = Depends(get_runtime_adapter)
):
    """Manually dispatch a scheduled job immediately."""
    job = db.get_cron_job(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")

    now_iso = datetime.now().isoformat()
    task_run_id = await dispatch_scheduled_job(runtime, job)

    db.update_cron_job(job_id, {
        "last_run_id": task_run_id,
        "last_run_at": now_iso,
        "last_status": "RUNNING"
    })

    return {
        "message": f"Schedule '{job['name']}' triggered successfully",
        "task_id": task_run_id,
        "agent_id": job["agent_id"],
        "dispatched_at": now_iso
    }


@router.get("/{job_id}/upcoming")
async def get_schedule_upcoming_runs(
    job_id: str,
    count: int = 5,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Get the upcoming N predicted execution timestamps for a schedule."""
    job = db.get_cron_job(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")

    upcoming = get_upcoming_runs(job["cron_expression"], count=count)
    return {"job_id": job_id, "upcoming_runs": upcoming}


@router.post("/validate")
async def validate_cron(payload: CronValidationRequest):
    """Validate a cron expression and return next 5 projected runs."""
    is_valid = validate_cron_expression(payload.cron_expression)
    if not is_valid:
        return {"valid": False, "error": "Invalid cron format. Expected 5 fields (min hour day-of-month month day-of-week)."}

    upcoming = get_upcoming_runs(payload.cron_expression, count=5)
    return {"valid": True, "upcoming_runs": upcoming}
