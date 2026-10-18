"""
Domain Dataclasses for Persistence Layer.
Separated from DatabaseManager to keep persistence modules concise and reusable.
"""

from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any
import inspect


@dataclass
class AgentMessage:
    """First-class internal agent-to-agent message."""
    id: str
    from_agent_id: str
    to_agent_id: str
    content: str
    task_id: Optional[str] = None
    run_id: Optional[str] = None
    parent_message_id: Optional[str] = None
    message_type: str = "QUESTION"
    status: str = "SENT"
    metadata: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None
    responded_at: Optional[str] = None
    channel_key: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentMessage":
        valid_fields = set(inspect.signature(cls).parameters.keys())
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered)


@dataclass
class MCPConnector:
    """Represents a connected Model Context Protocol server/service."""
    id: str
    name: str
    provider: str
    status: str = "DISCONNECTED"
    configuration: Optional[Dict[str, Any]] = None
    capabilities: Optional[List[str]] = None
    error_message: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MCPTool:
    """An individual tool exposed by an MCP connector."""
    id: str
    connector_id: str
    name: str
    description: str
    input_schema: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MCPToolCall:
    """Historical and active record of an MCP tool invocation."""
    id: str
    connector_id: str
    tool_id: str
    agent_id: str
    task_id: Optional[str] = None
    run_id: Optional[str] = None
    status: str = "STARTED"
    arguments: Optional[Dict[str, Any]] = None
    result: Optional[str] = None
    error: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AgentTeam:
    """A collaborative team of agents coordinated by a manager."""
    id: str
    name: str
    manager_agent_id: str
    project_id: Optional[str] = None
    description: Optional[str] = None
    status: str = "ACTIVE"
    members: Optional[List[Dict[str, Any]]] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Organization:
    """Enterprise tenant organization."""
    id: str
    name: str
    slug: str
    domain: Optional[str] = None
    settings_json: str = "{}"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class User:
    """Enterprise user belonging to an organization."""
    id: str
    organization_id: str
    email: str
    full_name: str
    role: str = "MEMBER"
    status: str = "ACTIVE"
    password_hash: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    last_login_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d.pop("password_hash", None)
        return d


@dataclass
class DepartmentMember:
    """Membership connecting a user to a specific department."""
    id: str
    department_id: str
    user_id: str
    role: str = "OPERATOR"
    joined_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class OrgInvitation:
    """Invitation issued to an email address to join an organization/department."""
    id: str
    organization_id: str
    email: str
    department_id: Optional[str] = None
    role: str = "MEMBER"
    invite_token: str = ""
    expires_at: Optional[str] = None
    status: str = "PENDING"
    created_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Department:
    """Organizational department with budget controls."""
    id: str
    name: str
    description: Optional[str] = None
    monthly_budget_usd: float = 100.0
    current_spend_usd: float = 0.0
    budget_action: str = "REQUIRE_APPROVAL"
    alert_threshold_pct: float = 80.0
    organization_id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DepartmentMCPAccess:
    """Department-level MCP access grant with tool filtering."""
    id: str
    department_id: str
    connector_id: str
    allowed_tools: str = "*"
    organization_id: Optional[str] = None
    is_active: bool = True
    granted_by_user_id: Optional[str] = None
    granted_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Workflow:
    """Autonomous agentic workflow definition."""
    id: str
    name: str
    description: Optional[str] = None
    department_id: Optional[str] = None
    definition_json: str = "{}"
    webhook_enabled: bool = True
    webhook_token: Optional[str] = None
    cron_expression: Optional[str] = None
    is_active: bool = True
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class WorkflowExecution:
    """Single execution instance of a workflow."""
    id: str
    workflow_id: str
    trigger_type: str
    trigger_payload: Optional[str] = None
    status: str = "PENDING"
    department_id: Optional[str] = None
    sandbox_path: Optional[str] = None
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None
    created_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class WorkflowStepRun:
    """Execution record for an individual step within a workflow."""
    id: str
    execution_id: str
    step_key: str
    agent_id: Optional[str] = None
    status: str = "PENDING"
    task_run_id: Optional[str] = None
    input_data: Optional[str] = None
    output_data: Optional[str] = None
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RunEvaluation:
    """Feedback and lesson learned from a workflow execution."""
    id: str
    execution_id: str
    workflow_id: str
    rating: Optional[int] = None
    feedback_notes: Optional[str] = None
    lessons_extracted: Optional[str] = None
    created_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
