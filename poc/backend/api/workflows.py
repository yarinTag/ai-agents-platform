"""Workflow API composition and compatibility exports."""
from ..dependencies import get_db_manager
from fastapi import APIRouter
from .workflows_models import *
from .workflows_mapping import _workflow_actor, _check_workflow_scope, _workflow_to_response, _execution_to_response
from . import workflows_generation as _generation
from .workflows_generation import *
from . import workflows_crud as _crud
from .workflows_crud import *
from . import workflows_channels as _channels
from .workflows_channels import *
from . import workflows_execution as _execution
from .workflows_execution import *
from . import workflows_playground as _playground
from .workflows_playground import *
from . import workflows_queries as _queries
from .workflows_queries import *

router = APIRouter()
router.include_router(_generation.router)
router.include_router(_queries.router)
router.include_router(_channels.router)
router.include_router(_playground.router)
router.include_router(_execution.router)
router.include_router(_crud.router)
