"""New lightweight workflow-chat API; independent of the removed assistant."""
import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timedelta
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from ..dependencies import get_db_manager, get_runtime_adapter, get_optional_runtime_adapter
from .workflow_chat_models import ChatReply, ChatRequest, ChatWorkflow
from .workflow_chat_policy import catalog, native_definition, validate_candidate, workspace
from .workflows_crud import persist_workflow
from .workflows_mapping import _workflow_to_response
from .workflows_models import WorkflowCreateRequest

router = APIRouter()


def claims(request):
    return getattr(request.state, 'user', None) or {}


def read_job(db, identity, job_id):
    user, _ = workspace(db, identity)
    with db._get_connection() as conn:
        row = conn.execute('SELECT * FROM workflow_builder_jobs WHERE id=? AND user_id=? AND organization_id=?',
            (job_id, user.id, user.organization_id)).fetchone()
        if not row:
            raise HTTPException(404, 'Chat draft not found.')
        workspace(db, identity, row['department_id'])
        if row['status'] == 'GENERATING' and row['deadline_at'] < datetime.now().isoformat():
            conn.execute("UPDATE workflow_builder_jobs SET status='FAILED', error=? WHERE id=? AND status='GENERATING'",
                ('The request expired. Please try again.', job_id))
            conn.commit()
            row = conn.execute('SELECT * FROM workflow_builder_jobs WHERE id=?', (job_id,)).fetchone()
        return dict(row)


def public_job(row):
    saved_request = json.loads(row['request_json'])
    return {'id': row['id'], 'status': row['status'], 'department_id': row['department_id'],
        'messages': saved_request.get('messages', []),
        'previous_workflow': saved_request.get('previous_workflow'),
        'result': json.loads(row['result_json']) if row['result_json'] else None,
        'error': row['error'], 'model': row['model_id'], 'provider': row['provider_id'],
        'workflow_id': row['workflow_id'] if row['status'] == 'CREATED' else None}


@router.get('/ai/context')
def context(request: Request, department_id: str | None = None,
            db=Depends(get_db_manager), runtime=Depends(get_optional_runtime_adapter)):
    user, departments = workspace(db, claims(request), department_id)
    selected = None
    if runtime and hasattr(runtime, 'workflow_chat_selection'):
        try:
            selected = runtime.workflow_chat_selection(user.organization_id)
        except ValueError:
            selected = None
    return {'departments': [{'id': d.id, 'name': d.name} for d in departments],
        'selection': selected, 'catalog': catalog(db, claims(request), department_id) if department_id else None}


@router.post('/ai/chat', status_code=202)
def chat(payload: ChatRequest, request: Request, background: BackgroundTasks,
         db=Depends(get_db_manager), runtime=Depends(get_runtime_adapter)):
    identity = claims(request)
    user, _ = workspace(db, identity, payload.department_id)
    if not hasattr(runtime, 'infer_workflow_chat'):
        raise HTTPException(503, 'The selected runtime does not support workflow creation chat.')
    raw = payload.model_dump_json()
    digest = hashlib.sha256(raw.encode()).hexdigest()
    try:
        selected = runtime.workflow_chat_selection(user.organization_id)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from None
    now = datetime.now()
    with db._get_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        existing = conn.execute('SELECT * FROM workflow_builder_jobs WHERE id=?', (payload.request_id,)).fetchone()
        if existing:
            if existing['user_id'] != user.id or existing['organization_id'] != user.organization_id:
                raise HTTPException(404, 'Chat draft not found.')
            if existing['request_hash'] != digest:
                raise HTTPException(409, 'This request ID was already used for another message.')
            return public_job(dict(existing))
        conn.execute("""UPDATE workflow_builder_jobs SET status='FAILED', error='Request expired.'
            WHERE status='GENERATING' AND deadline_at < ?""", (now.isoformat(),))
        try:
            conn.execute('''INSERT INTO workflow_builder_jobs
                (id, organization_id, user_id, department_id, request_hash, request_json,
                 status, provider_id, model_id, cost_source, created_at, deadline_at)
                VALUES (?, ?, ?, ?, ?, ?, 'GENERATING', ?, ?, ?, ?, ?)''',
                (payload.request_id, user.organization_id, user.id, payload.department_id, digest, raw,
                 selected['provider_id'], selected['model_id'], selected['cost_source'],
                 now.isoformat(), (now + timedelta(seconds=180)).isoformat()))
        except sqlite3.IntegrityError as exc:
            raise HTTPException(409, 'Another workflow request is running in this department. Try again shortly.') from exc
        conn.commit()
    background.add_task(generate, db, runtime, identity, payload.request_id)
    return public_job(read_job(db, identity, payload.request_id))


def parse_reply(output):
    if isinstance(output, dict):
        return ChatReply.model_validate(output)
    text = str(output or '')
    decoder = json.JSONDecoder()
    for offset, value in enumerate(text):
        if value != '{':
            continue
        try:
            parsed, _ = decoder.raw_decode(text[offset:])
            return ChatReply.model_validate(parsed)
        except ValueError:
            continue
    raise ValueError('The model returned an invalid reply. Please try again.')


def generate(db, runtime, identity, job_id):
    inference = {}
    result = None
    error = None
    try:
        row = read_job(db, identity, job_id)
        payload = ChatRequest.model_validate_json(row['request_json'])
        if row['status'] != 'GENERATING':
            return
        resources = catalog(db, identity, payload.department_id)
        department = db.get_department(payload.department_id)
        remaining = max(0, department.monthly_budget_usd - department.current_spend_usd)
        if row['cost_source'] == 'API_KEY' and remaining <= 0:
            raise HTTPException(402, 'This department has no remaining API budget.')
        prompt = json.dumps({'locale': payload.locale, 'messages': [m.model_dump() for m in payload.messages],
            'previous_workflow': payload.previous_workflow.model_dump() if payload.previous_workflow else None,
            'approved_catalog': resources}, ensure_ascii=False)
        if len(prompt) > 160000:
            raise ValueError('The conversation and resource list are too large. Start a new conversation.')

        def stopped():
            try:
                return read_job(db, identity, job_id)['status'] != 'GENERATING'
            except HTTPException:
                return True

        selected = {key: row[key] for key in ('provider_id', 'model_id', 'cost_source')}
        selected['organization_id'] = row['organization_id']
        inference = runtime.infer_workflow_chat(selected, prompt, ChatReply.model_json_schema(), remaining, stopped)
        resources = catalog(db, identity, payload.department_id)
        if inference.get('error'):
            error = inference['error']
        else:
            reply = parse_reply(inference.get('output'))
            errors = validate_candidate(reply.workflow, resources) if reply.workflow else []
            message = reply.message if not errors else ('הטיוטה דורשת תיקון לפני היצירה. הפרטים מופיעים בתצוגה המקדימה.' if payload.locale == 'he' else 'This draft needs corrections before it can be created. See the details in the preview.')
            result = {'message': message, 'workflow': reply.workflow.model_dump() if reply.workflow else None,
                'errors': errors, 'ready': bool(reply.workflow) and not errors}
    except HTTPException as exc:
        error = str(exc.detail)
    except ValueError:
        error = 'The model returned an invalid workflow reply. Please try again or change the configured model.'
    except Exception:
        error = 'Unable to generate the workflow. Check runtime configuration and try again.'
    with db._get_connection() as conn:
        # Account for paid usage even if cancellation/revocation wins publication.
        conn.execute('''UPDATE workflow_builder_jobs SET input_tokens=?, output_tokens=?, cost_usd=? WHERE id=?''',
            (inference.get('input_tokens', 0), inference.get('output_tokens', 0), inference.get('cost_usd'), job_id))
        conn.execute('''UPDATE workflow_builder_jobs SET status=?, result_json=?, error=?
            WHERE id=? AND status='GENERATING' ''',
            ('FAILED' if error else 'READY', json.dumps(result, ensure_ascii=False) if result else None, error, job_id))
        conn.commit()


@router.get('/ai/chat/{job_id}')
def get_chat(job_id: str, request: Request, db=Depends(get_db_manager)):
    return public_job(read_job(db, claims(request), job_id))


@router.post('/ai/chat/{job_id}/cancel')
def cancel_chat(job_id: str, request: Request, db=Depends(get_db_manager)):
    row = read_job(db, claims(request), job_id)
    with db._get_connection() as conn:
        conn.execute("UPDATE workflow_builder_jobs SET status='CANCELLED' WHERE id=? AND status='GENERATING'", (row['id'],))
        conn.commit()
    return public_job(read_job(db, claims(request), job_id))


@router.post('/ai/chat/{job_id}/create')
def create_from_chat(job_id: str, request: Request, db=Depends(get_db_manager)):
    row = read_job(db, claims(request), job_id)
    if row['status'] == 'CREATED':
        workflow = db.get_workflow(row['workflow_id'])
        if not workflow or workflow.organization_id != row['organization_id'] or workflow.department_id != row['department_id']:
            raise HTTPException(404, 'The created workflow is no longer available in this department.')
        return _workflow_to_response(workflow)
    if row['status'] not in ('READY', 'CREATING'):
        raise HTTPException(409, 'Wait for a complete workflow preview before creating it.')
    result = json.loads(row['result_json'] or '{}')
    if not result.get('workflow'):
        raise HTTPException(422, 'Answer the assistant’s questions before creating a workflow.')
    candidate = ChatWorkflow.model_validate(result['workflow'])
    resources = catalog(db, claims(request), row['department_id'])
    errors = validate_candidate(candidate, resources)
    if errors:
        raise HTTPException(422, {'message': 'Resource permissions changed. Refine the workflow before creating it.', 'errors': errors})
    with db._get_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        current = conn.execute('SELECT * FROM workflow_builder_jobs WHERE id=?', (job_id,)).fetchone()
        workflow_id = current['workflow_id'] or 'wf_' + uuid.uuid4().hex
        conn.execute("UPDATE workflow_builder_jobs SET workflow_id=?, status='CREATING' WHERE id=?", (workflow_id, job_id))
        conn.commit()
    existing = db.get_workflow(workflow_id)
    if existing:
        if existing.organization_id != row['organization_id'] or existing.department_id != row['department_id']:
            raise HTTPException(404, 'The created workflow is no longer available in this department.')
        response = _workflow_to_response(existing)
    else:
        definition = native_definition(candidate, resources, runner_agent_id=f"wf-agent-{workflow_id}")
        payload = WorkflowCreateRequest(name=candidate.name, description=candidate.description,
            department_id=row['department_id'], definition_json=json.dumps(definition),
            cron_expression=candidate.cron_expression, webhook_enabled=False)
        try:
            response = persist_workflow(payload, request, db, workflow_id=workflow_id, initially_active=False)
        except sqlite3.IntegrityError:
            existing = db.get_workflow(workflow_id)
            if not existing:
                raise
            response = _workflow_to_response(existing)
    with db._get_connection() as conn:
        conn.execute("UPDATE workflow_builder_jobs SET status='CREATED' WHERE id=?", (job_id,))
        conn.commit()
    return response
