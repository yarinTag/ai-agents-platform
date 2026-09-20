"""
Agent Hierarchy Validator.

Enforces business and architectural rules for agent organizational hierarchy:
- ROOT_ORCHESTRATOR has no parent
- MANAGER may have children
- WORKER and SPECIALIST cannot have children
- An agent has at most one parent
- Circular references are strictly forbidden
- Maximum hierarchy depth is enforced (default: 3)
"""

from typing import Optional, List, Set
import logging

from config import AgentConfig, AgentRole
from persistence import DatabaseManager

logger = logging.getLogger(__name__)

DEFAULT_MAX_HIERARCHY_DEPTH = 3


class HierarchyValidationError(ValueError):
    """Raised when an agent hierarchy violates structural or role rules."""
    pass


def validate_agent_hierarchy(
    agent_id: str,
    role_type: str,
    parent_id: Optional[str],
    db_manager: DatabaseManager,
    max_depth: int = DEFAULT_MAX_HIERARCHY_DEPTH
) -> None:
    """
    Validate hierarchy constraints for an agent before creation or update.
    Raises HierarchyValidationError if any rule is violated.
    """
    norm_role = role_type.upper() if role_type else AgentRole.WORKER.value

    # Rule 1: ROOT_ORCHESTRATOR must have no parent
    if norm_role == AgentRole.ROOT_ORCHESTRATOR.value:
        if parent_id:
            raise HierarchyValidationError(
                f"Agent '{agent_id}' with role ROOT_ORCHESTRATOR cannot have a parent (got: '{parent_id}')."
            )

    # Rule 2: Cannot be own parent
    if parent_id and parent_id == agent_id:
        raise HierarchyValidationError(
            f"Agent '{agent_id}' cannot be its own parent."
        )

    # If parent is specified, validate parent exists and role allows children
    if parent_id:
        parent = db_manager.get_agent(parent_id)
        if not parent:
            raise HierarchyValidationError(
                f"Parent agent '{parent_id}' does not exist."
            )

        parent_role = parent.role_type.upper() if parent.role_type else AgentRole.WORKER.value
        if parent_role in [AgentRole.WORKER.value, AgentRole.SPECIALIST.value]:
            raise HierarchyValidationError(
                f"Parent agent '{parent_id}' has role '{parent_role}', which cannot have children. "
                f"Only MANAGER or ROOT_ORCHESTRATOR may have child agents."
            )

        # Rule 3: Cycle Detection
        # Traverse upwards from parent_id to root. If agent_id is encountered, it's a cycle.
        visited: Set[str] = {agent_id}
        curr = parent
        depth = 1  # Depth of the new agent from its parent

        while curr:
            if curr.id in visited:
                raise HierarchyValidationError(
                    f"Circular reference detected in agent hierarchy: '{agent_id}' is an ancestor of '{parent_id}'."
                )
            visited.add(curr.id)
            depth += 1

            if depth > max_depth:
                raise HierarchyValidationError(
                    f"Hierarchy depth ({depth}) exceeds maximum allowed depth of {max_depth}."
                )

            if curr.parent_id:
                curr = db_manager.get_agent(curr.parent_id)
            else:
                break

    # Rule 4: If demoting an existing agent to WORKER/SPECIALIST, verify it has no existing children
    if norm_role in [AgentRole.WORKER.value, AgentRole.SPECIALIST.value]:
        existing_children = db_manager.get_child_agents(agent_id)
        if existing_children:
            child_ids = [c.id for c in existing_children]
            raise HierarchyValidationError(
                f"Cannot set role of '{agent_id}' to '{norm_role}' because it currently manages child agents: {child_ids}."
            )
