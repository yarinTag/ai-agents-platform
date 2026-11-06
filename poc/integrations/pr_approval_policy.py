"""Server-only PR merge policy. Model tools cannot approve or invoke this action."""
import hashlib
import json
from .tool_definitions import ToolAccessError, require_credentials, resource_values
from .tool_scopes import agent_tool_allowed, connector_authorized, execution_context, require_initiator
from .github_prs import GitHubReads

MERGE_OPERATION = 'merge_pull_request'


def merge_tool(db, connector):
    identifier = 'tool_merge_' + hashlib.sha256(connector.id.encode()).hexdigest()[:24]
    return db.get_mcp_tool(identifier) or db.save_mcp_tool({'id': identifier, 'connector_id': connector.id,
        'name': MERGE_OPERATION, 'description': 'Server-only SHA-pinned merge after authenticated human approval and fresh checks.',
        'input_schema': {'type': 'object', 'additionalProperties': False}})


def authorize_subject(db, approval, subject, merge=False):
    execution = db.get_workflow_execution(approval['execution_id'])
    workflow = db.get_workflow(execution.workflow_id) if execution else None
    agent = db.get_agent(subject['agent_id'])
    if (not execution or execution.status not in ('RUNNING', 'WAITING_APPROVAL') or execution.trigger_type == 'PLAYGROUND'
            or not workflow or workflow.organization_id != approval['organization_id']
            or workflow.department_id != approval['department_id'] or workflow.revision != approval['workflow_revision']
            or not agent or agent.organization_id != workflow.organization_id
            or agent.department_id not in (None, workflow.department_id)):
        raise ToolAccessError('Approval ownership, workflow revision or live execution changed.')
    context = execution_context(db, execution.id)
    if not context:
        raise ToolAccessError('The original execution authority is unavailable.')
    require_initiator(db, context.get('initiator_id'), workflow.organization_id, workflow.department_id)
    connector = connector_authorized(db, subject['connector_id'], workflow.organization_id, workflow.department_id, agent)
    require_credentials(connector)
    if connector.provider.lower() != 'github' or subject['repository'] not in resource_values(connector.configuration or {}, 'repositories'):
        raise ToolAccessError('The reviewed repository is no longer authorized.')
    tool = db.get_mcp_tool(subject['tool_id'])
    if (not tool or tool.connector_id != connector.id or tool.name != 'get_pull_request_review'
            or not agent_tool_allowed(db, agent, connector, tool)
            or not db.check_department_mcp_permission(workflow.department_id, connector.id, tool.name)['allowed']):
        raise ToolAccessError('PR review permission was revoked.')
    if merge:
        permission = db.check_department_mcp_permission(workflow.department_id, connector.id, MERGE_OPERATION)
        if not permission.get('allowed') or '*' in (permission.get('allowed_tools') or []):
            raise ToolAccessError('Merging requires an explicit merge_pull_request department grant; wildcard grants cannot merge.')
        if not agent_tool_allowed(db, agent, connector, merge_tool(db, connector)):
            raise ToolAccessError('The execution agent cannot merge pull requests.')
    from governance.enforcement import require_capability
    require_capability(db, execution.id, agent, connector, 'get_pull_request_review', subject['repository'])
    if merge:
        require_capability(db, execution.id, agent, connector, MERGE_OPERATION, subject['repository'], approval_path=True)
    if not db.check_department_budget(workflow.department_id).get('allowed'):
        raise ToolAccessError('Department budget does not permit further integration work.')
    return connector


def pinned_subjects(db, execution_id, source_step):
    with db._get_connection() as conn:
        steps = conn.execute('SELECT task_run_id,status FROM workflow_step_runs WHERE execution_id=? AND step_key=?',
                             (execution_id, source_step)).fetchall()
        if len(steps) != 1 or steps[0]['status'] != 'COMPLETED':
            raise ToolAccessError('Approval requires exactly one completed source step.')
        calls = conn.execute('''SELECT c.* FROM mcp_tool_calls c JOIN mcp_tools t ON t.id=c.tool_id
            WHERE c.task_id=? AND c.status='COMPLETED' AND t.name='get_pull_request_review' ''',
                             (steps[0]['task_run_id'],)).fetchall()
    subjects = {}
    for call in calls:
        value = json.loads(call['result'] or '{}')
        if value.get('candidate_ready') is not True or value.get('partial') is not False:
            continue
        pull = value['pull_request']
        subject = {'repository': value['repository'], 'pull_number': pull['number'],
                   'head_sha': pull['head']['sha'], 'base_sha': pull['base']['sha'],
                   'connector_id': call['connector_id'], 'agent_id': call['agent_id'], 'tool_id': call['tool_id'],
                   'url': pull['url'], 'author': pull['author']}
        subjects[(subject['connector_id'], subject['repository'], subject['pull_number'])] = subject
    if len(subjects) > 10:
        raise ToolAccessError('One approval batch supports at most ten reviewed PRs; narrow the workflow request.')
    return list(subjects.values())


def fresh_review(db, approval, subject, merge):
    authorize = lambda: authorize_subject(db, approval, subject, merge)
    connector = authorize()
    client = GitHubReads(connector.configuration or {}, subject['repository'], authorize)
    result = client.review(subject['pull_number'])
    pull = result['pull_request']
    if (not result['candidate_ready'] or result['partial'] or pull['head']['sha'] != subject['head_sha']
            or pull['base']['sha'] != subject['base_sha']):
        raise ToolAccessError('PR commits/checks/reviews changed or are not merge-ready. Create a fresh review and approval.')
    return client
