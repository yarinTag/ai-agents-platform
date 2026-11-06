"""Shared runtime ceiling applied by existing audited tool/workspace/merge adapters."""
from .policy import decide


def execution_snapshot(db, execution_id):
    from integrations.tool_scopes import execution_context
    context = execution_context(db, execution_id) or {}
    return context.get('governance'), context.get('initiator_id')


def require_capability(db, execution_id, agent, connector, operation, resource_id, *, branch=None, approval_path=False):
    from integrations.tool_definitions import ToolAccessError
    execution = db.get_workflow_execution(execution_id)
    workflow = db.get_workflow(execution.workflow_id) if execution else None
    if not workflow or not workflow.organization_id or not workflow.department_id:
        raise ToolAccessError('Capability execution requires persisted workflow tenant/department scope.')
    from integrations.tool_scopes import execution_context
    context = execution_context(db, execution_id)
    if not context or context.get('workflow_revision', workflow.revision) != workflow.revision:
        raise ToolAccessError('The captured workflow revision or authority context changed.')
    frozen, initiator = execution_snapshot(db, execution_id)
    value = decide(db, workflow.organization_id, workflow.department_id, connector.id,
                   connector.provider.lower() + '.' + operation, resource_id, user_id=initiator,
                   service=initiator is None, agent_id=agent.id, workflow_id=workflow.id,
                   branch=branch, frozen=frozen)
    if value['decision'] == 'denied' or (value['decision'] == 'requires_approval' and not approval_path):
        raise ToolAccessError('Capability policy blocked this action: ' + value['reason'])
    return value
