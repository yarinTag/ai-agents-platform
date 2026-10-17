"""
Runtime domain models for AI Agents Platform.

Defines runtime-agnostic task lifecycle states and execution run models.
These models are independent of any specific model provider or CLI implementation.
"""

from dataclasses import dataclass, asdict, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any


class TaskStatus(str, Enum):
    """Canonical lifecycle states for an agent task run."""
    QUEUED = "queued"
    PENDING = "pending"
    RUNNING = "running"
    SCHEDULED = "scheduled"
    WAITING_FOR_CHILDREN = "waiting_for_children"
    WAITING_FOR_MANAGER = "waiting_for_manager"
    WAITING_FOR_HUMAN = "waiting_for_human"
    WAITING_INPUT = "waiting_input"
    PENDING_APPROVAL = "pending_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class AgentRun:
    """Represents a running or completed agent task execution."""
    run_id: str
    agent_id: str
    project_id: Optional[str]
    prompt: str
    status: TaskStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    result: Optional[str] = None
    error: Optional[str] = None
    exit_code: Optional[int] = None
    events: List[Dict[str, Any]] = field(default_factory=list)
    parent_task_id: Optional[str] = None
    root_task_id: Optional[str] = None
    assigned_by: Optional[str] = None
    session_id: Optional[str] = None
    dangerously_skip_permissions: bool = False
    dependencies: List[str] = field(default_factory=list)
    structured_result: Optional[Dict[str, Any]] = None
    acceptance_criteria: Optional[str] = None
    retry_count: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    cost_usd: float = 0.0
    cost_source: str = "UNKNOWN"
    model: Optional[str] = None
    organization_id: Optional[str] = None

    def __post_init__(self):
        if self.events is None:
            self.events = []
        if self.dependencies is None:
            self.dependencies = []

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat() if self.created_at else None
        if self.started_at:
            data['started_at'] = self.started_at.isoformat()
        if self.ended_at:
            data['ended_at'] = self.ended_at.isoformat()
        data['status'] = self.status.value if hasattr(self.status, 'value') else str(self.status)
        data['parent_task_id'] = self.parent_task_id
        data['root_task_id'] = self.root_task_id
        data['assigned_by'] = self.assigned_by
        data['dangerously_skip_permissions'] = self.dangerously_skip_permissions
        data['dependencies'] = list(self.dependencies) if self.dependencies else []
        data['structured_result'] = self.structured_result
        data['acceptance_criteria'] = self.acceptance_criteria
        data['retry_count'] = self.retry_count
        data['input_tokens'] = self.input_tokens
        data['output_tokens'] = self.output_tokens
        data['cache_read_tokens'] = self.cache_read_tokens
        data['cache_write_tokens'] = self.cache_write_tokens
        data['cost_usd'] = self.cost_usd
        data['cost_source'] = self.cost_source
        data['model'] = self.model
        data['organization_id'] = self.organization_id
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AgentRun':
        status_val = data.get('status', 'queued')
        if isinstance(status_val, str):
            try:
                status = TaskStatus(status_val)
            except ValueError:
                status = TaskStatus.QUEUED
        else:
            status = status_val

        created_at = None
        if data.get('created_at'):
            if isinstance(data['created_at'], str):
                created_at = datetime.fromisoformat(data['created_at'].replace('Z', '+00:00'))
            else:
                created_at = data['created_at']

        started_at = None
        if data.get('started_at'):
            if isinstance(data['started_at'], str):
                started_at = datetime.fromisoformat(data['started_at'].replace('Z', '+00:00'))
            else:
                started_at = data['started_at']

        ended_at = None
        if data.get('ended_at'):
            if isinstance(data['ended_at'], str):
                ended_at = datetime.fromisoformat(data['ended_at'].replace('Z', '+00:00'))
            else:
                ended_at = data['ended_at']

        return cls(
            run_id=data['run_id'],
            agent_id=data['agent_id'],
            project_id=data.get('project_id'),
            prompt=data.get('prompt', ''),
            status=status,
            created_at=created_at or datetime.now(),
            started_at=started_at,
            ended_at=ended_at,
            result=data.get('result'),
            error=data.get('error'),
            exit_code=data.get('exit_code'),
            events=data.get('events') or [],
            parent_task_id=data.get('parent_task_id'),
            root_task_id=data.get('root_task_id'),
            assigned_by=data.get('assigned_by'),
            session_id=data.get('session_id'),
            dangerously_skip_permissions=data.get('dangerously_skip_permissions', False),
            dependencies=data.get('dependencies') or [],
            structured_result=data.get('structured_result'),
            acceptance_criteria=data.get('acceptance_criteria'),
            retry_count=data.get('retry_count', 0),
            input_tokens=data.get('input_tokens', 0) or 0,
            output_tokens=data.get('output_tokens', 0) or 0,
            cache_read_tokens=data.get('cache_read_tokens', 0) or 0,
            cache_write_tokens=data.get('cache_write_tokens', 0) or 0,
            cost_usd=float(data.get('cost_usd', 0.0) or 0.0),
            cost_source=data.get('cost_source', 'UNKNOWN'),
            model=data.get('model'),
            organization_id=data.get('organization_id')
        )
