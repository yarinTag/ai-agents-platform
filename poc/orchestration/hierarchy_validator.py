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

DEFAULT_MAX_HIERARCHY_DEPTH = 5


class HierarchyValidationError(ValueError):
    """Raised when an agent hierarchy violates structural or role rules."""
    pass


class CommunicationAuthorizationError(ValueError):
    """Raised when an agent message violates hierarchy communication permissions."""
    pass


class DelegationError(ValueError):
    """Raised when a task delegation violates organizational hierarchy."""
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
                f"Only MANAGER, SUPER_AGENT, or ROOT_ORCHESTRATOR may have child agents."
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


def validate_agent_communication(
    sender: AgentConfig,
    receiver: AgentConfig,
    db_manager: DatabaseManager
) -> None:
    """
    Validate that sender is authorized to send a message to receiver according to hierarchy and permissions.
    Permitted relationships:
    - Super Agent & Root Orchestrator <-> any subordinate
    - Subordinates -> Super Agent
    - Parent -> Child
    - Child -> Parent
    - Sibling -> Sibling (if siblings share same parent and sibling communication is permitted)
    - Explicit peer allowance (receiver in sender.allowed_peer_ids)
    - Dangerously skip permissions
    """
    if sender.id == receiver.id:
        raise CommunicationAuthorizationError(f"Agent '{sender.id}' cannot send a message to itself.")

    if getattr(sender, "dangerously_skip_permissions", False):
        return

    sender_role = (getattr(sender, "role_type", "") or "WORKER").upper()
    receiver_role = (getattr(receiver, "role_type", "") or "WORKER").upper()

    # Super Agent & Root Orchestrator can message anyone
    if sender_role in ("SUPER_AGENT", "ROOT_ORCHESTRATOR"):
        return

    # Anyone can message Super Agent for assistance/direction
    if receiver_role == "SUPER_AGENT":
        return

    # Parent -> Child
    if getattr(receiver, "parent_id", None) == sender.id:
        return

    # Child -> Parent
    if getattr(sender, "parent_id", None) == receiver.id:
        return

    # Explicit peer allowance
    if receiver.id in (getattr(sender, "allowed_peer_ids", []) or []):
        return

    # Sibling -> Sibling
    sender_parent = getattr(sender, "parent_id", None)
    receiver_parent = getattr(receiver, "parent_id", None)
    if sender_parent and receiver_parent and sender_parent == receiver_parent:
        sender_allow_sibling = getattr(sender, "allow_sibling_communication", True)
        if sender_allow_sibling:
            return
        else:
            raise CommunicationAuthorizationError(
                f"Sibling communication is disabled for agent '{sender.id}'."
            )

    raise CommunicationAuthorizationError(
        f"Agent '{sender.id}' is not authorized to communicate directly with '{receiver.id}'. "
        f"Direct messages must follow hierarchy (Parent/Child), permitted Siblings, or explicit peer permissions."
    )


def validate_delegation_authority(
    parent_agent: AgentConfig,
    target_agent: AgentConfig,
    db_manager: Optional[DatabaseManager] = None
) -> None:
    """
    Validate that parent_agent is authorized to delegate a task to target_agent.
    Rules:
    1. Parent agent must have role ROOT_ORCHESTRATOR, MANAGER, or SUPER_AGENT.
       Workers and Specialists cannot delegate.
    2. Target agent must report directly to parent_agent (target_agent.parent_id == parent_agent.id),
       OR target_agent.id must be in parent_agent.allowed_child_ids.
    3. Workers cannot be delegated to by managers other than their direct manager,
       preventing bypass of the reporting hierarchy.
    """
    if parent_agent.id == target_agent.id:
        raise DelegationError(f"Agent '{parent_agent.id}' cannot delegate to itself.")

    parent_role = (getattr(parent_agent, "role_type", "") or "WORKER").upper()
    if parent_role in ("WORKER", "SPECIALIST"):
        raise DelegationError(
            f"Agent '{parent_agent.id}' has role '{parent_role}', which is not authorized to delegate tasks. "
            f"Only ROOT_ORCHESTRATOR, MANAGER, or SUPER_AGENT may delegate."
        )

    # Check direct reporting line or allowed children
    target_parent_id = getattr(target_agent, "parent_id", None)
    allowed_children = getattr(parent_agent, "allowed_child_ids", []) or []

    is_direct_parent = (target_parent_id == parent_agent.id)
    is_allowed_child = (target_agent.id in allowed_children)
    is_root = parent_role in ("ROOT_ORCHESTRATOR", AgentRole.ROOT_ORCHESTRATOR.value)

    if not (is_direct_parent or is_allowed_child or (is_root and not target_parent_id)):
        raise DelegationError(
            f"Agent '{parent_agent.id}' is not authorized to delegate to '{target_agent.id}'. "
            f"'{target_agent.id}' reports to '{target_parent_id}', not '{parent_agent.id}'."
        )
