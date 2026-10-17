"""
Model Policy & Capability Abstraction for AI Agents Platform.

Separates logical intelligence tiers and required capabilities (reasoning, coding, speed)
from specific model names and backend providers.

Agents request a model tier (e.g. tier:architect, tier:worker) or specific capability,
and this layer resolves it to the appropriate model identifier for the active runtime.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


class ModelTier(str, Enum):
    """Logical capability tiers for platform agents."""
    EXECUTIVE = "executive"      # High-reasoning (CEO, planning, multi-agent debate)
    ARCHITECT = "architect"      # Deep technical architecture, schema design, reviews
    DEVELOPER = "developer"      # Core coding, implementation, feature execution
    WORKER = "worker"            # High-throughput subtasks, unit tests, documentation
    FAST = "fast"                # Instant response, triage, lightweight summarization
    DEFAULT = "default"          # Runtime default model


@dataclass
class ModelCapability:
    """Declared capabilities and constraints for a model tier."""
    tier: ModelTier
    description: str
    min_context_window: int
    requires_tools: bool = True
    requires_streaming: bool = True
    requires_reasoning: bool = False
    # Runtime-specific concrete model mappings
    runtime_model_mappings: Dict[str, str] = field(default_factory=dict)
    fallback_models: List[str] = field(default_factory=list)


@dataclass
class ResolvedModel:
    """Result of resolving an agent's model spec against the active runtime."""
    tier: Optional[ModelTier]
    resolved_model: str
    runtime_type: str
    is_tier_mapped: bool
    context_window: int = 200000


class ModelPolicyResolver:
    """
    Resolves agent model preferences (tiers, capabilities, or direct strings)
    to concrete model names for a target runtime backend.
    """

    def __init__(self):
        self._capabilities: Dict[ModelTier, ModelCapability] = {
            ModelTier.EXECUTIVE: ModelCapability(
                tier=ModelTier.EXECUTIVE,
                description="High-capability reasoning for leadership, planning, and war room consensus",
                min_context_window=200000,
                requires_reasoning=True,
                runtime_model_mappings={
                    "claude_code": "claude-3-7-sonnet-20250219",
                    "openai": "o3-mini",
                    "nvidia_nim": "nvidia/nemotron-3-super-120b-a12b",
                },
                fallback_models=["claude-3-5-sonnet-20241022"]
            ),
            ModelTier.ARCHITECT: ModelCapability(
                tier=ModelTier.ARCHITECT,
                description="Deep technical architecture, schema design, and code review",
                min_context_window=200000,
                requires_reasoning=True,
                runtime_model_mappings={
                    "claude_code": "claude-3-7-sonnet-20250219",
                    "openai": "gpt-4o",
                    "nvidia_nim": "meta/llama-3.3-70b-instruct",
                },
                fallback_models=["claude-3-5-sonnet-20241022"]
            ),
            ModelTier.DEVELOPER: ModelCapability(
                tier=ModelTier.DEVELOPER,
                description="General software development, backend and frontend implementation",
                min_context_window=200000,
                requires_tools=True,
                runtime_model_mappings={
                    "claude_code": "claude-3-5-sonnet-20241022",
                    "openai": "gpt-4o",
                    "nvidia_nim": "meta/llama-3.3-70b-instruct",
                },
                fallback_models=["claude-3-5-haiku-20241022"]
            ),
            ModelTier.WORKER: ModelCapability(
                tier=ModelTier.WORKER,
                description="High-throughput subtasks, unit tests, format conversions",
                min_context_window=128000,
                requires_tools=True,
                runtime_model_mappings={
                    "claude_code": "claude-3-5-haiku-20241022",
                    "openai": "gpt-4o-mini",
                    "nvidia_nim": "meta/llama-3.3-70b-instruct",
                },
                fallback_models=["default"]
            ),
            ModelTier.FAST: ModelCapability(
                tier=ModelTier.FAST,
                description="Lightweight and rapid execution for simple queries",
                min_context_window=128000,
                requires_tools=False,
                runtime_model_mappings={
                    "claude_code": "claude-3-5-haiku-20241022",
                    "openai": "gpt-4o-mini",
                    "nvidia_nim": "meta/llama-3.3-70b-instruct",
                },
                fallback_models=["default"]
            ),
            ModelTier.DEFAULT: ModelCapability(
                tier=ModelTier.DEFAULT,
                description="Runtime-configured default model",
                min_context_window=200000,
                runtime_model_mappings={
                    "claude_code": "default",
                    "openai": "default",
                    "nvidia_nim": "default",
                }
            )
        }

    def register_capability(self, capability: ModelCapability) -> None:
        """Register or override a model tier capability profile."""
        self._capabilities[capability.tier] = capability

    def get_capability(self, tier: ModelTier) -> Optional[ModelCapability]:
        """Get capability descriptor for a specific tier."""
        return self._capabilities.get(tier)

    def list_tiers(self) -> List[Dict[str, Any]]:
        """List all available logical model tiers with their metadata."""
        return [
            {
                "id": f"tier:{tier.value}",
                "tier": tier.value,
                "name": f"Tier: {tier.value.title()}",
                "description": cap.description,
                "min_context_window": cap.min_context_window,
                "requires_reasoning": cap.requires_reasoning,
                "requires_tools": cap.requires_tools,
            }
            for tier, cap in self._capabilities.items()
            if tier != ModelTier.DEFAULT
        ]

    def resolve(self, model_spec: Optional[str], runtime_type: str = "claude_code") -> ResolvedModel:
        """
        Resolve an agent's model spec string to a concrete model for the given runtime.

        Handles:
        - "tier:architect" -> mapped model for runtime
        - "architect" -> mapped model for runtime
        - "default" or None -> default model
        - Direct vendor model strings (e.g. "claude-3-5-sonnet") -> passed through directly
        """
        raw_spec = (model_spec or "default").strip()

        # Check for explicit 'tier:' prefix or direct tier name
        tier_candidate = None
        if raw_spec.lower().startswith("tier:"):
            tier_name = raw_spec[5:].strip().lower()
            try:
                tier_candidate = ModelTier(tier_name)
            except ValueError:
                pass
        else:
            try:
                tier_candidate = ModelTier(raw_spec.lower())
            except ValueError:
                pass

        if tier_candidate and tier_candidate in self._capabilities:
            cap = self._capabilities[tier_candidate]
            concrete_model = cap.runtime_model_mappings.get(runtime_type)
            if concrete_model:
                return ResolvedModel(
                    tier=tier_candidate,
                    resolved_model=concrete_model,
                    runtime_type=runtime_type,
                    is_tier_mapped=True,
                    context_window=cap.min_context_window
                )

        # Fallback to direct model pass-through (for backward compatibility)
        return ResolvedModel(
            tier=None,
            resolved_model=raw_spec,
            runtime_type=runtime_type,
            is_tier_mapped=False,
            context_window=200000
        )


# Global singleton instance
model_policy_resolver = ModelPolicyResolver()
