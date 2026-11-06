"""Tasks: crud ownership."""

from fastapi import HTTPException, Depends, status, BackgroundTasks, Request
from typing import List, Optional
from datetime import datetime
from ..dependencies import get_config_manager, get_db_manager, get_runtime_adapter, get_optional_runtime_adapter, get_event_service, AgentRun, TaskStatus, EventService, EventType
from ..security import get_current_org_id
import uuid
from ..dependencies import get_task_queue_publisher
import asyncio
import json
from .tasks_models import TaskCreate, TaskResponse
from .tasks_mapping import task_run_to_response
from fastapi import APIRouter

router = APIRouter()


@router.post("/", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    task_data: TaskCreate,
    background_tasks: BackgroundTasks,
    request: Request,
    config_manager = Depends(get_config_manager),
    db_manager = Depends(get_db_manager),
    runtime_adapter = Depends(get_optional_runtime_adapter),
    event_service: EventService = Depends(get_event_service)
):
    """Submit a new task for execution."""
    org_id = task_data.organization_id or get_current_org_id(request)

    # Find agent from config or db
    agent = db_manager.get_agent(task_data.agent_id) or config_manager.get_agent(task_data.agent_id)
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

    # AI Security Firewall: Scan prompt for Direct Injections, Jailbreaks, and Malicious Commands
    from ..security.firewall import get_prompt_firewall
    firewall = get_prompt_firewall()
    firewall.assert_clean_prompt(
        text=prompt,
        source="tasks_api",
        db_manager=db_manager,
        org_id=org_id,
        actor=getattr(request.state, "user", {}).get("email", "api_user") if hasattr(request, "state") else "api_user"
    )

    # Distributed Queue Dispatch branch
    if task_data.use_queue:
        task_id = f"task_{uuid.uuid4().hex[:12]}"
        publisher = get_task_queue_publisher()
        run = AgentRun(
            run_id=task_id,
            agent_id=agent.id,
            project_id=task_data.project_id,
            prompt=prompt,
            status=TaskStatus.QUEUED,
            created_at=datetime.now(),
            organization_id=org_id
        )
        db_manager.save_task_run(run)
        try:
            await publisher.publish_task(
                task_id=task_id,
                agent_id=agent.id,
                project_id=task_data.project_id or "default",
                prompt=prompt,
                org_id=org_id,
                priority=task_data.priority or 5
            )
        except Exception as error:
            run.status = TaskStatus.FAILED
            run.error = "Queue dispatch unavailable"
            run.ended_at = datetime.now()
            db_manager.save_task_run(run)
            raise HTTPException(status_code=503, detail="Queue dispatch unavailable") from error
        return task_run_to_response(run)

    if runtime_adapter is None:
        runtime_adapter = get_runtime_adapter()

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
            started_at=datetime.now(),
            organization_id=org_id
        )
    else:
        if org_id and not getattr(run, "organization_id", None):
            run.organization_id = org_id

    try:
        db_manager.save_task_run(run)
    except Exception as e:
        print(f"Warning saving task run to DB: {e}")

    resp = task_run_to_response(run)

    # Emit task lifecycle events
    event_service.emit(
        event_type=EventType.TASK_CREATED,
        payload=resp,
        agent_id=run.agent_id,
        task_id=run.run_id,
        project_id=run.project_id,
        source="tasks_api"
    )
    event_service.emit(
        event_type=EventType.TASK_STARTED,
        payload=resp,
        agent_id=run.agent_id,
        task_id=run.run_id,
        project_id=run.project_id,
        source="tasks_api"
    )

    try:
        db_manager.log_audit(
            action="TASK_DISPATCH",
            actor="api_client",
            entity_type="task",
            entity_id=run.run_id,
            details={
                "agent_id": run.agent_id,
                "project_id": run.project_id,
                "prompt_preview": prompt[:80] if prompt else "",
                "organization_id": org_id
            }
        )
    except Exception:
        pass

    return resp




@router.get("/", response_model=List[TaskResponse])
@router.get("", response_model=List[TaskResponse])
async def list_tasks(
    request: Request,
    agent_id: Optional[str] = None,
    project_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    execution_scope: str = "all",
    db_manager = Depends(get_db_manager),
    runtime_adapter = Depends(get_optional_runtime_adapter)
):
    """List tasks with optional filtering, merging DB and live runtime runs."""
    if execution_scope not in ("all", "office", "workflow"):
        raise HTTPException(status_code=422, detail="Invalid execution_scope")
    contexts = db_manager.get_workflow_task_contexts()
    task_status = None
    if status:
        try:
            task_status = TaskStatus(status)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status: {status}"
            )

    org_id = get_current_org_id(request)

    runs_map = {}
    for run in db_manager.list_task_runs(
        agent_id=agent_id,
        project_id=project_id,
        status=task_status,
        limit=limit,
        organization_id=org_id,
        execution_scope=execution_scope
    ):
        runs_map[run.run_id] = run

    if hasattr(runtime_adapter, 'list_runs'):
        for run in runtime_adapter.list_runs():
            if org_id and getattr(run, "organization_id", None) and run.organization_id != org_id:
                continue
            if execution_scope == "office" and run.run_id in contexts:
                continue
            if execution_scope == "workflow" and run.run_id not in contexts:
                continue
            if agent_id and run.agent_id != agent_id:
                continue
            if project_id and run.project_id != project_id:
                continue
            if task_status and run.status != task_status:
                continue
            runs_map[run.run_id] = run

    runs = list(runs_map.values())
    runs.sort(key=lambda r: r.created_at or datetime.min, reverse=True)
    return [{**task_run_to_response(run), **contexts.get(run.run_id, {})} for run in runs[:limit]]




@router.delete("/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
@router.delete("/{run_id}/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    run_id: str,
    request: Request,
    db_manager = Depends(get_db_manager),
    runtime_adapter = Depends(get_runtime_adapter),
    event_service: EventService = Depends(get_event_service)
):
    """Delete a task run."""
    org_id = get_current_org_id(request)
    existing = db_manager.get_task_run(run_id)
    if not existing and hasattr(runtime_adapter, "get_run_status"):
        existing = runtime_adapter.get_run_status(run_id)
    if org_id and existing and getattr(existing, "organization_id", None) and existing.organization_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task not found: {run_id}"
        )

    try:
        # Cancel if currently active in runtime
        if hasattr(runtime_adapter, "active_runs") and run_id in runtime_adapter.active_runs:
            try:
                runtime_adapter.cancel_task(run_id)
            except Exception:
                pass

        db_manager.delete_task_run(run_id)

        # Notify UI via event stream
        event_service.emit(
            event_type=EventType.TASK_DELETED,
            payload={"run_id": run_id, "id": run_id, "deleted": True},
            task_id=run_id,
            source="tasks_api"
        )
    except Exception as e:
        print(f"Warning deleting task run: {e}")
    return None



@router.get("/{run_id}", response_model=TaskResponse)
@router.get("/{run_id}/", response_model=TaskResponse)
async def get_task(
    run_id: str,
    request: Request,
    db_manager = Depends(get_db_manager),
    runtime_adapter = Depends(get_optional_runtime_adapter)
):
    """Get a specific task by ID, checking DB and active runtime."""
    active_run = None
    if hasattr(runtime_adapter, "get_run_status"):
        active_run = runtime_adapter.get_run_status(run_id)
    if not active_run and hasattr(runtime_adapter, "list_runs"):
        for r in runtime_adapter.list_runs():
            if getattr(r, "run_id", None) == run_id:
                active_run = r
                break

    run = active_run or db_manager.get_task_run(run_id)
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
    return task_run_to_response(run)



@router.post("/{run_id}/cancel", response_model=TaskResponse)
@router.post("/{run_id}/cancel/", response_model=TaskResponse)
async def cancel_task(
    run_id: str,
    request: Request,
    runtime_adapter = Depends(get_runtime_adapter),
    db_manager = Depends(get_db_manager)
):
    """Cancel a running task."""
    # Check if task exists
    existing_run = db_manager.get_task_run(run_id)
    if not existing_run and hasattr(runtime_adapter, "get_run_status"):
        existing_run = runtime_adapter.get_run_status(run_id)
    if not existing_run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task not found: {run_id}"
        )
    org_id = get_current_org_id(request)
    if org_id and getattr(existing_run, "organization_id", None) and existing_run.organization_id != org_id:
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

