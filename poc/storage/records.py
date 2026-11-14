"""Persistence records shared by repositories and API compatibility exports."""
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional

class Record:
    """Shared dataclass serialization; specialized public projections may override."""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AgentMessage(Record):
    """First-class internal agent-to-agent message."""
    id: str
    from_agent_id: str
    to_agent_id: str
    content: str
    task_id: Optional[str] = None
    run_id: Optional[str] = None
    parent_message_id: Optional[str] = None
    message_type: str = "QUESTION"  # QUESTION, ANSWER, REQUEST, DELEGATION, STATUS, RESULT, HANDOFF
    status: str = "SENT"  # SENT, DELIVERED, READ, ANSWERED, FAILED
    metadata: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None
    responded_at: Optional[str] = None
    channel_key: Optional[str] = None


    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AgentMessage':
        import inspect
        valid_fields = set(inspect.signature(cls).parameters.keys())
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered)

@dataclass
class MCPConnector(Record):
    """Represents a connected Model Context Protocol server/service."""
    id: str
    name: str
    provider: str
    status: str = "DISCONNECTED"  # CONNECTED, DISCONNECTED, ERROR
    configuration: Optional[Dict[str, Any]] = None
    capabilities: Optional[List[str]] = None
    error_message: Optional[str] = None
    organization_id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass
class MCPTool(Record):
    """An individual tool exposed by an MCP connector."""
    id: str
    connector_id: str
    name: str
    description: str
    input_schema: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None


@dataclass
class MCPToolCall(Record):
    """Historical and active record of an MCP tool invocation."""
    id: str
    connector_id: str
    tool_id: str
    agent_id: str
    task_id: Optional[str] = None
    run_id: Optional[str] = None
    status: str = "STARTED"  # STARTED, COMPLETED, FAILED
    arguments: Optional[Dict[str, Any]] = None
    result: Optional[str] = None
    error: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


@dataclass
class AgentTeam(Record):
    """A collaborative team of agents coordinated by a manager."""
    id: str
    name: str
    manager_agent_id: str
    project_id: Optional[str] = None
    description: Optional[str] = None
    status: str = "ACTIVE"  # ACTIVE, COMPLETED, DISBANDED
    members: Optional[List[Dict[str, Any]]] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass
class Organization(Record):
    """Enterprise tenant organization."""
    id: str
    name: str
    slug: str
    domain: Optional[str] = None
    settings_json: str = "{}"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    plugins_source_mode: str = "local"
    plugins_git_repo: Optional[str] = None
    plugins_local_path: Optional[str] = None


@dataclass
class User:
    """Enterprise user belonging to an organization."""
    id: str
    organization_id: str
    email: str
    full_name: str
    role: str = "MEMBER"  # ORG_ADMIN, DEPT_ADMIN, MEMBER, AUDITOR
    status: str = "ACTIVE"  # ACTIVE, PENDING, SUSPENDED
    password_hash: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    last_login_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d.pop("password_hash", None)
        return d

@dataclass
class DepartmentMember(Record):
    """Membership connecting a user to a specific department."""
    id: str
    department_id: str
    user_id: str
    role: str = "OPERATOR"  # MANAGER, OPERATOR, VIEWER
    joined_at: Optional[str] = None


@dataclass
class OrgInvitation(Record):
    """Invitation issued to an email address to join an organization/department."""
    id: str
    organization_id: str
    email: str
    department_id: Optional[str] = None
    role: str = "MEMBER"
    invite_token: str = ""
    expires_at: Optional[str] = None
    status: str = "PENDING"  # PENDING, ACCEPTED, EXPIRED, REVOKED
    created_at: Optional[str] = None


@dataclass
class Department(Record):
    """Organizational department with budget controls."""
    id: str
    name: str
    description: Optional[str] = None
    monthly_budget_usd: float = 100.0
    current_spend_usd: float = 0.0
    budget_action: str = "REQUIRE_APPROVAL"  # HARD_STOP, REQUIRE_APPROVAL, NOTIFY_ONLY
    alert_threshold_pct: float = 80.0
    organization_id: Optional[str] = None
    parent_department_id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass
class DepartmentMCPAccess(Record):
    """Department-level MCP access grant with tool filtering."""
    id: str
    department_id: str
    connector_id: str
    allowed_tools: str = "*"
    organization_id: Optional[str] = None
    is_active: bool = True
    granted_by_user_id: Optional[str] = None
    granted_at: Optional[str] = None


@dataclass
class Workflow(Record):
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
    organization_id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    revision: int = 1


@dataclass
class WorkflowExecution(Record):
    """Single execution instance of a workflow."""
    id: str
    workflow_id: str
    trigger_type: str  # WEBHOOK, CRON, MANUAL, META_ORCHESTRATOR
    trigger_payload: Optional[str] = None
    status: str = "PENDING"  # PENDING, RUNNING, WAITING_APPROVAL, COMPLETED, FAILED, CANCELLED
    department_id: Optional[str] = None
    sandbox_path: Optional[str] = None
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None
    created_at: Optional[str] = None
    payload_hash: Optional[str] = None


@dataclass
class WorkflowStepRun(Record):
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


@dataclass
class RunEvaluation(Record):
    """Feedback and lesson learned from a workflow execution."""
    id: str
    execution_id: str
    workflow_id: str
    rating: Optional[int] = None
    feedback_notes: Optional[str] = None
    lessons_extracted: Optional[str] = None
    created_at: Optional[str] = None



class WorkflowRevisionConflict(ValueError):
    """A workflow was edited after the caller loaded its base revision."""

