"""
Typed Event models for the AI Agents Office Platform.

Defines all platform event types and the canonical PlatformEvent structure
with correlation IDs and monotonic global sequence numbering.
"""

from enum import Enum
from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import Optional, Dict, Any
import uuid


class EventType(str, Enum):
    # Agent lifecycle
    AGENT_CREATED = "agent.created"
    AGENT_UPDATED = "agent.updated"
    AGENT_DELETED = "agent.deleted"

    # Task lifecycle
    TASK_CREATED = "task.created"
    TASK_ASSIGNED = "task.assigned"
    TASK_QUEUED = "task.queued"
    TASK_STARTED = "task.started"
    TASK_DELEGATED = "task.delegated"
    TASK_DELETED = "task.deleted"

    # Execution events
    EXECUTION_STARTED = "execution.started"
    EXECUTION_THOUGHT = "execution.thought"
    EXECUTION_TOOL_START = "execution.tool.start"
    EXECUTION_TOOL_END = "execution.tool.end"
    EXECUTION_OUTPUT = "execution.output"

    # Task completion & status
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"
    TASK_CANCELLED = "task.cancelled"

    # Result flow
    RESULT_SUBMITTED = "result.submitted"
    RESULT_FORWARDED = "result.forwarded"

    # Human Approvals
    APPROVAL_REQUIRED = "approval.required"
    APPROVAL_GRANTED = "approval.granted"
    APPROVAL_DENIED = "approval.denied"


@dataclass
class PlatformEvent:
    """
    Canonical platform event. Every important state transition produces a PlatformEvent.
    """
    event_type: str
    payload: Dict[str, Any]
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    sequence_number: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    agent_id: Optional[str] = None
    task_id: Optional[str] = None
    execution_id: Optional[str] = None
    parent_task_id: Optional[str] = None
    project_id: Optional[str] = None
    correlation_id: Optional[str] = None
    source: str = "platform"

    @property
    def id(self) -> str:
        """Alias for event_id to match database primary key naming."""
        return self.event_id

    def to_dict(self) -> Dict[str, Any]:
        """Serialize event to a JSON-compatible dictionary."""
        data = asdict(self)
        if isinstance(self.event_type, Enum):
            data["event_type"] = self.event_type.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlatformEvent":
        """Deserialize from dictionary."""
        d = dict(data)
        if "id" in d and "event_id" not in d:
            d["event_id"] = d.pop("id")
        return cls(**d)

