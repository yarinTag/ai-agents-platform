"""Narrow legacy authoring projections without granting new operations/resources."""
from .policy import decide


def narrow_catalog(db, user, department_id, connectors, agents):
    for connector in connectors:
        identifier = connector['id']
        values = connector['repositories'] if connector['provider'] == 'github' else connector['channels']
        families = (('tools', 'resources_by_tool', False),
                    ('workspace_operations', 'resources_by_workspace_operation', False),
                    ('server_operations', 'resources_by_server_operation', True))
        for field, resource_field, approval_path in families:
            resource_map = {}
            for operation in connector[field]:
                selected = []
                for resource in values:
                    value = decide(db, user.organization_id, department_id, identifier,
                                   connector['provider'] + '.' + operation, resource,
                                   user_id=user.id, purpose='authoring')
                    if value['decision'] == 'allowed' or (approval_path and value['decision'] == 'requires_approval'):
                        selected.append(resource)
                if selected:
                    resource_map[operation] = selected
            connector[field] = list(resource_map)
            connector[resource_field] = resource_map
        connector['tool_capabilities'] = {operation: description for operation, description in connector['tool_capabilities'].items()
                                         if operation in connector['tools']}
        connector['execution_supported'] = connector['execution_supported'] and bool(connector['tools'])
        for agent in agents:
            actual_id = agent['id'] if not agent.get('provision_on_create') else None
            resources = agent.setdefault('capability_resources', {}).setdefault(identifier, {})
            for field, resource_field, approval_path in families:
                agent_field = 'connector_tools' if field == 'tools' else field
                old = agent.get(agent_field, {}).get(identifier, [])
                permitted = []
                for operation in old:
                    selected = []
                    for resource in connector[resource_field].get(operation, []):
                        value = decide(db, user.organization_id, department_id, identifier,
                                       connector['provider'] + '.' + operation, resource,
                                       user_id=user.id, agent_id=actual_id, purpose='authoring')
                        if value['decision'] == 'allowed' or (approval_path and value['decision'] == 'requires_approval'):
                            selected.append(resource)
                    if selected:
                        resources[operation] = selected
                        permitted.append(operation)
                agent[agent_field][identifier] = permitted
    return connectors


def reference_allowed(connector, operation, resource, family='resources_by_tool'):
    # Older fixtures/catalogs are accepted only when the new projection is absent.
    return family not in connector or resource in connector[family].get(operation, [])
