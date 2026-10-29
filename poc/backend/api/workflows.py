"""Compatibility exports and router composition for workflows."""

from fastapi import APIRouter
# Bootstrap the single legacy import bridge before domain compatibility exports.
from ..dependencies import get_db_manager
from .workflows_models import (WorkflowCreateRequest, WorkflowUpdateRequest, ChannelBindingDto, WorkflowResponse, WorkflowExecutionResponse, EvaluationRequest, WorkflowGenerateRequest, WorkflowGenerateResponse, WorkflowFormatConvertRequest, WorkflowFormatConvertResponse)
from .workflows_mapping import (_check_workflow_scope, _workflow_to_response)
from .workflows_generation import (generate_workflow_definition, convert_format)
from .workflows_crud import (create_workflow, list_workflows, get_workflow, update_workflow, delete_workflow)
from .workflows_channels import (bind_workflow_channel, unbind_workflow_channel)
from .workflows_execution import (execute_workflow, trigger_webhook, get_execution_status, evaluate_execution)

router = APIRouter()
from .workflows_generation import router as generation_router
router.include_router(generation_router)
from .workflows_crud import router as crud_router
router.include_router(crud_router)
from .workflows_channels import router as channels_router
router.include_router(channels_router)
from .workflows_execution import router as execution_router
router.include_router(execution_router)
