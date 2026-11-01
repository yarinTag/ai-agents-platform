"""
System events and monitoring API endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import StreamingResponse
from typing import List, Optional, Any
import asyncio
import json
from datetime import datetime, timedelta

# All PoC imports go through the centralized dependencies module
from ..dependencies import (
    get_config_manager, get_db_manager, get_runtime_adapter, get_optional_runtime_adapter,
    get_event_bus, get_event_service,
    TaskStatus, EventBus, EventService, PlatformEvent
)


router = APIRouter()


@router.get("/stream")
@router.get("/stream/")
async def stream_events(
    request: Request,
    agent_id: Optional[str] = None,
    task_id: Optional[str] = None,
    project_id: Optional[str] = None,
    after_sequence: Optional[int] = None,
    since: Optional[str] = None,
    live: bool = True,
    limit: Optional[int] = None,
    event_bus: EventBus = Depends(get_event_bus),
    event_service: EventService = Depends(get_event_service)
):
    """
    Global Server-Sent Events (SSE) stream endpoint.
    Streams real-time platform events with support for filtering and historical replay.
    Only events owned by the caller's organization (and departments) are streamed.
    """
    from ..security import get_authorized_scope
    from .scope import EventScope
    tenant = EventScope(event_service.db_manager, get_authorized_scope(request, event_service.db_manager))
    def stream_data(event):
        data = event.to_dict()
        if event.task_id and not (data.get("payload") or {}).get("workflow_execution_id"):
            data["payload"] = {**(data.get("payload") or {}),
                **event_service.db_manager.get_task_workflow_context(event.task_id)}
        return data

    async def event_generator():
        # Match filter for live events
        def matches_filter(event: PlatformEvent) -> bool:
            if agent_id and event.agent_id != agent_id:
                return False
            if task_id and event.task_id != task_id:
                return False
            if project_id and event.project_id != project_id:
                return False
            return True

        # Subscribe first to capture events while replay occurs
        queue, unsubscribe = event_bus.subscribe(filter_fn=matches_filter)
        last_seq = 0
        sent_count = 0

        try:
            # 0. Send immediate connected event to commit response headers
            yield f"event: connected\ndata: {json.dumps({'status': 'connected', 'timestamp': datetime.now().isoformat()})}\n\n"

            # 1. Historical replay if requested
            if after_sequence is not None or since is not None:
                historical_events = event_service.get_events(
                    agent_id=agent_id,
                    task_id=task_id,
                    project_id=project_id,
                    after_sequence=after_sequence,
                    since=since,
                    limit=limit or 500
                )
                for e in historical_events:
                    if e.sequence_number and e.sequence_number > last_seq:
                        last_seq = e.sequence_number
                    if not await asyncio.to_thread(tenant.allows, e):
                        continue
                    yield f"event: {e.event_type}\ndata: {json.dumps(stream_data(e))}\n\n"
                    sent_count += 1
                    if limit and sent_count >= limit:
                        return

            # If client only requested historical replay (live=False), finish stream cleanly
            if not live:
                return

            # 2. Live event streaming with 2s heartbeat
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=2.0)
                    # Deduplicate if event was already yielded in historical replay
                    if last_seq and event.sequence_number and event.sequence_number <= last_seq:
                        continue
                    if not await asyncio.to_thread(tenant.allows, event):
                        continue
                    yield f"event: {event.event_type}\ndata: {json.dumps(stream_data(event))}\n\n"
                    sent_count += 1
                    if limit and sent_count >= limit:
                        break
                except asyncio.TimeoutError:
                    heartbeat_payload = json.dumps({"timestamp": datetime.now().isoformat()})
                    yield f"event: heartbeat\ndata: {heartbeat_payload}\n\n"

        except asyncio.CancelledError:
            # Client disconnected
            pass
        finally:
            unsubscribe()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.get("/system/stats")
async def get_system_stats(
    request: Request,
    config_manager = Depends(get_config_manager),
    db_manager = Depends(get_db_manager),
    runtime_adapter = Depends(get_optional_runtime_adapter)
):
    """Get statistics for the caller's organization only."""
    from ..security import get_current_org_id
    org_id = get_current_org_id(request)
    if not org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="An organization scope is required.")
    owned = lambda item: getattr(item, "organization_id", None) == org_id
    agents = [a for a in config_manager.list_agents() if owned(a)]
    projects = [p for p in config_manager.list_projects() if owned(p)]
    project_ids = {p.id for p in projects}
    # Skills have no organization: global skills plus skills of this org's projects.
    skills = [s for s in db_manager.list_skills() if s.project_id is None or s.project_id in project_ids]
    recent_tasks = db_manager.list_task_runs(limit=10, organization_id=org_id)

    # Count tasks by status
    task_counts = {status.value: 0 for status in TaskStatus}
    for task in recent_tasks:
        task_counts[task.status.value] = task_counts.get(task.status.value, 0) + 1

    # Get active runs from runtime adapter
    active_runs = []
    live_runs = runtime_adapter.list_runs() if runtime_adapter else recent_tasks
    for run in live_runs:
        run_id = run.run_id
        if owned(run) and run.status in [TaskStatus.QUEUED, TaskStatus.RUNNING]:
            active_runs.append({
                "run_id": run_id,
                "agent_id": run.agent_id,
                "project_id": run.project_id,
                "status": run.status.value,
                "started_at": run.started_at.isoformat() if run.started_at else None
            })

    return {
        "agents": {
            "total": len(agents),
            "by_status": {}  # Could add agent status tracking later
        },
        "projects": {
            "total": len(projects)
        },
        "skills": {
            "total": len(skills),
            "global": len([s for s in skills if s.project_id is None]),
            "project-specific": len([s for s in skills if s.project_id is not None])
        },
        "tasks": {
            "total_recent": len(recent_tasks),
            "by_status": task_counts,
            "active": len(active_runs),
            "active_runs": active_runs
        },
        "runtime_available": runtime_adapter is not None,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }


@router.get("/system/health")
async def get_system_health(
    config_manager = Depends(get_config_manager),
    db_manager = Depends(get_db_manager),
    runtime_adapter = Depends(get_optional_runtime_adapter)
):
    """Get system health status."""
    health_checks = []
    overall_healthy = True

    # Check config manager
    try:
        agents = config_manager.list_agents()
        health_checks.append({
            "component": "config_manager",
            "status": "healthy",
            "message": "Configuration loaded"
        })
    except Exception as e:
        health_checks.append({
            "component": "config_manager",
            "status": "unhealthy",
            "message": str(e)
        })
        overall_healthy = False

    # Check database manager
    try:
        db_agents = db_manager.list_agents()
        health_checks.append({
            "component": "persistence_manager",
            "status": "healthy",
            "message": "Database reachable"
        })
    except Exception as e:
        health_checks.append({
            "component": "persistence_manager",
            "status": "unhealthy",
            "message": str(e)
        })
        overall_healthy = False

    # Check runtime adapter
    try:
        if runtime_adapter is None:
            raise RuntimeError("Runtime capability is unavailable")
        runs = runtime_adapter.list_runs()
        active_count = len([
            r for r in runs
            if r.status in [TaskStatus.QUEUED, TaskStatus.RUNNING]
        ])
        health_checks.append({
            "component": "runtime_adapter",
            "status": "healthy",
            "message": "Runtime responding"
        })
    except Exception as e:
        health_checks.append({
            "component": "runtime_adapter",
            "status": "unhealthy",
            "message": str(e)
        })
        overall_healthy = False

    return {
        "status": "healthy" if overall_healthy else "unhealthy",
        "checks": health_checks,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }


@router.get("/system/recent-activity")
async def get_recent_activity(
    request: Request,
    limit: int = 20,
    execution_scope: str = "all",
    db_manager = Depends(get_db_manager)
):
    """Get recent system activity across agents, projects, skills, and tasks."""
    if execution_scope not in ("all", "office", "workflow"):
        raise HTTPException(status_code=422, detail="Invalid execution_scope")
    from ..security import get_current_org_id
    try:
        # Get recent task runs
        recent_tasks = db_manager.list_task_runs(limit=limit, execution_scope=execution_scope,
            organization_id=get_current_org_id(request))

        activity = []
        for task in recent_tasks:
            activity.append({
                "type": "task",
                "action": f"Task {task.status.value}",
                "description": f"Agent {task.agent_id} -> {task.status.value}",
                "timestamp": task.ended_at.isoformat() if task.ended_at else task.created_at.isoformat(),
                "entity_id": task.run_id,
                "entity_type": "task_run",
                "agent_id": task.agent_id,
                "project_id": task.project_id
            })

        # Sort by timestamp descending
        activity.sort(key=lambda x: x["timestamp"], reverse=True)

        return {
            "activity": activity[:limit],
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve recent activity: {str(e)}"
        )


# WebSocket endpoint for real-time system updates (optional enhancement)
@router.websocket("/ws/system")
async def system_websocket(websocket):
    """WebSocket endpoint for real-time system updates."""
    await websocket.accept()
    try:
        while True:
            # Send periodic updates
            await asyncio.sleep(5)
            # In a real implementation, you'd send actual system updates
            await websocket.send_json({
                "type": "heartbeat",
                "timestamp": datetime.utcnow().isoformat() + "Z"
            })
    except Exception:
        # Client disconnected
        pass
    finally:
        await websocket.close()
