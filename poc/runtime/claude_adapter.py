"""
ClaudeCodeAdapter: Implements RuntimeAdapter protocol by wrapping the verified
ClaudeCodeRuntimeAdapter. Preserves all working subprocess and streaming behavior.
"""

from typing import Optional, Callable, Dict, Any
import logging

from config import AgentConfig, ProjectConfig
from runtime_adapter import ClaudeCodeRuntimeAdapter, runtime_adapter as default_claude_adapter
from .protocol import RuntimeAdapter, RuntimeCapabilities

logger = logging.getLogger(__name__)


class ClaudeCodeAdapter:
    """
    Adapter wrapping ClaudeCodeRuntimeAdapter to conform to RuntimeAdapter protocol.
    Does NOT rewrite the verified subprocess management logic.
    """

    def __init__(self, existing_adapter: Optional[ClaudeCodeRuntimeAdapter] = None):
        self._adapter = existing_adapter or default_claude_adapter

    def __getattr__(self, name: str) -> Any:
        """Forward any unknown attributes to the wrapped runtime adapter."""
        return getattr(self._adapter, name)

    def start_execution(
        self,
        agent_config: AgentConfig,
        project_config: Optional[ProjectConfig],
        prompt: str,
        session_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> str:
        """Start task execution using Claude Code subprocess."""
        project_id = project_config.id if project_config else None
        run_id = self._adapter.start_task(
            agent_id=agent_config.id,
            project_id=project_id,
            prompt=prompt,
            session_id=session_id
        )
        logger.info(
            f"ClaudeCodeAdapter started execution {run_id} for agent '{agent_config.id}' "
            f"(correlation: {correlation_id}, task: {task_id})"
        )
        return run_id

    def get_execution_status(self, execution_id: str) -> Optional[Any]:
        """Retrieve execution run status."""
        return self._adapter.get_run_status(execution_id)

    def cancel_execution(self, execution_id: str) -> bool:
        """Cancel execution."""
        return self._adapter.cancel_run(execution_id)

    def subscribe_to_events(
        self,
        execution_id: str,
        handler: Callable[[Dict[str, Any]], None]
    ) -> Callable[[], None]:
        """Subscribe to output stream events for an execution."""
        return self._adapter.subscribe_to_events(execution_id, handler)

    def get_capabilities(self) -> RuntimeCapabilities:
        """Return Claude Code runtime capabilities."""
        return RuntimeCapabilities(
            supports_streaming=True,
            supports_tool_use=True,
            supports_session_resume=True,
            supports_cancellation=True,
            supports_concurrent=True,
            max_concurrent=None,
            supported_models=["default", "sonnet", "opus", "haiku", "fable"]
        )
