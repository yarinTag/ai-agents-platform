"""
RuntimeAdapter Protocol and capability abstractions for the AI Agents Platform.

Claude Code is a runtime implementation, not the Agent OS itself. All runtime backends
must implement this protocol to be plugged into the platform orchestration layer.
"""

from typing import Protocol, Optional, Callable, Dict, Any, List, runtime_checkable
from dataclasses import dataclass
from config import AgentConfig, ProjectConfig
from .models import AgentRun


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
    supports_playground: bool = False


@runtime_checkable
class RuntimeAdapter(Protocol):
    """Protocol defining the contract for any AI runtime backend."""

    def start_task(
        self,
        agent_id: str,
        project_id: Optional[str] = None,
        prompt: Optional[str] = None,
        session_id: Optional[str] = None,
        fork_session: bool = False,
        task_id: Optional[str] = None,
    ) -> str:
        """
        Start a task execution by agent ID or task ID.
        Returns run_id (unique string identifier for this execution).
        """
        ...

    def get_run_status(
        self,
        run_id: str
    ) -> Optional[AgentRun]:
        """Get the current status/run record for a task."""
        ...

    def cancel_run(
        self,
        run_id: str
    ) -> bool:
        """Cancel an in-flight run."""
        ...

    def resume_task(
        self,
        run_id: str,
        answer: str
    ) -> str:
        """Resume a suspended/waiting task run with an operator or supervisor response."""
        ...

    def list_runs(self) -> List[AgentRun]:
        """List all tracked runs."""
        ...

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
        Start an execution attempt using full config objects.
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


@runtime_checkable
class PlaygroundRuntimeAdapter(RuntimeAdapter, Protocol):
    """Optional tool-free extension; ordinary adapters need not implement it."""

    def start_playground_task(self, agent_id: str, task_id: str, prompt: str, workspace: str) -> str:
        """Optional capability: fresh tool-free inference, no external callbacks or escalation."""
        ...
