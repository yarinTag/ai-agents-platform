"""Workflow-to-agent boundaries and current queued-run actor admission."""
from .execution_models import UnauthorizedUserDepartmentError


def require_agent_scope(agent, workflow, user_context=None, db=None):
    if not agent:
        return
    organization_id = getattr(workflow, 'organization_id', None)
    if organization_id and getattr(agent, 'organization_id', None) != organization_id:
        raise ValueError('Workflow execution agent is outside its organization')
    department_id = getattr(agent, 'department_id', None)
    workflow_department = getattr(workflow, 'department_id', None)
    if department_id and department_id != workflow_department:
        raise UnauthorizedUserDepartmentError((user_context or {}).get('sub', 'workflow'), department_id,
            'Workflow execution agent is outside the workflow department')
    require_workflow_actor(workflow, user_context, db)


def require_workflow_actor(workflow, user_context=None, db=None):
    """Recheck current account and capped membership before run admission."""
    organization_id = getattr(workflow, "organization_id", None)
    workflow_department = getattr(workflow, "department_id", None)
    if not user_context:
        return  # Scheduler/engine entry points still enforce the stored ownership boundary above.
    if not db:
        raise ValueError('Current database actor verification is required')
    if user_context.get('service') in ('api_key', 'open_development') and user_context.get('org_id') == organization_id:
        return
    user = db.get_user(user_context.get('sub'))
    if not user or user.status != 'ACTIVE' or user.organization_id != organization_id:
        raise ValueError('Workflow actor is no longer active in this organization')
    if user.role == 'ORG_ADMIN':
        return
    if user.role not in ('MANAGER', 'OPERATOR') or not workflow_department:
        raise UnauthorizedUserDepartmentError(user.id, workflow_department, 'Workflow operation permission is required')
    memberships = db.get_user_departments(user.id)
    if not any(row.get('department_id') == workflow_department and row.get('organization_id') == organization_id
               and row.get('department_role') in ('MANAGER', 'OPERATOR', 'ORG_ADMIN') for row in memberships):
        raise UnauthorizedUserDepartmentError(user.id, workflow_department, 'Workflow department permission was revoked')
