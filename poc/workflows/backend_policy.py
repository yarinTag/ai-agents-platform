"""Workflow backend inheritance and admission, separate from model selection."""
import json
from runtime.execution_backends import parse_backend, require_backend
from .settings import validate_settings


def step_backend(settings, step):
    """Explicit step override wins; omitted/null overrides inherit workflow settings."""
    if not isinstance(step.params, dict):
        raise ValueError('Workflow step params must be an object.')
    value = step.params.get('execution_backend')
    return parse_backend(settings.execution_backend if value is None else value)


def validate_step_backends(definition):
    """Authoring accepts known pending backends; execution admission is separate."""
    settings = validate_settings(definition.settings)
    for step in definition.steps:
        step_backend(settings, step)


def preflight_backends(definition, *, playground=False, db=None, workflow=None):
    """Check every AI step before any model/tool/notification side effect."""
    settings = validate_settings(definition.settings)
    for step in definition.steps:
        selected = step_backend(settings, step)
        if step.params.get('channel_action') is not None:
            continue  # Deterministic server delivery does not start an agent runtime.
        try:
            require_backend(selected, playground=playground,
                            governed_connectors=bool(step.mcp_servers))
            if selected.value == 'claude_code':
                from runtime.claude_hosted.policy import require_read_workspace
                require_read_workspace(step, settings)
                if db is not None and workflow is not None:
                    from runtime.claude_hosted.policy import preflight_hosted
                    preflight_hosted(db, workflow, step, settings)
        except ValueError as exc:
            raise ValueError(f'Workflow step {step.key}: {exc}') from None


def backend_for_task(db, task_id):
    """Resolve only persisted task lineage, never a client-supplied workflow ID."""
    if not task_id.startswith(('wf_task_', 'pg_task_', 'review_')):
        return parse_backend()
    with db._get_connection() as conn:
        row = conn.execute('SELECT e.workflow_id,s.step_key FROM workflow_step_runs s '
                           'JOIN workflow_executions e ON e.id=s.execution_id '
                           'WHERE s.task_run_id=?', (task_id,)).fetchone()
    if not row:
        # Reviews inherit their parent's backend; standalone non-workflow reviews
        # retain direct API. Missing workflow step identity is never an escape.
        if task_id.startswith('review_'):
            run = db.get_task_run(task_id)
            if run and run.parent_task_id and run.parent_task_id.startswith(('wf_task_', 'pg_task_')):
                return backend_for_task(db, run.parent_task_id)
            return parse_backend()
        raise ValueError('Workflow backend context is missing for this task.')
    workflow = db.get_workflow(row['workflow_id'])
    if not workflow:
        raise ValueError('Workflow backend definition no longer exists.')
    from .parser import WorkflowParser
    definition = WorkflowParser.from_dict(json.loads(workflow.definition_json))
    step = next((item for item in definition.steps if item.key == row['step_key']), None)
    if not step:
        raise ValueError('Workflow backend step no longer exists.')
    return step_backend(validate_settings(definition.settings), step)
