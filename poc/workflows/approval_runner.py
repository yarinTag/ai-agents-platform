"""Bridge a deterministic approval gate into the common step result contract."""
from datetime import datetime
from runtime.models import TaskStatus
from .execution_models import WorkflowStepResult


def execute_gate(db, step, task, record_id, execution_id, outputs, playground_workspace):
    try:
        if playground_workspace:
            raise ValueError('Human approval and merging are unavailable in Playground.')
        from integrations.tool_scopes import prepare_scope
        from .human_approval import start_gate
        prepare_scope(db, task.run_id, execution_id, step)
        waiting = start_gate(db, step, task, record_id, execution_id, outputs)
        task.status = TaskStatus.PENDING_APPROVAL if waiting else TaskStatus.COMPLETED
        status = 'WAITING_APPROVAL' if waiting else 'COMPLETED'
    except Exception as exc:
        task.status, task.error = TaskStatus.FAILED, str(exc)
        status = 'FAILED'
    if status != 'WAITING_APPROVAL':
        task.ended_at = datetime.now()
    db.save_task_run(task)
    output = task.result or task.error or ''
    with db._get_connection() as conn:
        conn.execute('UPDATE workflow_step_runs SET status=?,output_data=?,error_message=?,completed_at=? WHERE id=?',
                     (status, output, task.error, task.ended_at.isoformat() if task.ended_at else None, record_id))
    return WorkflowStepResult(step_key=step.key, status=status, task_run_id=task.run_id,
                              output=output, error=task.error)
