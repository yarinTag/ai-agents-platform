"""Authoritative workflow-to-agent ownership checks, shared by all entry points."""
from .execution_models import UnauthorizedUserDepartmentError


def require_agent_scope(agent, workflow, user_context=None):
    if not agent:
        return
    organization_id = getattr(workflow, "organization_id", None)
    if organization_id and getattr(agent, "organization_id", None) != organization_id:
        raise ValueError("Workflow execution agent is outside its organization")
    department_id = getattr(agent, "department_id", None)
    if not department_id:
        return
    if user_context:
        if user_context.get("role") == "ORG_ADMIN":
            return
        departments = {
            item.get("id") if isinstance(item, dict) else str(item)
            for item in user_context.get("departments", [])
        }
        allowed = department_id in departments
    else:
        allowed = department_id == workflow.department_id
    if not allowed:
        raise UnauthorizedUserDepartmentError(
            (user_context or {}).get("sub", "workflow"), department_id,
            "Workflow execution agent is outside the authorized departments",
        )
