"""Tasks: delegation ownership."""

from fastapi import HTTPException, Depends, status, Request
from typing import List
from ..dependencies import get_db_manager, get_orchestration_engine, DelegationError, ConcurrencyLimitExceededError
from ..security import get_current_org_id
from .tasks_models import TaskDelegateRequest, TaskResponse
from .tasks_mapping import task_run_to_response
from fastapi import APIRouter

router = APIRouter()


@router.post("/{run_id}/delegate", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
@router.post("/{run_id}/delegate/", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def delegate_task(
    run_id: str,
    delegate_req: TaskDelegateRequest,
    request: Request,
    orchestration_engine = Depends(get_orchestration_engine),
    db_manager = Depends(get_db_manager)
):
    """Delegate a subtask from a parent task to a target agent."""
    org_id = get_current_org_id(request)
    parent_run = db_manager.get_task_run(run_id)
    if org_id and parent_run and getattr(parent_run, "organization_id", None) and parent_run.organization_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task not found: {run_id}"
        )
    try:
        subtask = orchestration_engine.delegate_task(
            parent_task_id=run_id,
            target_agent_id=delegate_req.target_agent_id,
            subtask_prompt=delegate_req.subtask_prompt,
            timeout_seconds=delegate_req.timeout_seconds or 300,
            project_id=delegate_req.project_id,
            dependencies=delegate_req.dependencies,
            acceptance_criteria=delegate_req.acceptance_criteria
        )

        try:
            db_manager.log_audit(
                action="TASK_DELEGATE",
                actor="orchestration_engine",
                entity_type="task",
                entity_id=subtask.run_id,
                details={
                    "parent_task_id": run_id,
                    "target_agent_id": delegate_req.target_agent_id,
                    "subtask_prompt": delegate_req.subtask_prompt[:80] if delegate_req.subtask_prompt else ""
                }
            )
        except Exception:
            pass

        return task_run_to_response(subtask)
    except ConcurrencyLimitExceededError as e:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(e))
    except DelegationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))



@router.get("/{run_id}/subtasks", response_model=List[TaskResponse])
@router.get("/{run_id}/subtasks/", response_model=List[TaskResponse])
async def get_subtasks(
    run_id: str,
    request: Request,
    db_manager = Depends(get_db_manager)
):
    """Get all subtasks delegated by a parent task."""
    org_id = get_current_org_id(request)
    if org_id:
        parent_run = db_manager.get_task_run(run_id)
        if parent_run and getattr(parent_run, "organization_id", None) and parent_run.organization_id != org_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task not found: {run_id}"
            )
    subtasks = db_manager.get_subtasks(run_id)
    return [task_run_to_response(s) for s in subtasks]



@router.get("/{run_id}/tree")
@router.get("/{run_id}/tree/")
async def get_task_tree(
    run_id: str,
    request: Request,
    db_manager = Depends(get_db_manager)
):
    """Get recursive task execution tree rooted at this task."""
    org_id = get_current_org_id(request)
    if org_id:
        parent_run = db_manager.get_task_run(run_id)
        if parent_run and getattr(parent_run, "organization_id", None) and parent_run.organization_id != org_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task tree not found: {run_id}"
            )
    tree = db_manager.get_task_tree(run_id)
    if not tree:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task tree not found: {run_id}"
        )
    return tree
