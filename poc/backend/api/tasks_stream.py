"""Tasks: stream ownership."""

from fastapi import HTTPException, Depends, status, Request
from typing import Any
from ..dependencies import get_db_manager, get_runtime_adapter, get_optional_runtime_adapter, TaskStatus
from ..security import get_current_org_id
import asyncio
import json
from .tasks_mapping import task_run_to_response
from fastapi import APIRouter

router = APIRouter()


_active_connections = {}



@router.get("/{run_id}/events")
@router.get("/{run_id}/events/")
async def task_events(
    run_id: str,
    request: Request,
    runtime_adapter = Depends(get_runtime_adapter),
    db_manager = Depends(get_db_manager)
):
    """Server-Sent Events endpoint for real-time task monitoring."""
    # Verify task exists
    run = runtime_adapter.get_run_status(run_id)
    if not run:
        # Check DB as fallback
        run = db_manager.get_task_run(run_id)
        if not run:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task not found: {run_id}"
            )
    org_id = get_current_org_id(request)
    if org_id and getattr(run, "organization_id", None) and run.organization_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task not found: {run_id}"
        )

    async def event_generator():
        """Generate SSE events for the task."""
        loop = asyncio.get_running_loop()
        event_queue = asyncio.Queue(maxsize=1000)

        def enqueue(event):
            try:
                event_queue.put_nowait(event)
            except asyncio.QueueFull:
                pass

        def event_handler(event):
            event_with_meta = {
                **event, "_timestamp": event.get("_timestamp", loop.time()), "_run_id": run_id,
            }
            try:
                loop.call_soon_threadsafe(enqueue, event_with_meta)
            except RuntimeError:
                pass  # The disconnected client's event loop is already closed.

        # Subscribe to events
        unsubscribe = runtime_adapter.subscribe_to_events(run_id, event_handler)

        def format_sse(event_name: str, payload: Any) -> str:
            payload_str = json.dumps(payload) if not isinstance(payload, str) else payload
            return f"event: {event_name}\ndata: {payload_str}\n\n"

        try:
            # Send initial connection established event
            yield format_sse("connected", {
                "run_id": run_id,
                "status": run.status.value if run else "unknown",
                "timestamp": asyncio.get_event_loop().time()
            })

            # Stream events as they arrive
            while True:
                try:
                    # Wait for event with timeout to allow checking connection
                    event = await asyncio.wait_for(event_queue.get(), timeout=30.0)

                    # Check if this is an end event
                    event_type = event.get("type", "event")
                    if event_type == "end_of_output" or event_type in ["result", "error"]:
                        yield format_sse(event_type, event)
                        # Send close event after result/error
                        if event_type in ["result", "error"]:
                            yield format_sse("close", {"run_id": run_id})
                        break
                    else:
                        yield format_sse("event", event)

                except asyncio.TimeoutError:
                    # Send heartbeat to keep connection alive
                    yield format_sse("heartbeat", {
                        "run_id": run_id,
                        "timestamp": asyncio.get_event_loop().time()
                    })
                    # Check if task is still running
                    current_run = runtime_adapter.get_run_status(run_id)
                    if current_run and current_run.status in [
                        TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED
                    ]:
                        # Task finished, send final update and close
                        yield format_sse("update", task_run_to_response(current_run))
                        yield format_sse("close", {"run_id": run_id})
                        break

        except Exception as e:
            yield format_sse("error", {
                "message": str(e),
                "run_id": run_id
            })
        finally:
            # Clean up subscription
            try:
                unsubscribe()
            except Exception:
                pass

    # Return SSE response with proper text/event-stream media type
    from fastapi.responses import StreamingResponse
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )



@router.get("/{run_id}/logs")
@router.get("/{run_id}/logs/")
async def get_task_logs(
    run_id: str,
    request: Request,
    db_manager = Depends(get_db_manager),
    runtime_adapter = Depends(get_optional_runtime_adapter)
):
    """Get full task execution logs/events from persistence or live runtime."""
    run = db_manager.get_task_run(run_id)
    if not run and hasattr(runtime_adapter, "get_run_status"):
        run = runtime_adapter.get_run_status(run_id)
    if not run and hasattr(runtime_adapter, "list_runs"):
        for r in runtime_adapter.list_runs():
            if getattr(r, "run_id", None) == run_id:
                run = r
                break
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task not found: {run_id}"
        )
    org_id = get_current_org_id(request)
    if org_id and getattr(run, "organization_id", None) and run.organization_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task not found: {run_id}"
        )

    return {
        "run_id": run.run_id,
        "events": getattr(run, "events", None) or [],
        "status": run.status.value if hasattr(run.status, "value") else str(run.status),
        "result": run.result,
        "error": run.error
    }

