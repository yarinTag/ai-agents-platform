"""Policy edit authority: organization ceiling, exact resources, restrictive managers."""
from .registry import capability, configured_resources
from .models import PolicyDocument


def validate_document(db, actor, document, scope_type, scope_id, previous):
    if not actor.user_id:
        raise PermissionError('A current personal organization administrator or manager is required.')
    if scope_type == 'organization' and not actor.admin:
        raise PermissionError('Only organization administrators can edit the organization ceiling.')
    if not actor.admin:
        actor.require(scope_id, 3)
        old = PolicyDocument.model_validate(previous['document'])
        old_rules = {rule.id: rule.model_dump() for rule in old.rules}
        new_rules = {rule.id: rule.model_dump() for rule in document.rules}
        if old.default != document.default or any(new_rules.get(key) != value for key, value in old_rules.items()):
            raise PermissionError('Managers may append restrictions, not remove or change existing policy or its default.')
        if any(rule.effect == 'allow' for rule in document.rules if rule.id not in old_rules):
            raise PermissionError('Managers cannot add allow grants. Ask the organization administrator.')
    for rule in document.rules:
        cap = capability(rule.capability_id)
        if not cap or not cap.implemented or cap.resource_type != rule.resource_type:
            raise ValueError('Policy references an unimplemented capability or wrong resource type.')
        connector = db.get_mcp_connector(rule.connector_id)
        if not connector or connector.organization_id != actor.organization_id:
            raise ValueError('Policy connector is outside the current organization.')
        if not actor.admin:
            grant = db.get_department_mcp_access(scope_id, rule.connector_id)
            if not grant or not grant.is_active or grant.organization_id not in (None, actor.organization_id):
                raise PermissionError('Managers may restrict only connectors currently granted to their department.')
        if not set(rule.resource_ids) <= set(configured_resources(connector, cap)):
            raise ValueError('Policy resources must be exact currently configured resource identifiers.')
        if rule.branches and (cap.provider != 'github' or cap.operation not in ('clone_repository', 'open_pull_request')):
            raise ValueError('Branch constraints are supported only by repository workspace capabilities.')
        for identifier in rule.user_ids:
            user = db.get_user(identifier)
            if not user or user.organization_id != actor.organization_id:
                raise ValueError('Policy user selector is outside the organization.')
            if scope_type == 'department' and user.role != 'ORG_ADMIN' and not any(
                    m['department_id'] == scope_id and m['organization_id'] == actor.organization_id
                    for m in db.get_user_departments(identifier)):
                raise ValueError('Policy user selector is outside the department.')
        for kind, identifiers in (('agent', rule.agent_ids), ('workflow', rule.workflow_ids)):
            for identifier in identifiers:
                record = getattr(db, 'get_' + kind)(identifier)
                if (not record or record.organization_id != actor.organization_id or
                        (scope_type == 'department' and record.department_id not in (None, scope_id))):
                    raise ValueError('Policy selector is outside the authorized scope.')
