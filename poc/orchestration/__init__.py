"""
Orchestration package for the AI Agents Platform.
"""

from .hierarchy_validator import validate_agent_hierarchy, HierarchyValidationError, DEFAULT_MAX_HIERARCHY_DEPTH

__all__ = ["validate_agent_hierarchy", "HierarchyValidationError", "DEFAULT_MAX_HIERARCHY_DEPTH"]
