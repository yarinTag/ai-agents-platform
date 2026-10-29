"""Compatibility exports and router composition for agents."""

from fastapi import APIRouter
# Bootstrap the single legacy import bridge before domain compatibility exports.
from ..dependencies import get_db_manager
from .agents_models import (_check_runtime_provider, AgentBase, AgentCreate, AgentUpdate, AgentResponse)
from .agents_mapping import (agent_to_response, _check_agent_scope)
from .agents_queries import (list_agents, get_entire_hierarchy_tree, get_agent, get_agent_children, get_agent_subtree)
from .agents_commands import (create_agent, update_agent, delete_agent)

router = APIRouter()
from .agents_queries import router as queries_router
router.include_router(queries_router)
from .agents_commands import router as commands_router
router.include_router(commands_router)
