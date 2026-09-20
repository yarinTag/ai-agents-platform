"""
System events and monitoring API endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
import asyncio
import json
from datetime import datetime, timedelta

# Import from parent directory (backend)
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dependencies import get_config_manager, get_db_manager, get_runtime_adapter
from runtime_adapter import TaskStatus


router = APIRouter()


@router.get("/system/stats")
async def get_system_stats(
    config_manager = Depends(get_config_manager),
    db_manager = Depends(get_db_manager),
    runtime_adapter = Depends(get_runtime_adapter)
):
    """Get overall system statistics."""
    agents = config_manager.list_agents()
    projects = config_manager.list_projects()
    skills = db_manager.list_skills()
    recent_tasks = db_manager.list_task_runs(limit=10)

    # Count tasks by status
    task_counts = {status.value: 0 for status in TaskStatus}
    for task in recent_tasks:
        task_counts[task.status.value] = task_counts.get(task.status.value, 0) + 1

    # Get active runs from runtime adapter
    active_runs = []
    for run_id, run in runtime_adapter._runs.items():
        if run.status in [TaskStatus.QUEUED, TaskStatus.RUNNING]:
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
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }


@router.get("/system/health")
async def get_system_health(
    config_manager = Depends(get_config_manager),
    db_manager = Depends(get_db_manager),
    runtime_adapter = Depends(get_runtime_adapter)
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
            "message": f"Loaded {len(agents)} agents"
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
            "message": f"Connected to DB, {len(db_agents)} agents persisted"
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
        # Simple check: can we access the adapter?
        active_count = len([
            r for r in runtime_adapter._runs.values()
            if r.status in [TaskStatus.QUEUED, TaskStatus.RUNNING]
        ])
        health_checks.append({
            "component": "runtime_adapter",
            "status": "healthy",
            "message": f"Managing {len(runtime_adapter._runs)} total runs, {active_count} active"
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
    limit: int = 20,
    db_manager = Depends(get_db_manager)
):
    """Get recent system activity across agents, projects, skills, and tasks."""
    try:
        # Get recent task runs
        recent_tasks = db_manager.list_task_runs(limit=limit)

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