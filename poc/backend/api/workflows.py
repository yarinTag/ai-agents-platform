"""Workflow API composition and compatibility exports."""
from ..dependencies import get_db_manager
from .router_composition import compose_routers
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


from . import workflow_chat as _chat
from . import workflows_settings as _settings
from . import workflows_approvals as _approvals
from . import workflows_channel_triggers as _channel_triggers
from . import workflows_dag_approvals as _dag_approvals

router = compose_routers(_dag_approvals.router, _approvals.router, _chat.router, _settings.router, _generation.router, _queries.router, _channels.router, _channel_triggers.router, _playground.router, _execution.router, _crud.router)
