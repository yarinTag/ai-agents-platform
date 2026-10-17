"""
Runtime package exposing RuntimeAdapter protocol and real implementations.
Zero mocks.
"""

from .protocol import RuntimeAdapter, RuntimeCapabilities
from .models import TaskStatus, AgentRun
from .model_policy import ModelPolicyResolver, ModelTier, ModelCapability, model_policy_resolver
from .registry import RuntimeRegistry, runtime_registry

__all__ = [
    "RuntimeAdapter",
    "RuntimeCapabilities",
    "TaskStatus",
    "AgentRun",
    "ModelPolicyResolver",
    "ModelTier",
    "ModelCapability",
    "model_policy_resolver",
    "RuntimeRegistry",
    "runtime_registry",
]
