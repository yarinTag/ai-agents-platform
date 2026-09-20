"""
Task management API endpoints.
"""

from fastapi import APIRouter, HTTPException, Depends, status, BackgroundTasks
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
import uuid
from datetime import datetime

# Import from parent directory (backend)
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dependencies import get_config_manager, get_db_manager, get_runtime_adapter
from config import AgentConfig, ProjectConfig
from runtime_adapter import AgentRun, TaskStatus
import asyncio
import json


router = APIRouter()


# Pydantic models for request/response
class TaskCreate(BaseModel):
    agent_id: str = Field(..., min_length=1)
    prompt: Optional[str] = None
    input_data: Optional[Any] = None
    project_id: Optional[str] = None
    skill_id: Optional[str] = None


class TaskResponse(BaseModel):
    id: str
    run_id: str
    agent_id: str
    project_id: Optional[str] = None
    prompt: str = ""
    input_data: Optional[Any] = None
    output_data: Optional[Any] = None
    status: str
    created_at: str
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    result: Optional[str] = None
    error: Optional[str] = None
    exit_code: Optional[int] = None

    class Config:
        from_attributes = True


class TaskEvent(BaseModel):
    type: str
    timestamp: float
    run_id: str
    # Additional fields will vary by event type
    message: Optional[dict] = None
    result: Optional[str] = None
    error: Optional[dict] = None
    estimated_tokens: Optional[int] = None
    estimated_tokens_delta: Optional[int] = None
    subtype: Optional[str] = None
    session_id: Optional[str] = None


# In-memory store for active SSE connections (in production, use Redis or similar)
_active_connections = {}


def task_run_to_response(run: AgentRun) -> dict:
    """Convert AgentRun to API response format."""
    return {
        "id": run.run_id,
        "run_id": run.run_id,
        "agent_id": run.agent_id,
        "project_id": run.project_id,
        "prompt": run.prompt,
        "input_data": {"task": run.prompt, "prompt": run.prompt},
        "output_data": {"result": run.result} if run.result else None,
        "status": run.status.value,
        "created_at": run.created_at.isoformat() if run.created_at else datetime.now().isoformat(),
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "ended_at": run.ended_at.isoformat() if run.ended_at else None,
        "result": run.result,
        "error": run.error,
        "exit_code": run.exit_code
    }


@router.post("/", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    task_data: TaskCreate,
    background_tasks: BackgroundTasks,
    config_manager = Depends(get_config_manager),
    db_manager = Depends(get_db_manager),
    runtime_adapter = Depends(get_runtime_adapter)
):
    """Submit a new task for execution."""
    # Find agent from config or db
    agent = config_manager.get_agent(task_data.agent_id) or db_manager.get_agent(task_data.agent_id)
    if not agent:
        # Fallback by case-insensitive matching
        for a in config_manager.list_agents():
            if a.id.lower() == task_data.agent_id.lower():
                agent = a
                break
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent not found: {task_data.agent_id}"
        )

    # Extract prompt
    prompt = task_data.prompt
    if not prompt and task_data.input_data:
        if isinstance(task_data.input_data, dict):
            prompt = task_data.input_data.get("task") or task_data.input_data.get("prompt") or json.dumps(task_data.input_data)
        else:
            prompt = str(task_data.input_data)
    if not prompt:
        prompt = "Execute agent mission"

    # Start the task via runtime adapter
    run_id = runtime_adapter.start_task(
        agent_id=agent.id,
        project_id=task_data.project_id,
        prompt=prompt
    )

    await asyncio.sleep(0.05)
    run = runtime_adapter.get_run_status(run_id)

    if not run:
        run = AgentRun(
            run_id=run_id,
            agent_id=agent.id,
            project_id=task_data.project_id,
            prompt=prompt,
            status=TaskStatus.RUNNING,
            created_at=datetime.now(),
            started_at=datetime.now()
        )

    try:
        db_manager.save_task_run(run)
    except Exception as e:
        print(f"Warning saving task run to DB: {e}")

    return task_run_to_response(run)


@router.get("/", response_model=List[TaskResponse])
@router.get("", response_model=List[TaskResponse])
async def list_tasks(
    agent_id: Optional[str] = None,
    project_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    db_manager = Depends(get_db_manager),
    runtime_adapter = Depends(get_runtime_adapter)
):
    """List tasks with optional filtering, merging DB and live runtime runs."""
    task_status = None
    if status:
        try:
            task_status = TaskStatus(status)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {status}"
            )

    runs_map = {}
    for run in db_manager.list_task_runs(
        agent_id=agent_id,
        project_id=project_id,
        status=task_status,
        limit=limit
    ):
        runs_map[run.run_id] = run

    if hasattr(runtime_adapter, 'list_runs'):
        for run in runtime_adapter.list_runs():
            if agent_id and run.agent_id != agent_id:
                continue
            if project_id and run.project_id != project_id:
                continue
            if task_status and run.status != task_status:
                continue
            runs_map[run.run_id] = run

    runs = list(runs_map.values())
    runs.sort(key=lambda r: r.created_at or datetime.min, reverse=True)
    return [task_run_to_response(run) for run in runs[:limit]]


@router.delete("/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
@router.delete("/{run_id}/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    run_id: str,
    db_manager = Depends(get_db_manager)
):
    """Delete a task run."""
    try:
        db_manager.delete_task_run(run_id)
    except Exception as e:
        print(f"Warning deleting task run: {e}")
    return None


@router.get("/{run_id}", response_model=TaskResponse)
async def get_task(
    run_id: str,
    db_manager = Depends(get_db_manager)
):
    """Get a specific task by ID."""
    run = db_manager.get_task_run(run_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task not found: {run_id}"
        )
    return task_run_to_response(run)


@router.post("/{run_id}/cancel", response_model=TaskResponse)
async def cancel_task(
    run_id: str,
    runtime_adapter = Depends(get_runtime_adapter),
    db_manager = Depends(get_db_manager)
):
    """Cancel a running task."""
    # Check if task exists
    existing_run = db_manager.get_task_run(run_id)
    if not existing_run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task not found: {run_id}"
        )

    # Attempt cancellation
    success = runtime_adapter.cancel_run(run_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel task {run_id} (may already be completed)"
        )

    # Get updated status
    await asyncio.sleep(0.1)  # Give it a moment to update
    updated_run = runtime_adapter.get_run_status(run_id)
    if not updated_run:
        # Fallback to DB
        updated_run = db_manager.get_task_run(run_id)

    return task_run_to_response(updated_run)


@router.get("/{run_id}/events")
async def task_events(
    run_id: str,
    runtime_adapter = Depends(get_runtime_adapter)
):
    """Server-Sent Events endpoint for real-time task monitoring."""
    # Verify task exists
    run = runtime_adapter.get_run_status(run_id)
    if not run:
        # Check DB as fallback
        from dependencies import get_db_manager
        db_manager = get_db_manager()
        run = db_manager.get_task_run(run_id)
        if not run:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task not found: {run_id}"
            )

    async def event_generator():
        """Generate SSE events for the task."""
        # Set up a queue to collect events
        event_queue = asyncio.Queue()

        # Define event handler
        def event_handler(event):
            # Add metadata
            event_with_meta = {
                **event,
                "_timestamp": event.get("_timestamp", asyncio.get_event_loop().time()),
                "_run_id": run_id
            }
            # Put in queue (non-blocking)
            try:
                event_queue.put_nowait(event_with_meta)
            except asyncio.QueueFull:
                pass  # Drop event if queue full

        # Subscribe to events
        unsubscribe = runtime_adapter.subscribe_to_events(run_id, event_handler)

        try:
            # Send initial connection established event
            yield {
                "event": "connected",
                "data": json.dumps({
                    "run_id": run_id,
                    "status": run.status.value if run else "unknown",
                    "timestamp": asyncio.get_event_loop().time()
                })
            }

            # Stream events as they arrive
            while True:
                try:
                    # Wait for event with timeout to allow checking connection
                    event = await asyncio.wait_for(event_queue.get(), timeout=30.0)

                    # Check if this is an end event
                    if event.get("type") == "end_of_output" or \
                       event.get("type") in ["result", "error"]:
                        yield {
                            "event": event["type"],
                            "data": json.dumps(event)
                        }
                        # Send close event after result/error
                        if event.get("type") in ["result", "error"]:
                            yield {
                                "event": "close",
                                "data": json.dumps({"run_id": run_id})
                            }
                        break
                    else:
                        yield {
                            "event": "event",
                            "data": json.dumps(event)
                        }

                except asyncio.TimeoutError:
                    # Send heartbeat to keep connection alive
                    yield {
                        "event": "heartbeat",
                        "data": json.dumps({
                            "run_id": run_id,
                            "timestamp": asyncio.get_event_loop().time()
                        })
                    }
                    # Check if task is still running
                    current_run = runtime_adapter.get_run_status(run_id)
                    if current_run and current_run.status in [
                        TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED
                    ]:
                        # Task finished, send final update and close
                        yield {
                            "event": "update",
                            "data": json.dumps(task_run_to_response(current_run))
                        }
                        yield {
                            "event": "close",
                            "data": json.dumps({"run_id": run_id})
                        }
                        break

        except Exception as e:
            yield {
                "event": "error",
                "data": json.dumps({
                    "message": str(e),
                    "run_id": run_id
                })
            }
        finally:
            # Clean up subscription
            try:
                unsubscribe()
            except:
                pass

    # Return SSE response
    from fastapi.responses import StreamingResponse
    return StreamingResponse(
        event_generator(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream",
        }
    )


@router.get("/{run_id}/logs")
async def get_task_logs(
    run_id: str,
    db_manager = Depends(get_db_manager)
):
    """Get full task execution logs/events from persistence."""
    run = db_manager.get_task_run(run_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task not found: {run_id}"
        )

    return {
        "run_id": run.run_id,
        "events": run.events or [],
        "status": run.status.value,
        "result": run.result,
        "error": run.error
    }