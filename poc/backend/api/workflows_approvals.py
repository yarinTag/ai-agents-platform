"""Authenticated workflow gate decisions. Telegram contains links, never authority."""
import json
from datetime import datetime
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict
from ..dependencies import get_db_manager
from ..security.identity import load_actor
from ..security.resource_access import Resources

router = APIRouter()


class ApprovalDecision(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    approve: bool


def _row(db, execution_id):
    with db._get_connection() as conn:
        row = conn.execute('SELECT * FROM workflow_approvals WHERE execution_id=?', (execution_id,)).fetchone()
    return dict(row) if row else None


def _public(row):
    config = json.loads(row['config_json'])
    return {'id': row['id'], 'status': row['status'], 'report': row['report'],
            'kind': config['kind'], 'merge_after_approval': config['merge_after_approval'],
            'expires_at': row['expires_at'], 'resolved_by': row['resolved_by'], 'error': row['error'],
            'subjects': [{key: subject[key] for key in ('repository', 'pull_number', 'head_sha', 'base_sha', 'url')}
                         for subject in json.loads(row['subjects_json'])],
            'receipts': json.loads(row['receipts_json'])}


@router.get('/executions/{execution_id}/approval')
def get_workflow_approval(execution_id: str, request: Request, db=Depends(get_db_manager)):
    actor = load_actor(request, db)
    Resources(actor).require('execution', execution_id)
    row = _row(db, execution_id)
    if row:
        from workflows.human_approval import expire_if_due
        expire_if_due(db, row)
        row = _row(db, execution_id)
    return _public(row) if row else None


@router.post('/executions/{execution_id}/approval', status_code=202)
def decide_workflow_approval(execution_id: str, payload: ApprovalDecision, request: Request,
                             background: BackgroundTasks, db=Depends(get_db_manager)):
    def authorize():
        actor = load_actor(request, db)
        if not actor.user_id:
            raise HTTPException(403, 'A signed-in human approver is required.')
        Resources(actor).require('execution', execution_id, 3)
        current = _row(db, execution_id)
        if not current or current['expires_at'] <= datetime.now().isoformat():
            raise HTTPException(409, 'This approval is unavailable or expired. Start a new review.')
        return actor
    actor = authorize()
    row = _row(db, execution_id)
    with db._get_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        updated = conn.execute('''UPDATE workflow_approvals SET status='RESOLVING',resolved_by=?
            WHERE id=? AND status='PENDING' AND expires_at>?
            AND EXISTS(SELECT 1 FROM workflow_executions WHERE id=? AND status='WAITING_APPROVAL')''',
            (actor.user_id, row['id'], datetime.now().isoformat(), execution_id)).rowcount
        if updated != 1:
            raise HTTPException(409, 'The gate is not waiting, or another decision already claimed it. No retry is performed.')
    from workflows.human_approval import resolve
    background.add_task(resolve, db, row, payload.approve, authorize)
    return {'id': row['id'], 'status': 'RESOLVING'}
