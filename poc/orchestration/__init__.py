"""
Orchestration package for the AI Agents Platform.
"""

from .hierarchy_validator import (
    validate_agent_hierarchy, HierarchyValidationError, DEFAULT_MAX_HIERARCHY_DEPTH,
    validate_agent_communication, CommunicationAuthorizationError
)
from .engine import OrchestrationEngine, DelegationError, ConcurrencyLimitExceededError
from .supervisor_resolver import SupervisorResolver
from .project_intelligence import ProjectIntelligence
from .code_indexer import CodeIndexer, code_indexer
from .team_coordinator import TeamCoordinator

__all__ = [
    "validate_agent_hierarchy",
    "HierarchyValidationError",
    "DEFAULT_MAX_HIERARCHY_DEPTH",
    "validate_agent_communication",
    "CommunicationAuthorizationError",
    "OrchestrationEngine",
    "DelegationError",
    "ConcurrencyLimitExceededError",
    "SupervisorResolver",
    "ProjectIntelligence",
    "CodeIndexer",
    "code_indexer",
    "TeamCoordinator"
]

