"""Authoring projection of existing governed repository workspace permissions."""
from types import SimpleNamespace
from integrations.repo_workspace import OPERATIONS, _tool, workspace_configuration
from integrations.tool_scopes import agent_tool_allowed


def workspace_operations(db, connector, department_id):
    if connector.provider.lower() != 'github':
        return []
    allowed = []
    for operation in OPERATIONS:
        _tool(db, connector, operation)  # Register permission metadata, never a grant or model tool.
        permission = db.check_department_mcp_permission(department_id, connector.id, operation)
        if permission.get('allowed') and not (operation == 'open_pull_request' and
                                             '*' in (permission.get('allowed_tools') or [])):
            allowed.append(operation)
    return allowed


def agent_workspace_operations(db, agent, connector, operations):
    return [operation for operation in operations if agent_tool_allowed(db, agent, connector, _tool(db, connector, operation))]


def validate_workspace(step, agents, connectors):
    errors = []
    config = step.workspace
    if step.required_outcome == 'pull_request' and (config is None or config.mode != 'write'):
        errors.append(f'Step {step.key} requires a write repository workspace to produce a pull request.')
    if config is None:
        return errors
    if step.resources or step.send_output_of:
        errors.append(f'Step {step.key}: repository workspaces cannot be mixed with connector tools or delivery actions.')
    try:
        workspace_configuration(SimpleNamespace(params={'workspace': config.model_dump()}, mcp_servers=[]))
    except ValueError as exc:
        errors.append(str(exc))
    connector = connectors.get(config.connector_id, {})
    if connector.get('provider') != 'github' or config.repository not in connector.get('repositories', []):
        errors.append(f'Step {step.key} requires an approved GitHub workspace repository.')
    required = {'clone_repository'} | ({'open_pull_request'} if config.mode == 'write' else set())
    available = set(connector.get('workspace_operations', []))
    assigned = set(agents.get(step.agent_id, {}).get('workspace_operations', {}).get(config.connector_id, []))
    from governance.catalog import reference_allowed
    if any(not reference_allowed(connector, operation, config.repository, 'resources_by_workspace_operation') for operation in required):
        errors.append(f'Step {step.key} repository workspace is denied by capability policy.')
    combinations = agents.get(step.agent_id, {}).get('capability_resources', {}).get(config.connector_id)
    if combinations is not None and any(config.repository not in combinations.get(operation, []) for operation in required):
        errors.append(f'Step {step.key} agent workspace scope is denied by capability policy.')
    if not required <= available or not required <= assigned:
        errors.append(f'Step {step.key} requires granted workspace operations: {", ".join(sorted(required))}. '
                      'An administrator must grant these explicitly; read-only GitHub tools cannot create PRs.')
    return errors
