"""One audited merge attempt per persisted human-approved subject; no model entry point."""
import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from .tool_definitions import ToolAccessError
from .pr_approval_policy import fresh_review, merge_tool
from .provider_http import request_json


def now():
    return datetime.now(timezone.utc).isoformat()


def require_claim(db, approval, subject):
    with db._get_connection() as conn:
        row = conn.execute('SELECT * FROM workflow_approvals WHERE id=?', (approval['id'],)).fetchone()
    if (not row or row['status'] != 'RESOLVING' or row['execution_id'] != approval['execution_id']
            or row['organization_id'] != approval['organization_id'] or row['department_id'] != approval['department_id']
            or row['expires_at'] <= datetime.now().isoformat()
            or json.loads(row['config_json']).get('merge_after_approval') is not True
            or subject not in json.loads(row['subjects_json'])):
        raise ToolAccessError('Merge requires the exact live persisted human approval claim and reviewed subject.')
    user = db.get_user(row['resolved_by']) if row['resolved_by'] else None
    if not user or user.status != 'ACTIVE' or user.organization_id != row['organization_id']:
        raise ToolAccessError('The persisted human merge approver is no longer authorized.')
    if user.role != 'ORG_ADMIN' and (user.role != 'MANAGER' or not any(
            member['organization_id'] == row['organization_id'] and member['department_id'] == row['department_id']
            and member['department_role'] in ('MANAGER', 'ORG_ADMIN') for member in db.get_user_departments(user.id))):
        raise ToolAccessError('The persisted human merge approver no longer manages this department.')
    return user.id


def merge_subject(db, approval, subject, approver_check, receipts):
    approver_check()
    actor = require_claim(db, approval, subject)
    def live_claim():
        approver_check()
        require_claim(db, approval, subject)
    client = fresh_review(db, approval, subject, True, live_claim)
    approver_check()
    require_claim(db, approval, subject)
    client.authorize()
    identity = ':'.join(str(subject[key]) for key in ('connector_id', 'repository', 'pull_number', 'head_sha', 'base_sha'))
    identifier = 'call_merge_' + hashlib.sha256((approval['id'] + ':' + identity).encode()).hexdigest()
    connector = db.get_mcp_connector(subject['connector_id'])
    tool = merge_tool(db, connector)
    receipt = {'operation': 'merge_pull_request', 'approval_id': approval['id'], 'audit_id': identifier,
               'connector_id': connector.id, 'repository': subject['repository'], 'pull_number': subject['pull_number'],
               'head_sha': subject['head_sha'], 'base_sha': subject['base_sha'], 'status': 'STARTED',
               'approved_by': actor, 'agent_id': subject['agent_id'], 'started_at': now()}
    with db._get_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        # An intent claim survives a timeout/crash. A repeated resolution cannot issue PUT twice.
        try:
            conn.execute('''INSERT INTO mcp_tool_calls
                (id,connector_id,tool_id,agent_id,task_id,run_id,status,arguments,started_at)
                VALUES (?,?,?,?,?,?,'STARTED',?,?)''',
                (identifier, connector.id, tool.id, subject['agent_id'], approval['task_id'], approval['execution_id'],
                 json.dumps({key: value for key, value in receipt.items() if key != 'status'}), receipt['started_at']))
        except sqlite3.IntegrityError:
            raise ToolAccessError('This approved merge was already attempted. Inspect the receipt; no automatic retry.') from None
        receipts.append(receipt)
        conn.execute('UPDATE workflow_approvals SET receipts_json=? WHERE id=?', (json.dumps(receipts), approval['id']))
    dispatched = False
    try:
        approver_check()
        require_claim(db, approval, subject)
        client.authorize()
        if subject.get('target_sha'):
            from urllib.parse import quote
            branch = client.get('branches/' + quote(subject['target_ref'], safe=''))
            if not isinstance(branch, dict) or (branch.get('commit') or {}).get('sha') != subject['target_sha']:
                raise ToolAccessError('Target branch changed after approval. Create a fresh review and approval.')
        # GitHub's merge API pins the PR head and applies repository merge rules.
        dispatched = True
        value = request_json('api.github.com', f"/repos/{subject['repository']}/pulls/{subject['pull_number']}/merge",
                             headers=client.headers, payload={'sha': subject['head_sha'], 'merge_method': 'squash'}, method='PUT')
        if (not isinstance(value, dict) or value.get('merged') is not True or not isinstance(value.get('sha'), str)
                or not re.fullmatch(r'(?:[0-9a-f]{40}|[0-9a-f]{64})', value['sha'])):
            raise ToolAccessError('GitHub did not confirm the merge identity. Outcome may be unknown; no automatic retry.')
        receipt.update(status='COMPLETED', merge_commit_sha=value['sha'], completed_at=now())
        # Store the acknowledged receipt before any later checks can fail or a batch stops.
        db.update_mcp_tool_call(identifier, 'COMPLETED', result=json.dumps(receipt), completed_at=receipt['completed_at'])
        with db._get_connection() as conn:
            conn.execute('UPDATE workflow_approvals SET receipts_json=? WHERE id=?', (json.dumps(receipts), approval['id']))
    except Exception:
        if receipt['status'] != 'COMPLETED':
            receipt.update(status='UNKNOWN' if dispatched else 'NOT_DISPATCHED', completed_at=now())
            db.update_mcp_tool_call(identifier, 'FAILED', error='Merge outcome unknown; inspect receipt before any recovery.' if dispatched
                                   else 'Merge blocked before dispatch.', result=json.dumps(receipt), completed_at=receipt['completed_at'])
            with db._get_connection() as conn:
                conn.execute('UPDATE workflow_approvals SET receipts_json=? WHERE id=?', (json.dumps(receipts), approval['id']))
        raise
