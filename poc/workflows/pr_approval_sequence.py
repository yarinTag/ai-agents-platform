"""Advance a terminal PR merge gate with one freshly pinned subject at a time."""
import json
import time
import uuid
from datetime import datetime, timedelta

from integrations.github_prs import GitHubReads
from integrations.identity_proofs import InvalidProof
from integrations.pr_approval_policy import authorize_subject
from integrations.tool_definitions import ToolAccessError


def prepare_next(db, approval, subject, approver_check):
    def authorize():
        approver_check()
        return authorize_subject(db, approval, subject, merge=True)

    connector = authorize()
    review = GitHubReads(connector.configuration or {}, subject['repository'], authorize)
    evidence = review.review(subject['pull_number'])
    pull = evidence['pull_request']
    number = subject['pull_number']
    if (pull['head']['sha'] != subject['head_sha'] or pull.get('author') != subject['author']
            or (subject.get('target_ref') and pull['base']['ref'] != subject['target_ref'])):
        raise ToolAccessError(f'PR #{number} changed since the initial review. Start a fresh review for the remaining PRs.')
    if (evidence.get('partial') is not False or evidence.get('evidence_version') != 2
            or evidence.get('approval_ready') is not True or evidence.get('observed_ci_passed') is not True
            or not evidence.get('target_sha')):
        raise ToolAccessError(f'PR #{number} did not pass the fresh evidence checks. Review the remaining PRs before merging.')
    authorize()
    pinned = dict(subject, base_sha=pull['base']['sha'], target_sha=evidence['target_sha'],
                  target_ref=pull['base']['ref'])
    files = evidence.get('files') or []
    paths = [item.get('filename') for item in files if isinstance(item, dict) and item.get('filename')]
    blockers = evidence.get('blocker_codes') or []
    details = "\n".join((
        f"Changed paths ({len(files)}): {', '.join(paths[:5]) or 'none reported'}",
        f"Current merge blockers: {', '.join(blockers) or 'none reported'}",
    ))
    original = pinned.get('review_findings')
    initial_note = f"Initial review finding: {original}\n" if original else ""
    report = (f"Fresh GitHub evidence for {subject['repository']} #{number}\n"
              f"Reviewed head: {pinned['head_sha']}\n"
              f"Target: {pinned['target_ref']} at {pinned['target_sha']}\n"
              "Observed CI passed. The PR head and author match the initial review.\n"
              f"{initial_note}{details}\n"
              "The initial model review is available in the workflow logs.")
    return pinned, report


def enqueue_next(conn, approval, next_review, remaining, now):
    from storage.channel_approval_delivery import enqueue

    subject, report = next_review
    config = json.loads(approval['config_json'])
    identifier = 'wfa_' + uuid.uuid4().hex
    expires = datetime.fromisoformat(now) + timedelta(hours=config['expires_hours'])
    conn.execute("""INSERT INTO workflow_approvals (
        id,execution_id,step_run_id,task_id,organization_id,department_id,workflow_revision,
        status,config_json,subjects_json,report,created_at,expires_at,position,remaining_json
    ) VALUES (?,?,?,?,?,?,?,'PENDING',?,?,?,?,?,?,?)""",
        (identifier, approval['execution_id'], approval['step_run_id'], approval['task_id'],
         approval['organization_id'], approval['department_id'], approval['workflow_revision'],
         approval['config_json'], json.dumps([subject]), report, now, expires.isoformat(),
         approval['position'] + 1, json.dumps(remaining[1:])))
    if config.get('channel_binding_id'):
        enqueue(conn, identifier, config['channel_binding_id'])


def run_receipts(conn, execution_id):
    rows = conn.execute('SELECT receipts_json FROM workflow_approvals WHERE execution_id=? ORDER BY position',
                        (execution_id,))
    return [receipt for row in rows for receipt in json.loads(row['receipts_json'])]



def advance_confirmed(db):
    """Claim a confirmed merge's continuation. This worker performs only reads."""
    from .human_approval import finish

    now = int(time.time())
    claim_until = now + 300
    with db._get_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute("""SELECT a.*,d.callback_id,d.binding_id,d.identity_link_id
            FROM workflow_approvals a LEFT JOIN pr_channel_deliveries d ON d.approval_id=a.id
            WHERE a.status='RESOLVING' AND a.advance_pending=1
            AND (a.advance_claim_until IS NULL OR a.advance_claim_until<=?)
            ORDER BY a.created_at,a.id LIMIT 1""", (now,)).fetchone()
        if not row:
            return
        conn.execute('UPDATE workflow_approvals SET advance_claim_until=? WHERE id=?', (claim_until, row['id']))
        approval = dict(row)

    receipts = json.loads(approval['receipts_json'])
    remaining = json.loads(approval['remaining_json'])

    def authorize():
        from storage.dag_approvals import _role
        with db._get_connection() as conn:
            current = conn.execute('SELECT status,advance_claim_until FROM workflow_approvals WHERE id=?',
                                   (approval['id'],)).fetchone()
            if (not current or current['status'] != 'RESOLVING' or current['advance_claim_until'] != claim_until
                    or claim_until <= int(time.time())
                    or _role(conn, approval, approval['resolved_by']) not in ('MANAGER', 'ORG_ADMIN')):
                raise ToolAccessError('The original approver or continuation claim is no longer authorized.')
            if approval['callback_id']:
                from storage.channel_approval_delivery import destination
                try:
                    binding, _, account, _ = destination(conn, approval)
                except InvalidProof:
                    raise ToolAccessError('The original approval channel is no longer authorized.') from None
                linked = conn.execute("""SELECT 1 FROM external_identity_links WHERE id=? AND organization_id=?
                    AND connector_id=? AND user_id=? AND account=? AND provider=?""",
                    (approval['identity_link_id'], approval['organization_id'], binding['connector_id'],
                     approval['resolved_by'], account, binding['provider'])).fetchone()
                if not linked:
                    raise ToolAccessError('The original channel identity link is no longer authorized.')

    try:
        if not receipts or receipts[-1]['status'] != 'COMPLETED':
            raise ToolAccessError('Confirmed merge receipt is missing. Reconcile the approval before continuing.')
        next_review = prepare_next(db, approval, remaining[0], authorize) if remaining else None
        finish(db, approval, 'APPROVED', receipts=receipts, next_review=next_review, advance_claim=claim_until)
    except ToolAccessError as exc:
        finish(db, approval, 'APPROVED', str(exc), receipts, advance_claim=claim_until)
