"""Current database policy and a credential-free allowlist for workflow chat."""
import json
from fastapi import HTTPException
from workflows.parser import validate_workflow_definition
from integrations.tool_definitions import OPERATIONS, ensure_tools, require_credentials, resource_values, valid_channel, valid_repository
from .workflow_chat_models import ChatWorkflow
from integrations.tool_scopes import agent_tool_allowed

PLANNED_RUNNER_ID = "__workflow_runner__"


def workspace(db, claims, department_id=None):
    user = db.get_user(claims.get('sub')) if claims else None
    if not user or user.status != 'ACTIVE' or user.organization_id != claims.get('org_id'):
        raise HTTPException(403, 'Sign in with an active organization account to create workflows.')
    departments = db.list_departments(organization_id=user.organization_id)
    membership = {m['department_id']: m['department_role'] for m in db.get_user_departments(user.id)
                  if m['organization_id'] == user.organization_id}
    allowed = [d for d in departments if user.role == 'ORG_ADMIN' or
               membership.get(d.id) in ('MANAGER', 'OPERATOR')]
    if department_id and department_id not in {d.id for d in allowed}:
        raise HTTPException(403, 'You no longer have permission to create workflows in this department.')
    return user, allowed



def catalog(db, claims, department_id):
    user, _ = workspace(db, claims, department_id)
    agent_records = [a for a in db.list_agents(organization_id=user.organization_id)
              if a.organization_id == user.organization_id and a.department_id in (None, department_id)
              and not a.is_workflow_agent]
    agents = [{'id': a.id, 'name': a.name, 'connector_tools': {}} for a in agent_records]
    connectors = []
    for connector in db.list_mcp_connectors(organization_id=user.organization_id):
        if connector.organization_id != user.organization_id or connector.status != 'CONNECTED':
            continue
        grant = db.get_department_mcp_access(department_id, connector.id)
        if not grant or not grant.is_active or grant.organization_id not in (None, user.organization_id):
            continue
        implementations = ensure_tools(db, connector)
        tools = [name for name in implementations if db.check_department_mcp_permission(department_id, connector.id, name)['allowed']]
        for record, public in zip(agent_records, agents):
            public['connector_tools'][connector.id] = [name for name in tools if agent_tool_allowed(db, record, connector, implementations[name])]
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
            'repositories': repositories, 'channels': channels,
            'channel_labels': {identifier: str(config.get('channel_labels', {}).get(identifier) or identifier)[:200]
                               for identifier in channels}})
    agents.append({'id': PLANNED_RUNNER_ID, 'name': 'Dedicated workflow runner',
        'provision_on_create': True,
        'connector_tools': {connector['id']: connector['tools'] for connector in connectors}})
    from plugins.workflow_skills import skill_catalog
    return {'agents': agents, 'connectors': connectors, 'skills': skill_catalog(db, user.organization_id),
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
        for field, group in (('repository', 'repositories'), ('channel_id', 'channels'), ('tool_name', 'tools')):
            value = getattr(ref, field, None)
            if value and value not in connector[group]:
                errors.append(f'{field} {value} is not allowed on {ref.connector_id}.')
    approved_skills = {skill['id'] for skill in resources.get('skills', [])}
    if set(candidate.skills) - approved_skills:
        errors.append('Workflow selects a skill outside the configured plugin catalog.')
    for step in candidate.steps:
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
            if delivery_tool not in destination['tools']:
                errors.append('The destination requires a granted message-delivery tool.')
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
        data = step.model_dump(exclude={'resources', 'send_output_of', 'skills'})
        if step.agent_id == PLANNED_RUNNER_ID and runner_agent_id:
            data['agent_id'] = runner_agent_id
        data['mcp_servers'] = sorted({r.connector_id for r in step.resources})
        data['params'] = {'authorized_resources': [r.model_dump(exclude_none=True) for r in step.resources]}
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
            'channel_name': connector.get('channel_labels', {}).get(destination.channel_id, destination.channel_id), 'trigger_enabled': False, 'notify_mode': 'ON_COMPLETE'}
    selected_skills = list(dict.fromkeys([*candidate.skills, *(value for step in candidate.steps for value in step.skills)]))
    return {'name': candidate.name, 'description': candidate.description, 'steps': steps, 'skills': selected_skills,
        'mcp_servers': sorted({value for step in steps for value in step['mcp_servers']}),
        'cron_expression': candidate.cron_expression, 'webhook_enabled': False, 'metadata': metadata}
