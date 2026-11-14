"""Terminal durable workflow approval gates; no blocked worker or model-held authority."""
import json
import uuid
from datetime import datetime, timedelta
from integrations.tool_definitions import ToolAccessError
from .approval_config import approval_configuration, public_url, validate_gates


def preflight(db, execution, workflow, definition):
    validate_gates(definition)
    from integrations.tool_scopes import prepare_scope
    from integrations.pr_approval_policy import authorize_subject
    for step in definition.steps:
        config = approval_configuration(step)
        if not config:
            continue
        if config.channel_binding_id:
            from storage.channel_approval_delivery import destination
            with db._get_connection() as conn:
                binding, _, _, _ = destination(conn, {
                    'binding_id': config.channel_binding_id, 'organization_id': workflow.organization_id,
                    'department_id': workflow.department_id,
                })
            if (binding['connector_id'], binding['channel_id']) != (config.connector_id, config.channel_id):
                raise ToolAccessError('Interactive approval binding does not match the declared destination.')
        else:
            public_url()
        if config.kind != 'pull_requests':
            continue
        source = next(item for item in definition.steps if item.key == config.source_step)
        scope = prepare_scope(db, None, execution.id, source, persist=False)
        reviews = [entry for entry in (scope or {}).get('entries', []) if entry['operation'] == 'get_pull_request_review']
        if not reviews:
            raise ToolAccessError('PR approval requires get_pull_request_review in the explicit source step tool scope.')
        for entry in reviews:
            for repository in entry['repositories']:
                authorize_subject(db, {'execution_id': execution.id, 'organization_id': workflow.organization_id,
                    'department_id': workflow.department_id, 'workflow_revision': workflow.revision},
                    {'repository': repository, 'agent_id': source.agent_id, 'connector_id': entry['connector_id'],
                     'tool_id': entry['tool_id']}, config.merge_after_approval)


def start_gate(db, step, task, step_record_id, execution_id, outputs):
    from integrations.tool_executor import WorkflowToolExecutor
    from integrations.pr_approval_policy import pinned_subjects, authorize_subject
    config = approval_configuration(step)
    execution = db.get_workflow_execution(execution_id)
    workflow = db.get_workflow(execution.workflow_id)
    report = outputs.get(config.source_step)
    if not isinstance(report, str) or not report.strip() or len(report) > 50000:
        raise ToolAccessError('Human approval requires a nonempty source report of at most 50,000 characters.')
    subjects = pinned_subjects(db, execution_id, config.source_step) if config.kind == 'pull_requests' else []
    if config.kind == 'pull_requests' and not subjects:
        task.result = 'No reviewed PR has complete, merge-ready evidence. No approval requested and nothing merged.'
        return False
    now = datetime.now()
    identifier = 'wfa_' + uuid.uuid4().hex
    approval = {'execution_id': execution_id, 'organization_id': workflow.organization_id,
                'department_id': workflow.department_id, 'workflow_revision': workflow.revision}
    for subject in subjects:
        authorize_subject(db, approval, subject, config.merge_after_approval)
    with db._get_connection() as conn:
        conn.execute('''INSERT INTO workflow_approvals
            (id,execution_id,step_run_id,task_id,organization_id,department_id,workflow_revision,
             status,config_json,subjects_json,report,created_at,expires_at)
            VALUES (?,?,?,?,?,?,?,'NOTIFYING',?,?,?,?,?)''',
            (identifier, execution_id, step_record_id, task.run_id, workflow.organization_id, workflow.department_id,
             workflow.revision, config.model_dump_json(), json.dumps(subjects), report,
             now.isoformat(), (now + timedelta(hours=config.expires_hours)).isoformat()))
        if config.channel_binding_id:
            from storage.channel_approval_delivery import enqueue
            enqueue(conn, identifier, config.channel_binding_id)
            conn.execute("UPDATE workflow_approvals SET status='PENDING' WHERE id=?", (identifier,))
    if config.channel_binding_id:
        task.result = f'Waiting for authenticated human approval: {identifier}.'
        return True
    link = f'{public_url()}/workflows/{workflow.id}/logs?execution={execution_id}'
    text = ('Human approval required. Sign in to review and approve or reject. '
            + ('Approval authorizes SHA-pinned PR merges after fresh checks.\n' if config.merge_after_approval else 'No merge is authorized.\n')
            + link + '\n\n' + report)
    executor = WorkflowToolExecutor(db, task.run_id)
    entries = list(executor.entries.values())
    if len(entries) != 1 or entries[0]['channels'] != [config.channel_id]:
        raise ToolAccessError('Approval notification requires exactly one governed channel destination.')
    try:
        executor.call(entries[0]['name'], {'channel_id': config.channel_id, 'text': text})
        executor.verify_completion()
    except Exception:
        with db._get_connection() as conn:
            conn.execute("UPDATE workflow_approvals SET status='FAILED',error='Approval notification failed; no retry or merge assumed.' WHERE id=?", (identifier,))
        raise
    with db._get_connection() as conn:
        conn.execute("UPDATE workflow_approvals SET status='PENDING' WHERE id=? AND status='NOTIFYING'", (identifier,))
    task.result = f'Waiting for authenticated human approval: {identifier}. No merge has occurred.'
    return True


def finish(db, approval, status, error=None, receipts=None):
    """Resolve the terminal gate atomically with its task, step and execution."""
    now = datetime.now().isoformat()
    completed = status == 'APPROVED'
    state = 'COMPLETED' if completed else 'FAILED'
    output = json.dumps({'approval_status': status, 'merge_receipts': receipts or [], 'error': error})
    with db._get_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        live = conn.execute('SELECT status FROM workflow_executions WHERE id=?', (approval['execution_id'],)).fetchone()
        if not live or live['status'] != 'WAITING_APPROVAL':
            conn.execute("UPDATE workflow_approvals SET status='FAILED',error=?,receipts_json=?,resolved_at=? WHERE id=?",
                ('The execution stopped; recorded external receipts require inspection.', json.dumps(receipts or []), now, approval['id']))
            return
        conn.execute('''UPDATE workflow_approvals SET status=?,error=?,receipts_json=?,resolved_at=? WHERE id=?''',
                     (status, error, json.dumps(receipts or []), now, approval['id']))
        conn.execute('UPDATE workflow_step_runs SET status=?,output_data=?,error_message=?,completed_at=? WHERE id=?',
                     (state, output, error, now, approval['step_run_id']))
        conn.execute('UPDATE task_runs SET status=?,result=?,error=?,ended_at=? WHERE run_id=?',
                     (state.lower(), output, error, now, approval['task_id']))
        conn.execute('UPDATE workflow_executions SET status=?,error_message=?,completed_at=? WHERE id=?',
                     (state, error, now, approval['execution_id']))


def resolve(db, approval, approve, approver_check):
    from integrations.pr_approval_policy import fresh_review
    from integrations.tool_scopes import execution_context, require_initiator
    receipts = []
    try:
        approver_check()
        if approval['expires_at'] <= datetime.now().isoformat():
            raise ToolAccessError('This approval expired. Create a fresh run.')
        execution = db.get_workflow_execution(approval['execution_id'])
        workflow = db.get_workflow(execution.workflow_id) if execution else None
        if (not execution or execution.status != 'WAITING_APPROVAL' or not workflow
                or workflow.organization_id != approval['organization_id'] or workflow.department_id != approval['department_id']
                or workflow.revision != approval['workflow_revision']):
            raise ToolAccessError('The waiting execution or workflow revision changed.')
        context = execution_context(db, execution.id) or {}
        require_initiator(db, context.get('initiator_id'), workflow.organization_id, workflow.department_id)
        if not approve:
            finish(db, approval, 'REJECTED', 'Rejected by the human approver.')
            return
        config = json.loads(approval['config_json'])
        subjects = json.loads(approval['subjects_json'])
        for subject in subjects:
            approver_check()
            fresh_review(db, approval, subject, config['merge_after_approval'], approver_check)
        if config['merge_after_approval']:
            for subject in subjects:
                from integrations.pr_merge import merge_subject
                merge_subject(db, approval, subject, approver_check, receipts)
        finish(db, approval, 'APPROVED', receipts=receipts)
    except Exception as exc:
        message = str(exc) if isinstance(exc, ToolAccessError) else 'Approval action failed; an external outcome may be unknown. No automatic retry.'
        finish(db, approval, 'FAILED', message, receipts)


def expire_if_due(db, approval):
    if approval['status'] != 'PENDING' or approval['expires_at'] > datetime.now().isoformat():
        return
    with db._get_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        claimed = conn.execute("UPDATE workflow_approvals SET status='EXPIRING' WHERE id=? AND status='PENDING' AND expires_at<=?",
                               (approval['id'], datetime.now().isoformat())).rowcount
    if claimed:
        finish(db, approval, 'EXPIRED', 'Approval expired without a decision. Start a new review.')
