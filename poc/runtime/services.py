"""Injected integrations used by the subprocess runtime.

Concrete persistence, orchestration and event systems are selected at composition
time. No optional backend service is imported by this contract module.
"""

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Protocol

from config import AgentConfig, ProjectConfig
from .models import AgentRun


class RuntimePersistence(Protocol):
    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]: ...
    def get_agent(self, agent_id: str) -> Optional[AgentConfig]: ...
    def get_project(self, project_id: str) -> Optional[ProjectConfig]: ...
    def get_task_run(self, run_id: str) -> Optional[AgentRun]: ...
    def save_task_run(self, run: AgentRun) -> None: ...
    def get_or_create_conversation(self, agent_id: str, project_id: Optional[str] = None) -> Dict[str, Any]: ...
    def has_chat_message_for_task(self, agent_id: str, task_id: str, sender_type: str,
                                  content: Optional[str] = None) -> bool: ...
    def save_chat_message(self, data: Dict[str, Any]) -> Dict[str, Any]: ...


class RuntimeConfiguration(Protocol):
    def get_agent(self, agent_id: str) -> Optional[AgentConfig]: ...
    def get_project(self, project_id: str) -> Optional[ProjectConfig]: ...


@dataclass
class RuntimeServices:
    """Ports supplied by the application; providers remain lazy for import safety.

    emit accepts EventService.emit keyword arguments. publish_chat receives the
    run and the persisted assistant message. supervisor accepts the existing
    resolve_or_escalate_question keyword contract. Missing supervisor support
    leaves a question waiting for input; it never implies completion.
    """

    database: Callable[[], RuntimePersistence]
    configuration: Callable[[], RuntimeConfiguration]
    resolve_model: Callable[[str], str]
    skills_prompt: Callable[[List[str]], str]
    capture_session: Callable[[AgentRun, str], None]
    emit: Optional[Callable[..., Any]] = None
    publish_chat: Optional[Callable[[AgentRun, Dict[str, Any]], None]] = None
    supervisor: Optional[Callable[..., Dict[str, Any]]] = None
    complete: Optional[Callable[[AgentRun], None]] = None
