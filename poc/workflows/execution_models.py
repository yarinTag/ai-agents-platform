"""Workflow execution results and policy errors."""
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

class BudgetExceededError(Exception):
    """Raised when department monthly budget is exceeded under HARD_STOP policy."""
    def __init__(self, department_id: str, message: str, current_spend: float, budget: float):
        super().__init__(message)
        self.department_id = department_id
        self.current_spend = current_spend
        self.budget = budget


class MCPGovernanceViolationError(Exception):
    """Raised when an MCP connector or tool violates department governance policies."""
    def __init__(self, department_id: str, connector_id: str, reason: str, tool_name: Optional[str] = None):
        super().__init__(reason)
        self.department_id = department_id
        self.connector_id = connector_id
        self.tool_name = tool_name
        self.reason = reason


class UnauthorizedUserDepartmentError(Exception):
    """Raised when an authenticated user attempts to execute a workflow outside their authorized departments."""
    def __init__(self, user_id: str, department_id: str, message: str):
        super().__init__(message)
        self.user_id = user_id
        self.department_id = department_id


@dataclass
class WorkflowStepResult:
    """Result of an individual workflow step execution."""
    step_key: str
    status: str
    task_run_id: str
    output: Optional[str] = None
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    error: Optional[str] = None

