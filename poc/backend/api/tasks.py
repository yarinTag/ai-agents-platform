"""Compatibility exports and router composition for tasks."""

from fastapi import APIRouter
# Bootstrap the single legacy import bridge before domain compatibility exports.
from ..dependencies import get_db_manager
from .tasks_models import (TaskCreate, TaskDelegateRequest, TaskResponse, TaskEvent)
from .tasks_mapping import (task_run_to_response)
from .tasks_crud import (create_task, list_tasks, delete_task, get_task, cancel_task)
from .tasks_stream import (_active_connections, task_events, get_task_logs)
from .tasks_delegation import (delegate_task, get_subtasks, get_task_tree)

router = APIRouter()
from .tasks_crud import router as crud_router
router.include_router(crud_router)
from .tasks_stream import router as stream_router
router.include_router(stream_router)
from .tasks_delegation import router as delegation_router
router.include_router(delegation_router)
