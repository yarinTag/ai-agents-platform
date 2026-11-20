"""Authenticated dashboard reads and decisions for saved workflow approvals."""
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
    approval_id: str | None = None


def _row(db, execution_id, approval_id=None):
    with db._get_connection() as conn:
        if approval_id is not None:
            row = conn.execute('SELECT * FROM workflow_approvals WHERE execution_id=? AND id=?',
                               (execution_id, approval_id)).fetchone()
        else:
            row = conn.execute('SELECT * FROM workflow_approvals WHERE execution_id=? ORDER BY position DESC LIMIT 1',
                               (execution_id,)).fetchone()
        return dict(row) if row else None


def _public(row):
    config = json.loads(row['config_json'])
    return {'id': row['id'], 'status': row['status'], 'report': row['report'],
            'kind': config['kind'], 'merge_after_approval': config['merge_after_approval'],
            'expires_at': row['expires_at'], 'resolved_by': row['resolved_by'], 'error': row['error'],
            'position': row['position'], 'remaining_count': len(json.loads(row['remaining_json'])),
            'subjects': [{key: subject[key] for key in ('repository', 'pull_number', 'head_sha', 'base_sha', 'url')}
                         for subject in json.loads(row['subjects_json'])],
            'receipts': json.loads(row['receipts_json'])}


@router.get('/executions/{execution_id}/approval')
def get_workflow_approval(execution_id: str, request: Request, approval_id: str | None = None,
                          db=Depends(get_db_manager)):
    actor = load_actor(request, db)
    Resources(actor).require('execution', execution_id)
    row = _row(db, execution_id, approval_id)
    if not row:
        return None
    from workflows.human_approval import expire_if_due
    from workflows.pr_approval_sequence import run_receipts
    expire_if_due(db, row)
    with db._get_connection() as conn:
        if approval_id is None:
            conn.execute('BEGIN')
            current = conn.execute('SELECT * FROM workflow_approvals WHERE execution_id=? ORDER BY position DESC LIMIT 1',
                                   (execution_id,)).fetchone()
            if not current:
                return None
            result = _public(current)
            result['receipts'] = run_receipts(conn, execution_id)
        else:
            current = conn.execute('SELECT * FROM workflow_approvals WHERE id=? AND execution_id=?',
                                   (row['id'], execution_id)).fetchone()
            result = _public(current) if current else None
    return result


@router.post('/executions/{execution_id}/approval', status_code=202)
def decide_workflow_approval(execution_id: str, payload: ApprovalDecision, request: Request,
                             background: BackgroundTasks, db=Depends(get_db_manager)):
    actor = load_actor(request, db)
    if not actor.user_id:
        raise HTTPException(403, 'A signed-in human approver is required.')
    Resources(actor).require('execution', execution_id, 3)
    row = _row(db, execution_id, payload.approval_id)
    if not row or (payload.approval_id is None and
                   (row['position'] != 0 or json.loads(row['remaining_json']))):
        # Legacy single-gate clients can only claim their one original round.
        raise HTTPException(409, 'This approval changed. Refresh and review the current PR.')

    def authorize():
        actor = load_actor(request, db)
        if not actor.user_id:
            raise HTTPException(403, 'A signed-in human approver is required.')
        Resources(actor).require('execution', execution_id, 3)
        current = _row(db, execution_id, row['id'])
        if not current or current['expires_at'] <= datetime.now().isoformat():
            raise HTTPException(409, 'This approval is unavailable or expired. Start a new review.')
        return actor

    with db._get_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        updated = conn.execute('''UPDATE workflow_approvals SET status='RESOLVING',resolved_by=?
            WHERE id=? AND status='PENDING' AND expires_at>?
            AND EXISTS(SELECT 1 FROM workflow_executions WHERE id=? AND status='WAITING_APPROVAL')''',
            (actor.user_id, row['id'], datetime.now().isoformat(), execution_id)).rowcount
        if updated != 1:
            raise HTTPException(409, 'The gate is not waiting, or another decision already claimed it. No retry is performed.')
        conn.execute("UPDATE pr_channel_deliveries SET retry_at=0 WHERE approval_id=?", (row['id'],))
    from workflows.human_approval import resolve
    background.add_task(resolve, db, row, payload.approve, authorize)
    return {'id': row['id'], 'status': 'RESOLVING'}
