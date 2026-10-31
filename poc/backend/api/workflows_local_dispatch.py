"""Explicit process-local production execution, independent of the broker."""
import json
import logging
import uuid
from datetime import datetime
from .workflows_mapping import _execution_to_response

logger = logging.getLogger(__name__)


def run_local(engine, workflow_id, execution_id, payload, payload_hash, user_context):
    try:
        engine.execute_workflow(workflow_id=workflow_id, execution_id=execution_id,
            trigger_type='MANUAL', trigger_payload=payload, payload_hash=payload_hash,
            user_context=user_context)
    except Exception:
        logger.exception('Local workflow execution %s failed', execution_id)
        current = engine.db.get_workflow_execution(execution_id)
        if current and current.status in ('QUEUED', 'RUNNING'):
            engine.db.update_workflow_execution(execution_id, status='FAILED',
                error_message='Local execution failed. Check workflow permissions, budget and runtime diagnostics.',
                completed_at=datetime.now().isoformat())


def dispatch_local(engine, background_tasks, workflow, payload, payload_hash, user_context):
    execution_id = 'wf_exec_' + uuid.uuid4().hex[:12]
    execution = engine.db.create_workflow_execution(execution_id=execution_id, workflow_id=workflow.id,
        trigger_type='MANUAL', trigger_payload=json.dumps(payload) if payload is not None else None,
        department_id=workflow.department_id, payload_hash=payload_hash, status='QUEUED')
    background_tasks.add_task(run_local, engine, workflow.id, execution_id, payload, payload_hash, user_context)
    return _execution_to_response(execution, message='Workflow accepted for execution on this server.')
