"""Server-owned workflow tool scopes. No prompt/model argument can supply identity."""
import hashlib
import json
from datetime import datetime, timedelta
from .tool_definitions import OPERATIONS, ToolAccessError, ensure_tools, require_credentials, resource_values, valid_channel, valid_repository


def require_initiator(db, user_id, organization_id, department_id):
    if not user_id:  # Explicit scheduled/webhook service execution, still tenant/department scoped.
        return
    user = db.get_user(user_id)
    if not user or user.status != 'ACTIVE' or user.organization_id != organization_id:
        raise ToolAccessError('The workflow initiator is no longer authorized.')
    if user.role != 'ORG_ADMIN' and not any(m['department_id'] == department_id and
            m['organization_id'] == organization_id and m['department_role'] in ('MANAGER', 'OPERATOR')
            for m in db.get_user_departments(user_id)):
        raise ToolAccessError('The workflow initiator no longer has execution access to this department.')


def connector_authorized(db, connector_id, organization_id, department_id, agent):
    connector = db.get_mcp_connector(connector_id)
    if not connector or connector.organization_id != organization_id or connector.status != 'CONNECTED':
        raise ToolAccessError('The workflow connector is unavailable in this organization.')
    grant = db.get_department_mcp_access(department_id, connector_id)
    if not grant or not grant.is_active or grant.organization_id not in (None, organization_id):
        raise ToolAccessError('The department has no active grant for this connector.')
    return connector


def agent_tool_allowed(db, agent, connector, tool):
    """Explicit agent restrictions intersect workflow/department grants; skip flags never bypass them."""
    config = agent.mcp_permissions or []
    rows = db.get_agent_mcp_permissions(agent.id)
    if not config and not rows:
        return True  # The explicit governed workflow step delegates only its declared scope.
    identifiers = (connector.id.casefold(), connector.provider.casefold())
    allowed = {'*', 'all'}
    for identifier in identifiers:
        allowed.update((identifier, identifier + '.*', identifier + '.' + tool.name.casefold()))
    if any(isinstance(value, str) and value.casefold() in allowed for value in config):
        return True
    return any(row['connector_id'] == connector.id and row.get('tool_id') in (None, tool.id, tool.name) for row in rows)


def prepare_scope(db, task_id, execution_id, step, initiator_id=None, persist=True):
    """Freeze the step's declared upper bound before launching its model process."""
    context = execution_context(db, execution_id)
    if not context and not step.mcp_servers:
        return
    execution = db.get_workflow_execution(execution_id)
    workflow = db.get_workflow(execution.workflow_id) if execution else None
    agent = db.get_agent(step.agent_id)
    if not workflow or not workflow.organization_id or not workflow.department_id or not agent:
        raise ToolAccessError('Connector execution requires an organization, department and configured agent.')
    if execution.trigger_type == 'PLAYGROUND':
        raise ToolAccessError('Playground cannot receive connector tools.')
    if not context:
        raise ToolAccessError('Workflow connector execution context is missing.')
    initiator_id = context.get('initiator_id')
    if agent.organization_id != workflow.organization_id or agent.department_id not in (None, workflow.department_id):
        raise ToolAccessError('Execution agent is outside this workflow department.')
    require_initiator(db, initiator_id, workflow.organization_id, workflow.department_id)
    references = step.params.get('authorized_resources') if isinstance(step.params, dict) else None
    if references is not None and (not isinstance(references, list) or any(not isinstance(r, dict) for r in references)):
        raise ToolAccessError('Invalid declared workflow resource scope.')
    if any(r.get('connector_id') not in step.mcp_servers for r in references or []):
        raise ToolAccessError('Resource reference is outside the step connector scope.')
    entries = []
    identifiers = set(step.mcp_servers)
    if references is not None:
        # Older builders copied every allowed connector into every step. Explicit
        # resource references narrow that superset; they never authorize extra sends.
        identifiers.intersection_update(r.get('connector_id') for r in references)
    for identifier in sorted(identifiers):
        connector = connector_authorized(db, identifier, workflow.organization_id, workflow.department_id, agent)
        provider = connector.provider.lower()
        if provider not in OPERATIONS:
            raise ToolAccessError(f'Connector provider {provider} has no governed runtime implementation.')
        require_credentials(connector)
        existing = ensure_tools(db, connector)
        config = connector.configuration or {}
        group = 'repositories' if provider == 'github' else 'channels'
        permitted = set(resource_values(config, group))
        refs = [r for r in references or [] if r.get('connector_id') == identifier]
        field = 'repository' if provider == 'github' else 'channel_id'
        selected = {r[field] for r in refs if r.get(field)} if references is not None else permitted
        if not selected or not selected <= permitted:
            raise ToolAccessError(f'No explicit authorized {group} are configured for connector {identifier}.')
        if any(not (valid_repository(value) if provider == 'github' else valid_channel(provider, value)) for value in selected):
            raise ToolAccessError('Use exact owner/repo names and real channel IDs; display-name aliases are not executable targets.')
        requested = {r['tool_name'] for r in refs if r.get('tool_name')}
        legacy = step.params.get('tools') or step.params.get('mcp_tools') or []
        if legacy:
            requested.update([legacy] if isinstance(legacy, str) else legacy)
        if requested - set(existing):
            raise ToolAccessError('The step requests a connector tool that has no runtime implementation.')
        available = []
        for operation, tool in existing.items():
            if requested and operation not in requested:
                continue
            if not db.check_department_mcp_permission(workflow.department_id, identifier, operation)['allowed']:
                continue
            if not agent_tool_allowed(db, agent, connector, tool):
                continue
            suffix = hashlib.sha256(f'{identifier}:{operation}'.encode()).hexdigest()[:24]
            available.append({'name': operation + '_' + suffix, 'operation': operation, 'tool_id': tool.id,
                'connector_id': identifier, 'provider': provider,
                'required_operation': bool(requested),
                'repositories': sorted(selected) if provider == 'github' else [],
                'channels': sorted(selected) if provider != 'github' else []})
        if not available or requested - {e['operation'] for e in available}:
            raise ToolAccessError('Required connector tools are not granted to this department. Update the tool whitelist before execution.')
        entries.extend(available)
    scope = {'organization_id': workflow.organization_id, 'department_id': workflow.department_id,
        'agent_id': agent.id, 'workflow_id': workflow.id, 'initiator_id': initiator_id, 'entries': entries,
        'deadline_at': (datetime.now() + timedelta(seconds=min(step.timeout_seconds or 180, 300))).isoformat()}
    if not persist:
        return scope
    with db._get_connection() as conn:
        conn.execute('INSERT INTO workflow_tool_scopes(task_id, execution_id, scope_json) VALUES (?, ?, ?)',
                     (task_id, execution_id, json.dumps(scope)))


def load_scope(db, task_id):
    with db._get_connection() as conn:
        row = conn.execute('SELECT execution_id,scope_json FROM workflow_tool_scopes WHERE task_id=?', (task_id,)).fetchone()
    if not row:
        return None
    value = json.loads(row['scope_json'])
    value['execution_id'] = row['execution_id']
    return value


def live_scope(db, task_id, frozen):
    task = db.get_task_run(task_id)
    execution = db.get_workflow_execution(frozen['execution_id'])
    workflow = db.get_workflow(frozen['workflow_id'])
    agent = db.get_agent(frozen['agent_id'])
    state = str(getattr(task.status, 'value', task.status)).lower() if task else ''
    if (state != 'running' or not execution or execution.status != 'RUNNING' or execution.trigger_type == 'PLAYGROUND'
            or frozen['deadline_at'] <= datetime.now().isoformat()):
        raise ToolAccessError('Connector scope is expired, cancelled or no longer running.')
    organization_id, department_id = frozen['organization_id'], frozen['department_id']
    if (not workflow or workflow.organization_id != organization_id or workflow.department_id != department_id
            or execution.workflow_id != workflow.id or execution.department_id != department_id
            or not agent or agent.organization_id != organization_id or agent.department_id not in (None, department_id)
            or task.agent_id != agent.id or task.organization_id != organization_id):
        raise ToolAccessError('Workflow tool identity or tenant scope changed.')
    require_initiator(db, frozen.get('initiator_id'), organization_id, department_id)
    budget = db.check_department_budget(department_id)
    if not budget.get('allowed'):
        raise ToolAccessError('Department budget does not permit further connector calls.')
    return agent


def execution_context(db, execution_id):
    with db._get_connection() as conn:
        row = conn.execute('SELECT context_json FROM workflow_execution_tool_contexts WHERE execution_id=?', (execution_id,)).fetchone()
    return json.loads(row['context_json']) if row else None


def prepare_execution_context(db, execution, workflow, definition, user_context=None):
    binding = definition.metadata.get('channel_binding') if definition.metadata else None
    workspaces = any((s.params or {}).get('workspace') is not None for s in definition.steps)
    if not (binding or workspaces or definition.mcp_servers or any(s.mcp_servers for s in definition.steps)):
        return
    if execution.trigger_type == 'PLAYGROUND':
        raise ToolAccessError('Playground cannot receive live connector context.')
    if not workflow.organization_id or not workflow.department_id:
        raise ToolAccessError('Live integrations require an organization and department.')
    identity = (user_context or {}).get('sub')
    if user_context and not identity:
        raise ToolAccessError('Authenticated workflow initiator identity is missing.')
    require_initiator(db, identity, workflow.organization_id, workflow.department_id)
    context = {'organization_id': workflow.organization_id, 'department_id': workflow.department_id,
               'initiator_id': identity, 'binding': binding}
    with db._get_connection() as conn:
        conn.execute('INSERT INTO workflow_execution_tool_contexts(execution_id,context_json) VALUES (?,?)',
                     (execution.id, json.dumps(context)))
    if binding and binding.get('notify_mode', 'ON_COMPLETE') != 'NONE':
        from .notification_guard import notification_target
        try:
            notification_target(db, workflow, execution.id)
        except ToolAccessError as error:
            record_notification_error(db, execution.id, str(error))
    from .repo_workspace import authorize_workspace, workspace_configuration
    for step in definition.steps:
        prepare_scope(db, None, execution.id, step, persist=False)
        workspace = workspace_configuration(step)
        if workspace is not None:
            authorize_workspace(db, execution.id, step, workspace)  # Fail before any step runs.


def record_notification_error(db, execution_id, error):
    with db._get_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute('SELECT context_json FROM workflow_execution_tool_contexts WHERE execution_id=?', (execution_id,)).fetchone()
        if row:
            context = json.loads(row['context_json'])
            context['notification_error'] = error[:1000]
            conn.execute('UPDATE workflow_execution_tool_contexts SET context_json=? WHERE execution_id=?',
                (json.dumps(context), execution_id))
