"""Current database policy and a credential-free allowlist for workflow chat."""
import json
from fastapi import HTTPException
from workflows.parser import validate_workflow_definition
from integrations.tool_definitions import OPERATIONS, ensure_tools, require_credentials, resource_values, valid_channel, valid_repository
from .workflow_chat_models import ChatWorkflow
from integrations.tool_scopes import agent_tool_allowed
from .workflow_chat_workspace import workspace_operations, agent_workspace_operations, validate_workspace

PLANNED_RUNNER_ID = "__workflow_runner__"


def _interactive_binding(config, resources):
    return next((binding['id'] for binding in resources.get('interactive_approval_bindings', [])
                 if binding['connector_id'] == config.connector_id and binding['channel_id'] == config.channel_id), None)


def workspace(db, claims, department_id=None):
    user = db.get_user(claims.get('sub')) if claims else None
    if not user or user.status != 'ACTIVE' or user.organization_id != claims.get('org_id'):
        raise HTTPException(403, 'Sign in with an active organization account to create workflows.')
    departments = db.list_departments(organization_id=user.organization_id)
    membership = {m['department_id']: m['department_role'] for m in db.get_user_departments(user.id)
                  if m['organization_id'] == user.organization_id}
    roles = ('MEMBER', 'OPERATOR', 'MANAGER', 'ORG_ADMIN')
    allowed = [d for d in departments if user.role in roles and (user.role == 'ORG_ADMIN' or
               membership.get(d.id) in roles)]
    if department_id and department_id not in {d.id for d in allowed}:
        raise HTTPException(403, 'You no longer have permission to create workflows in this department.')
    return user, allowed



def catalog(db, claims, department_id):
    user, _ = workspace(db, claims, department_id)
    agent_records = [a for a in db.list_agents(organization_id=user.organization_id)
              if a.organization_id == user.organization_id and a.department_id in (None, department_id)
              and not a.is_workflow_agent]
    agents = [{'id': a.id, 'name': a.name, 'connector_tools': {}, 'workspace_operations': {}, 'server_operations': {}} for a in agent_records]
    connectors = []
    for connector in db.list_mcp_connectors(organization_id=user.organization_id):
        if connector.organization_id != user.organization_id or connector.status != 'CONNECTED':
            continue
        grant = db.get_department_mcp_access(department_id, connector.id)
        if not grant or not grant.is_active or grant.organization_id not in (None, user.organization_id):
            continue
        implementations = ensure_tools(db, connector)
        from integrations.pr_approval_policy import merge_tool, MERGE_OPERATION
        server_operations = []
        if connector.provider.lower() == 'github':
            merge_tool(db, connector)
            grant = db.check_department_mcp_permission(department_id, connector.id, MERGE_OPERATION)
            if grant.get('allowed') and '*' not in (grant.get('allowed_tools') or []):
                server_operations.append(MERGE_OPERATION)
        tools = [name for name in implementations if db.check_department_mcp_permission(department_id, connector.id, name)['allowed']]
        workspace_tools = workspace_operations(db, connector, department_id)
        for record, public in zip(agent_records, agents):
            public['server_operations'][connector.id] = [op for op in server_operations if agent_tool_allowed(db, record, connector, merge_tool(db, connector))]
            public['connector_tools'][connector.id] = [name for name in tools if agent_tool_allowed(db, record, connector, implementations[name])]
            public['workspace_operations'][connector.id] = agent_workspace_operations(db, record, connector, workspace_tools)
        config = connector.configuration or {}
        repositories = [v for v in resource_values(config, 'repositories') if valid_repository(v)]
        channels = [v for v in resource_values(config, 'channels') if valid_channel(connector.provider.lower(), v)]
        try:
            require_credentials(connector)
            configured = True
        except ValueError:
            configured = False
        executable = bool(tools) and configured and bool(repositories if connector.provider.lower() == 'github' else channels)
        connectors.append({'id': connector.id, 'name': connector.name, 'provider': connector.provider,
            'tools': sorted(tools), 'execution_supported': executable,
            'tool_capabilities': {name: OPERATIONS[connector.provider.lower()][name] for name in tools},
            'server_operations': server_operations if configured else [],
            'workspace_operations': workspace_tools if configured else [],
            'repositories': repositories, 'channels': channels,
            'channel_labels': {identifier: str(config.get('channel_labels', {}).get(identifier) or identifier)[:200]
                               for identifier in channels}})
    agents.append({'id': PLANNED_RUNNER_ID, 'name': 'Dedicated workflow runner',
        'provision_on_create': True,
        'server_operations': {connector['id']: connector['server_operations'] for connector in connectors},
        'workspace_operations': {connector['id']: connector['workspace_operations'] for connector in connectors},
        'connector_tools': {connector['id']: connector['tools'] for connector in connectors}})
    from governance.catalog import narrow_catalog
    narrow_catalog(db, user, department_id, connectors, agents)
    from plugins.workflow_skills import skill_catalog
    from workflows.repo_sandbox import configuration_status
    from workflows.approval_config import public_url
    try:
        public_url()
        approval_ready = True
    except ValueError:
        approval_ready = False
    with db._get_connection() as conn:
        candidates = conn.execute("""SELECT id,connector_id,channel_id FROM channel_bindings
            WHERE organization_id=? AND department_id=? AND provider='telegram'
            AND approve_decisions=1 AND send_notifications=1""",
            (user.organization_id, department_id)).fetchall()
    from integrations.identity_proofs import InvalidProof, configuration
    bindings = []
    for binding in candidates:
        if not any(c['id'] == binding['connector_id'] and c['provider'] == 'telegram'
                   and binding['channel_id'] in c['channels'] and 'send_message' in c['tools'] for c in connectors):
            continue
        try:
            configuration('telegram', db.get_mcp_connector(binding['connector_id']).configuration or {})
        except (InvalidProof, AttributeError):
            continue
        bindings.append(dict(binding))
    return {'interactive_approval_bindings': bindings,
        'human_approval': {'configured': approval_ready or bool(bindings), 'terminal_only': True,
             'dashboard_configured': approval_ready,
             'delivery': 'Verified Telegram buttons for matching bindings, or authenticated dashboard approval',
             'missing_setup': None if approval_ready or bindings else 'Configure an interactive Telegram binding or the dashboard HTTPS URL.'},
        'agents': agents, 'connectors': connectors, 'skills': skill_catalog(db, user.organization_id),
        'workspace_readiness': configuration_status(),
        'note': 'Only these configured resource IDs are authorized. Discovery does not grant access. '
                'Only implemented and granted runtime tools are listed. A connected catalog entry alone is not executable. '
                'Channel display-name aliases are excluded; exact delivery IDs must be configured. '
                'Missing IDs require an administrator to configure or grant access; never invent them.'}


def validate_candidate(candidate, resources):
    errors = []
    agents = {a['id']: a for a in resources['agents']}
    connectors = {c['id']: c for c in resources['connectors']}
    def reference(ref):
        connector = connectors.get(ref.connector_id)
        if not connector:
            errors.append(f'Connector {ref.connector_id} is not allowed.')
            return
        if not connector.get('execution_supported'):
            errors.append(f'Connector {ref.connector_id} has no implemented and granted runtime tools.')
        from governance.catalog import reference_allowed
        resource = getattr(ref, 'repository', None) or ref.channel_id
        operation = getattr(ref, 'tool_name', None)
        if operation and resource and not reference_allowed(connector, operation, resource):
            errors.append('The selected capability/resource combination is denied by current policy.')
        for field, group in (('repository', 'repositories'), ('channel_id', 'channels'), ('tool_name', 'tools')):
            value = getattr(ref, field, None)
            if value and value not in connector[group]:
                errors.append(f'{field} {value} is not allowed on {ref.connector_id}.')
    approved_skills = {skill['id'] for skill in resources.get('skills', [])}
    if set(candidate.skills) - approved_skills:
        errors.append('Workflow selects a skill outside the configured plugin catalog.')
    for step in candidate.steps:
        if step.human_approval:
            errors.extend(validate_approval(step, candidate, resources, agents, connectors))
        errors.extend(validate_workspace(step, agents, connectors))
        if set(step.skills) - approved_skills:
            errors.append(f'Step {step.key} selects a skill outside the configured plugin catalog.')
        if step.send_output_of:
            if step.send_output_of not in step.depends_on or len(step.resources) != 1:
                errors.append('A delivery step needs one explicit channel resource and its source as a dependency.')
            elif not step.resources[0].channel_id or step.resources[0].repository:
                errors.append('A delivery step must reference only its destination channel.')
        if any(marker in step.prompt_template.casefold() for marker in
               ('inactive preview', 'do not claim execution', 'you have no tools')):
            errors.append(f'Step {step.key} contains draft-only instructions. Remove them from its execution prompt.')
        if step.agent_id not in agents:
            errors.append(f'Agent {step.agent_id} is not available in this department.')
        for ref in step.resources:
            reference(ref)
            combinations = agents.get(step.agent_id, {}).get('capability_resources', {}).get(ref.connector_id)
            if combinations is not None and ref.tool_name and (ref.repository or ref.channel_id) not in combinations.get(ref.tool_name, []):
                errors.append(f'Agent {step.agent_id} is not authorized for this capability/resource combination.')
        for identifier in {r.connector_id for r in step.resources}:
            connector = connectors.get(identifier)
            assigned = agents.get(step.agent_id, {}).get('connector_tools', {}).get(identifier, [])
            requested = {r.tool_name for r in step.resources if r.connector_id == identifier and r.tool_name}
            if not assigned or requested - set(assigned):
                errors.append(f'Agent {step.agent_id} lacks the required connector tool access.')
            if connector and connector['provider'] == 'github' and not any(r.connector_id == identifier and r.repository for r in step.resources):
                errors.append('GitHub steps require an explicit approved repository reference.')
            if connector and connector['provider'] in ('slack', 'telegram') and not any(r.connector_id == identifier and r.channel_id for r in step.resources):
                errors.append('Channel send steps require an explicit approved channel ID.')
    if candidate.destination:
        reference(candidate.destination)
        destination = connectors.get(candidate.destination.connector_id)
        if destination and destination['provider'] not in ('slack', 'telegram'):
            errors.append('Delivery requires an allowed Slack or Telegram connector.')
        if destination and destination['provider'] in ('slack', 'telegram'):
            delivery_tool = 'send_message' if destination['provider'] == 'telegram' else 'post_chat_message'
            from governance.catalog import reference_allowed
            if (delivery_tool not in destination['tools'] or not reference_allowed(
                    destination, delivery_tool, candidate.destination.channel_id)):
                errors.append('The destination requires a granted message-delivery tool.')
            notification_agent = agents.get(candidate.steps[0].agent_id, {})
            per_agent = notification_agent.get('capability_resources', {}).get(candidate.destination.connector_id)
            if per_agent is not None and candidate.destination.channel_id not in per_agent.get(delivery_tool, []):
                errors.append('The notification agent is not authorized for this exact channel.')
    if candidate.cron_expression:
        from croniter import croniter
        if not croniter.is_valid(candidate.cron_expression):
            errors.append('The schedule is not a valid cron expression.')
    definition = native_definition(candidate, resources)
    try:
        validate_workflow_definition(definition)
    except (ValueError, TypeError) as exc:
        errors.append(str(exc))
    return errors


def native_definition(candidate: ChatWorkflow, resources, runner_agent_id=None):
    connectors = {c['id']: c for c in resources['connectors']}
    steps = []
    for step in candidate.steps:
        data = step.model_dump(exclude={'resources', 'send_output_of', 'skills', 'workspace', 'required_outcome', 'human_approval'})
        if step.agent_id == PLANNED_RUNNER_ID and runner_agent_id:
            data['agent_id'] = runner_agent_id
        data['mcp_servers'] = sorted({r.connector_id for r in step.resources})
        data['params'] = {'authorized_resources': [r.model_dump(exclude_none=True) for r in step.resources]}
        if step.human_approval:
            config = step.human_approval
            binding = _interactive_binding(config, resources)
            if binding and config.kind == 'report' and not config.merge_after_approval:
                data['mcp_servers'] = []
                data['params'] = {'dag_approval': {'channel_binding_id': binding,
                    'summary_step': config.source_step, 'timeout_seconds': config.expires_hours * 3600}}
            else:
                data['params']['human_approval'] = {
                    **config.model_dump(exclude={'channel_binding_id'}), 'channel_binding_id': binding,
                }
        if step.workspace:
            data['params'] = {'workspace': step.workspace.model_dump(exclude_none=True)}
        if step.required_outcome == 'pull_request':
            data['params']['required_outcome'] = 'pull_request'
        if step.send_output_of and len(step.resources) == 1:
            ref = step.resources[0]
            data['params']['channel_action'] = {'action': 'send_channel_message',
                'connector_id': ref.connector_id, 'channel_id': ref.channel_id,
                'source_step': step.send_output_of}
        # Carry exact IDs into executable instructions, not just display metadata.
        if step.resources:
            data['prompt_template'] += '\nUse only these configured resources: ' + json.dumps(data['params']['authorized_resources'])
        steps.append(data)
    metadata = {}
    if candidate.destination:
        destination = candidate.destination
        connector = connectors.get(destination.connector_id, {})
        metadata['channel_binding'] = {'provider': connector.get('provider', ''),
            'connector_id': destination.connector_id, 'channel_id': destination.channel_id,
            'channel_name': connector.get('channel_labels', {}).get(destination.channel_id, destination.channel_id),
            'trigger_enabled': False, 'notify_mode': destination.notify_mode}
    selected_skills = list(dict.fromkeys([*candidate.skills, *(value for step in candidate.steps for value in step.skills)]))
    return {'name': candidate.name, 'description': candidate.description, 'steps': steps, 'skills': selected_skills,
        'mcp_servers': sorted({value for step in steps for value in step['mcp_servers']} |
                              {step.workspace.connector_id for step in candidate.steps if step.workspace}),
        'cron_expression': candidate.cron_expression, 'webhook_enabled': False, 'metadata': metadata}


def validate_approval(step, candidate, resources, agents, connectors):
    config = step.human_approval
    errors = []
    readiness = resources.get('human_approval', {})
    if not _interactive_binding(config, resources) and not readiness.get('dashboard_configured', readiness.get('configured')):
        errors.append('This destination needs an eligible interactive Telegram binding or an HTTPS dashboard URL.')
    if step.workspace or step.send_output_of:
        errors.append('Human approval cannot be combined with repository editing or a send-output action.')
    if config.source_step not in step.depends_on:
        errors.append('Approval source_step must be an explicit dependency.')
    source = next((item for item in candidate.steps if item.key == config.source_step), None)
    if config.kind == 'pull_requests':
        reviews = [ref for ref in (source.resources if source else []) if ref.tool_name == 'get_pull_request_review']
        if not reviews:
            errors.append('PR approval source must explicitly request get_pull_request_review.')
        for ref in reviews:
            if config.merge_after_approval and ('merge_pull_request' not in connectors.get(ref.connector_id, {}).get('server_operations', [])
                    or 'merge_pull_request' not in agents.get(source.agent_id, {}).get('server_operations', {}).get(ref.connector_id, [])):
                errors.append('Automatic merging requires an explicit merge_pull_request grant for the source agent and department.')
            if config.merge_after_approval:
                from governance.catalog import reference_allowed
                connector = connectors.get(ref.connector_id, {})
                agent = agents.get(source.agent_id, {})
                per_agent = agent.get('capability_resources', {}).get(ref.connector_id)
                if (not reference_allowed(connector, 'merge_pull_request', ref.repository, 'resources_by_server_operation')
                        or (per_agent is not None and ref.repository not in per_agent.get('merge_pull_request', []))):
                    errors.append('Automatic merging is not permitted for this exact repository and source agent.')
    channel = connectors.get(config.connector_id, {})
    tool = 'send_message' if channel.get('provider') == 'telegram' else 'post_chat_message'
    if (len(step.resources) != 1 or step.resources[0].connector_id != config.connector_id
            or step.resources[0].channel_id != config.channel_id or step.resources[0].tool_name != tool
            or channel.get('provider') not in ('telegram', 'slack')):
        errors.append('Approval requires one exact approved notification channel and delivery tool resource.')
    return errors
