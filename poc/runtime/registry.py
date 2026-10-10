"""
Runtime Registry for AI Agents Platform.

Maintains available Agent Runtime implementations behind the RuntimeAdapter contract.
The platform defaults to ClaudeCodeRuntime, but this registry allows future runtimes
(e.g., OpenAIRuntime, LocalLLMRuntime) to plug in without modifying Orchestration or A2A layers.
"""

from typing import Dict, Optional, List
import logging

from .protocol import RuntimeAdapter, RuntimeCapabilities

logger = logging.getLogger(__name__)


class RuntimeNotFoundError(ValueError):
    """Raised when a requested runtime adapter is not registered."""
    pass


class RuntimeRegistry:
    """Registry maintaining active and alternative Agent Runtime implementations."""

    def __init__(self):
        self._runtimes: Dict[str, RuntimeAdapter] = {}
        self._default_runtime_name: str = "claude_code"

    def register(self, name: str, adapter: RuntimeAdapter, set_default: bool = False) -> None:
        """Register an adapter under a unique runtime identifier."""
        clean_name = name.strip().lower()
        self._runtimes[clean_name] = adapter
        logger.info(f"Registered agent runtime '{clean_name}' ({adapter.__class__.__name__})")
        if set_default or len(self._runtimes) == 1:
            self._default_runtime_name = clean_name

    def get(self, name: Optional[str] = None) -> RuntimeAdapter:
        """Get a registered runtime adapter by name, or default if omitted."""
        if not name:
            clean_name = self._default_runtime_name
        else:
            clean_name = name.strip().lower()

        adapter = self._runtimes.get(clean_name)
        if not adapter:
            available = list(self._runtimes.keys())
            raise RuntimeNotFoundError(
                f"Runtime '{clean_name}' not found. Available runtimes: {available}"
            )
        return adapter

    def set_default(self, name: str) -> None:
        """Set the platform default runtime name."""
        clean_name = name.strip().lower()
        if clean_name not in self._runtimes:
            raise RuntimeNotFoundError(f"Cannot set default to unregistered runtime '{clean_name}'.")
        self._default_runtime_name = clean_name

    def get_default_name(self) -> str:
        """Get the platform default runtime name."""
        return self._default_runtime_name

    def list_runtimes(self) -> Dict[str, RuntimeCapabilities]:
        """List all registered runtimes and their declared capabilities."""
        return {
            name: adapter.get_capabilities()
            for name, adapter in self._runtimes.items()
        }

    def has(self, name: str) -> bool:
        """Check if a runtime is registered."""
        return name.strip().lower() in self._runtimes


# Global registry singleton
runtime_registry = RuntimeRegistry()
