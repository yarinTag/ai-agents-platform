"""Telegram acceptance against actual routes/storage; no provider or model mocks."""
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from persistence import DatabaseManager
from poc.tests.test_generic_governance_api import auth, baseline
from poc.tests.test_channel_ingress_api import (
    BASE, SECRET, configure, telegram_headers,
)
from integrations.telegram_approval_cards import action_token, signed_action
from storage import channel_approval_delivery as delivery, dag_approvals


@pytest.fixture
def gate(baseline):
    db, client = baseline
    connector = configure(client, db, 'telegram')
    response = client.post('/api/v1/governance/channel-bindings', headers=auth(), json={
        'department_id': 'atlas_engineering', 'connector_id': connector,
        'provider': 'telegram', 'channel_id': '12345',
        'uses': {'approve_decisions': True, 'send_notifications': True},
    })
    assert response.status_code == 201, response.text
    workflow = db.create_workflow(id='telegram-acceptance', name='Acceptance',
        definition_json='{}', department_id='atlas_engineering', organization_id='atlas')
    db.create_workflow_execution('acceptance-run', workflow.id, 'MANUAL',
                                 department_id=workflow.department_id)
    identifier = dag_approvals.suspend(db, execution_id='acceptance-run', step_key='gate',
        revision=workflow.revision, initiator_id='atlas_OPERATOR',
        policy={'approver_roles': ['MANAGER', 'ORG_ADMIN'], 'quorum': 1,
                'timeout_seconds': 600, 'channel_binding_id': response.json()['id']},
        checkpoint={'outputs': {}, 'input_tokens': 0, 'output_tokens': 0, 'cost_usd': 0})
    assert delivery.next_delivery(db)['id'] == identifier
    token = action_token(db.get_mcp_connector(connector).configuration['bot_token'], identifier)
    delivery.record_delivery(db, identifier, 'DELIVERED', connector=connector, channel='12345',
                             message='7', bot='123456', rendered='PENDING:0/1', token=token)
    with db._get_connection() as conn:
        for subject, user in [('12345', 'atlas_MANAGER'), ('23456', 'atlas_OPERATOR'),
                              ('34567', 'atlas_MEMBER'), ('45678', 'boreal_MANAGER')]:
            conn.execute('''INSERT INTO external_identity_links
                (id,organization_id,connector_id,user_id,provider,account,subject,created_at)
                VALUES (?,?,?,?,?,?,?,?)''',
                ('link-' + subject, 'atlas', connector, user, 'telegram', '123456', subject, int(time.time())))

    def post(*, sender=12345, action='a', callback='123', channel=12345, message=7):
        update = {'callback_query': {'id': callback,
            'data': f'dga:{action}:{token}:{signed_action(SECRET, token, action)}',
            'from': {'id': sender, 'is_bot': False},
            'message': {'message_id': message, 'chat': {'id': channel}, 'from': {'id': 123456}}}}
        result = client.post(f'{BASE}/{connector}', headers=telegram_headers(), json=update)
        assert result.status_code == 200, result.text
        return result.json()['text']

    return db, client, workflow, identifier, response.json()['id'], post


@pytest.mark.parametrize('case', ['unlinked', 'initiator', 'member', 'foreign', 'inactive',
                                  'membership', 'binding', 'wrong_channel', 'wrong_message', 'revision'])
def test_telegram_denied_actor_and_scope_never_vote(gate, case):
    db, _, workflow, identifier, binding, post = gate
    options = {}
    if case in ('unlinked', 'initiator', 'member', 'foreign'):
        options['sender'] = {'unlinked': 99999, 'initiator': 23456,
                             'member': 34567, 'foreign': 45678}[case]
    elif case == 'inactive':
        db.update_user('atlas_MANAGER', status='INACTIVE')
    elif case == 'membership':
        db.remove_user_from_department('atlas_engineering', 'atlas_MANAGER')
    elif case == 'binding':
        with db._get_connection() as conn:
            conn.execute('UPDATE channel_bindings SET approve_decisions=0 WHERE id=?', (binding,))
    elif case == 'revision':
        db.update_workflow(workflow.id, description='Changed definition revision')
    else:
        options['channel' if case == 'wrong_channel' else 'message'] = 99
    assert post(**options).startswith('Decision unavailable')
    with db._get_connection() as conn:
        assert conn.execute('SELECT count(*) FROM workflow_dag_approval_votes').fetchone()[0] == 0
        assert conn.execute('SELECT count(*) FROM dag_channel_callbacks').fetchone()[0] == 0
    assert dag_approvals.claim_resume(db, identifier, workflow.id, workflow.revision) is None


def test_telegram_reject_closes_gate_without_continuation(gate):
    db, _, workflow, identifier, _, post = gate
    assert post(action='r') == 'Decision recorded.'
    assert db.get_workflow_execution('acceptance-run').status == 'FAILED'
    assert delivery.next_edit(db)[1] == 'REJECTED'
    assert dag_approvals.claim_resume(db, identifier, workflow.id, workflow.revision) is None
    assert post(callback='124').startswith('Decision unavailable')


def test_telegram_expiry_survives_reopen_and_cannot_resume(gate):
    db, _, workflow, identifier, _, post = gate
    with db._get_connection() as conn:
        conn.execute('UPDATE workflow_dag_approvals SET expires_at=? WHERE id=?',
                     (int(time.time()) - 1, identifier))
    reopened = DatabaseManager(str(db.db_path))
    dag_approvals.expire(reopened)
    assert post().startswith('Decision unavailable')
    assert reopened.get_workflow_execution('acceptance-run').status == 'FAILED'
    assert delivery.next_edit(reopened)[1] == 'TIMED_OUT'
    assert dag_approvals.claim_resume(reopened, identifier, workflow.id, workflow.revision) is None


def test_telegram_concurrent_clicks_and_restart_resume_once(gate):
    db, _, workflow, identifier, _, post = gate
    barrier = Barrier(2, timeout=10)
    def click(callback):
        barrier.wait()
        return post(callback=callback)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(click, ['123', '124']))
    assert results.count('Decision recorded.') == 1
    reopened = DatabaseManager(str(db.db_path))
    assert dag_approvals.next_approved(reopened)['id'] == identifier
    assert dag_approvals.claim_resume(reopened, identifier, workflow.id, workflow.revision)
    again = DatabaseManager(str(db.db_path))
    assert dag_approvals.claim_resume(again, identifier, workflow.id, workflow.revision) is None
    with again._get_connection() as conn:
        assert conn.execute('SELECT count(*) FROM workflow_dag_approval_votes').fetchone()[0] == 1
        assert conn.execute('SELECT count(*) FROM dag_channel_callbacks').fetchone()[0] == 1


def test_telegram_revocation_after_vote_blocks_restart_resume(gate):
    db, _, workflow, identifier, _, post = gate
    assert post() == 'Decision recorded.'
    db.update_user('atlas_MANAGER', status='INACTIVE')
    reopened = DatabaseManager(str(db.db_path))
    assert dag_approvals.claim_resume(reopened, identifier, workflow.id, workflow.revision) is None
    dag_approvals.fail_resume(reopened, identifier)
    assert reopened.get_workflow_execution('acceptance-run').status == 'FAILED'
