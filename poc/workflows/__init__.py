"""
Workflow Engine Package:
Orchestrates multi-agent workflows defined via YAML/JSON, with steps executed
through OrchestrationEngine, sandbox management, department budget enforcement,
and webhook triggers.
"""

from .parser import WorkflowParser, WorkflowDefinition, WorkflowStepDefinition
from .sandbox import SandboxManager, SandboxSession
from .execution_models import WorkflowStepResult

def __getattr__(name):
    if name != "WorkflowEngine":
        raise AttributeError(name)
    from .engine import WorkflowEngine
    return WorkflowEngine

__all__ = [
    "WorkflowParser",
    "WorkflowDefinition",
    "WorkflowStepDefinition",
    "SandboxManager",
    "SandboxSession",
    "WorkflowEngine",
    "WorkflowStepResult",
]
