"""Public orchestration contracts; optional implementations load on demand."""

from importlib import import_module
from .hierarchy_validator import (
    validate_agent_hierarchy, HierarchyValidationError, DEFAULT_MAX_HIERARCHY_DEPTH,
    validate_agent_communication, CommunicationAuthorizationError,
)

_IMPLEMENTATIONS = {
    "OrchestrationEngine": ("engine", "OrchestrationEngine"),
    "DelegationError": ("engine", "DelegationError"),
    "ConcurrencyLimitExceededError": ("engine", "ConcurrencyLimitExceededError"),
    "SupervisorResolver": ("supervisor_resolver", "SupervisorResolver"),
    "ProjectIntelligence": ("project_intelligence", "ProjectIntelligence"),
    "CodeIndexer": ("code_indexer", "CodeIndexer"),
    "code_indexer": ("code_indexer", "code_indexer"),
    "TeamCoordinator": ("team_coordinator", "TeamCoordinator"),
}

__all__ = [
    "validate_agent_hierarchy", "HierarchyValidationError",
    "DEFAULT_MAX_HIERARCHY_DEPTH", "validate_agent_communication",
    "CommunicationAuthorizationError", *_IMPLEMENTATIONS,
]


def __getattr__(name):
    if name not in _IMPLEMENTATIONS:
        raise AttributeError(name)
    module, attribute = _IMPLEMENTATIONS[name]
    value = getattr(import_module('.' + module, __name__), attribute)
    globals()[name] = value
    return value
