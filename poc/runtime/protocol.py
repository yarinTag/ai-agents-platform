"""
RuntimeAdapter Protocol and capability abstractions for the AI Agents Platform.

Claude Code is a runtime, not the Agent OS. All runtime backends must implement
this protocol to be used by the platform orchestration layer.
"""

from typing import Protocol, Optional, Callable, Dict, Any, List, runtime_checkable
from dataclasses import dataclass
from config import AgentConfig, ProjectConfig


@dataclass
class RuntimeCapabilities:
    """Declared capabilities of a runtime adapter."""
    supports_streaming: bool
    supports_tool_use: bool
    supports_session_resume: bool
    supports_cancellation: bool
    supports_concurrent: bool
    max_concurrent: Optional[int]
    supported_models: List[str]


@runtime_checkable
class RuntimeAdapter(Protocol):
    """Protocol defining the contract for any AI runtime backend."""

    def start_execution(
        self,
        agent_config: AgentConfig,
        project_config: Optional[ProjectConfig],
        prompt: str,
        session_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> str:
        """
        Start an execution attempt.
        Returns execution_id (unique string identifier for this execution).
        """
        ...

    def get_execution_status(
        self,
        execution_id: str
    ) -> Optional[Any]:
        """Get the current status/run record for an execution."""
        ...

    def cancel_execution(
        self,
        execution_id: str
    ) -> bool:
        """Cancel an in-flight execution."""
        ...

    def subscribe_to_events(
        self,
        execution_id: str,
        handler: Callable[[Dict[str, Any]], None]
    ) -> Callable[[], None]:
        """
        Subscribe to real-time events for an execution.
        Returns an unsubscribe callable.
        """
        ...

    def get_capabilities(self) -> RuntimeCapabilities:
        """Return the runtime's declared capabilities."""
        ...
