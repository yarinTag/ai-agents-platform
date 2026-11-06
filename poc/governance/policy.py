"""Provider-neutral decisions: legacy ceiling AND frozen/current typed policy layers."""
from datetime import datetime, timezone
from .models import PolicyDocument, timestamp
from .registry import capability, configured_resources
from .store import capture

RANK = {'MEMBER': 1, 'OPERATOR': 2, 'MANAGER': 3, 'ORG_ADMIN': 4}


def _result(state, reason, revisions=None):
    return {'decision': state, 'reason': reason, 'non_executable': True, 'policy_revisions': revisions or []}


def _role(db, organization_id, department_id, user_id, service):
    if service and not user_id:
        return 4
    user = db.get_user(user_id) if user_id else None
    if not user or user.status != 'ACTIVE' or user.organization_id != organization_id:
        return 0
    if user.role == 'ORG_ADMIN':
        return 4
    membership = next((m for m in db.get_user_departments(user_id) if m['department_id'] == department_id
                       and m['organization_id'] == organization_id), {})
    return min(RANK.get(user.role, 0), RANK.get(membership.get('department_role'), 0))


def _layer(document, context, when):
    policy = PolicyDocument.model_validate(document)
    matched = []
    for rule in policy.rules:
        if (rule.capability_id != context['capability_id'] or rule.connector_id != context['connector_id']
                or rule.resource_type != context['resource_type'] or context['resource_id'] not in rule.resource_ids):
            continue
        if rule.not_before and when < timestamp(rule.not_before):
            continue
        if rule.expires_at and when >= timestamp(rule.expires_at):
            continue
        applies = True
        for selector, key in ((rule.user_ids, 'user_id'), (rule.agent_ids, 'agent_id'), (rule.workflow_ids, 'workflow_id'), (rule.branches, 'branch')):
            if selector and context.get(key) not in selector:
                # Missing execution identity cannot evade a targeted restriction.
                if context.get(key) is not None or rule.effect == 'allow':
                    applies = False
                    break
        if applies:
            matched.append(rule.effect)
    if 'deny' in matched:
        return 'denied'
    if policy.default == 'deny' and 'allow' not in matched:
        return 'denied'
    return 'requires_approval' if 'require_approval' in matched else 'allowed'


def decide(db, organization_id, department_id, connector_id, capability_id, resource_id, *,
           user_id=None, agent_id=None, workflow_id=None, purpose='execution', service=False,
           branch=None, frozen=None):
    cap = capability(capability_id)
    if not cap or not cap.implemented:
        return _result('denied', 'CAPABILITY_NOT_IMPLEMENTED')
    department = db.get_department(department_id) if department_id else None
    connector = db.get_mcp_connector(connector_id)
    if (not department or department.organization_id != organization_id or not connector
            or connector.organization_id != organization_id):
        return _result('denied', 'RESOURCE_OUTSIDE_SCOPE')
    rank = _role(db, organization_id, department_id, user_id, service)
    if rank < (1 if purpose == 'authoring' else 2):
        return _result('denied', 'CURRENT_ROLE_REQUIRED')
    if connector.status != 'CONNECTED' or connector.provider.lower() != cap.provider:
        return _result('denied', 'CONNECTOR_UNAVAILABLE')
    if resource_id not in configured_resources(connector, cap):
        return _result('denied', 'RESOURCE_NOT_CONFIGURED')
    from integrations.tool_definitions import require_credentials, ToolAccessError
    try:
        require_credentials(connector)
    except ToolAccessError:
        return _result('denied', 'CREDENTIALS_NOT_CONFIGURED')
    grant = db.get_department_mcp_access(department_id, connector_id)
    if not grant or not grant.is_active or grant.organization_id not in (None, organization_id):
        return _result('denied', 'LEGACY_CEILING_DENIED')
    permission = db.check_department_mcp_permission(department_id, connector_id, cap.operation)
    if not permission.get('allowed') or (cap.effect != 'read' and '*' in (permission.get('allowed_tools') or [])):
        # Existing channel-send wildcard behavior is not broadened, but remains compatible.
        if not (cap.resource_type == 'channel' and permission.get('allowed')):
            return _result('denied', 'EXPLICIT_CAPABILITY_GRANT_REQUIRED')
    agent = db.get_agent(agent_id) if agent_id else None
    if agent_id:
        if not agent or agent.organization_id != organization_id or agent.department_id not in (None, department_id):
            return _result('denied', 'AGENT_OUTSIDE_SCOPE')
        from integrations.tool_scopes import agent_tool_allowed
        tools = [tool for tool in db.list_mcp_tools(connector_id) if tool.name == cap.operation]
        if agent.mcp_permissions or db.get_agent_mcp_permissions(agent.id):
            if not any(agent_tool_allowed(db, agent, connector, tool) for tool in tools):
                return _result('denied', 'AGENT_CAPABILITY_DENIED')
    if workflow_id:
        workflow = db.get_workflow(workflow_id)
        if not workflow or workflow.organization_id != organization_id or workflow.department_id != department_id:
            return _result('denied', 'WORKFLOW_OUTSIDE_SCOPE')
    if purpose == 'execution' and not db.check_department_budget(department_id).get('allowed'):
        return _result('denied', 'DEPARTMENT_BUDGET_DENIED')
    context = {'capability_id': capability_id, 'connector_id': connector_id, 'resource_id': resource_id,
               'resource_type': cap.resource_type, 'user_id': user_id, 'agent_id': agent_id,
               'workflow_id': workflow_id, 'branch': branch}
    current = capture(db, organization_id, department_id)
    layers = [('current', current)]
    if frozen is not None:
        if frozen.get('organization_id') != organization_id or frozen.get('department_id') != department_id:
            return _result('denied', 'FROZEN_SCOPE_MISMATCH')
        layers.append(('frozen', frozen))
    approval = cap.approval_required
    revisions = []
    for source, snapshot in layers:
        when = timestamp(snapshot['captured_at'])
        for record in snapshot['policies']:
            revisions.append({'source': source, 'scope_type': record['scope_type'], 'revision': record['revision']})
            result = _layer(record['document'], context, when)
            if result == 'denied':
                return _result('denied', 'POLICY_DENIED', revisions)
            approval |= result == 'requires_approval'
    return _result('requires_approval' if approval else 'allowed',
                   'APPROVAL_REQUIRED' if approval else 'WITHIN_CURRENT_AND_CAPTURED_SCOPE', revisions)
