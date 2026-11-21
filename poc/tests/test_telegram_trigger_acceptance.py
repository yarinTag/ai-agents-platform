"""Actual Telegram ingress-to-engine acceptance without inference or external I/O."""
import json
import time

import pytest

from persistence import DatabaseManager
from poc.tests.test_generic_governance_api import auth, baseline
from poc.tests.test_channel_ingress_api import BASE, configure, telegram_headers, telegram_message
from backend.channel_trigger_worker import consume_one
from storage import channel_ingress
from workflows.engine import WorkflowEngine
from workflows.channel_trigger_dispatch import reserve_dispatches, admit_dispatch


@pytest.fixture
def trigger(baseline):
    db, client = baseline
    connector = configure(client, db, 'telegram')
    response = client.post('/api/v1/governance/channel-bindings', headers=auth(), json={
        'department_id': 'atlas_engineering', 'connector_id': connector,
        'provider': 'telegram', 'channel_id': '12345', 'uses': {'trigger_workflows': True},
    })
    assert response.status_code == 201, response.text
    rule = {'binding_id': response.json()['id'], 'enabled': True,
            'matcher': 'keyword', 'pattern': 'ai49_acceptance',
            'parameters': {'message': 'text'}, 'max_runs_per_hour': 1}
    definition = {'name': 'Telegram trigger acceptance', 'metadata': {}, 'steps': [
        {'key': 'gate_only', 'agent_id': 'atlas_engineering', 'depends_on': [],
         'params': {'dag_approval': {'quorum': 1, 'approver_roles': ['ORG_ADMIN']}}},
    ]}
    workflow = db.create_workflow(id='telegram-trigger-acceptance', name=definition['name'],
        department_id='atlas_engineering', organization_id='atlas', definition_json=json.dumps(definition))
    saved = client.put(f'/api/v1/workflows/{workflow.id}/channel-trigger', headers=auth('MANAGER'),
                       json={'expected_revision': workflow.revision, 'rule': rule})
    assert saved.status_code == 200, saved.text
    with db._get_connection() as conn:
        conn.execute('''INSERT INTO external_identity_links
            (id,organization_id,connector_id,user_id,provider,account,subject,created_at)
            VALUES ('trigger-link','atlas',?,'atlas_OPERATOR','telegram','123456','12345',?)''',
            (connector, int(time.time())))
    return db, client, connector, workflow.id, rule


def receive(client, connector, identifier=10, *, text='ai49_acceptance', bot=False, sender=12345):
    update = telegram_message(update_id=identifier, message_id=identifier, text=text)
    update['message']['from'].update(id=sender, is_bot=bot)
    return client.post(f'{BASE}/{connector}', headers=telegram_headers(), json=update)


def test_telegram_matching_event_reaches_real_gate_once_and_preview_is_inert(trigger):
    db, client, connector, workflow_id, rule = trigger
    preview = client.post(f'/api/v1/workflows/{workflow_id}/channel-trigger/preview', headers=auth(),
        json={'rule': rule, 'event': {'event_type': 'MESSAGE', 'channel_id': '12345',
                                    'message_id': 'preview', 'text': 'ai49_acceptance'}})
    assert preview.status_code == 200 and preview.json()['matched']
    assert db.list_workflow_executions(workflow_id) == []
    assert receive(client, connector).status_code == 202
    assert receive(client, connector).status_code == 200
    assert consume_one(WorkflowEngine(db_manager=db))
    execution, = db.list_workflow_executions(workflow_id)
    assert execution.status == 'WAITING_APPROVAL'
    assert execution.trigger_type == 'CHANNEL'
    reopened = DatabaseManager(str(db.db_path))
    assert not consume_one(WorkflowEngine(db_manager=reopened))
    assert len(reopened.list_workflow_executions(workflow_id)) == 1
    # A different matching event cannot evade the persisted hourly capacity.
    assert receive(client, connector, 11).status_code == 202
    assert consume_one(WorkflowEngine(db_manager=reopened))
    assert len(reopened.list_workflow_executions(workflow_id)) == 1
    with reopened._get_connection() as conn:
        assert conn.execute('SELECT count(*) FROM task_runs').fetchone()[0] == 0
        assert conn.execute('SELECT count(*) FROM channel_trigger_dispatches').fetchone()[0] == 1


@pytest.mark.parametrize('case', ['unrelated', 'bot', 'unlinked', 'inactive_sender',
                                  'inactive_principal', 'inactive_workflow', 'revoked_binding'])
def test_telegram_nonqualifying_events_start_nothing(trigger, case):
    db, client, connector, workflow_id, rule = trigger
    options = {}
    if case == 'unrelated':
        options['text'] = 'ordinary conversation'
    elif case == 'bot':
        options['bot'] = True
    elif case == 'unlinked':
        options['sender'] = 99999
    elif case in ('inactive_sender', 'inactive_principal'):
        db.update_user('atlas_OPERATOR' if case == 'inactive_sender' else 'atlas_MANAGER', status='INACTIVE')
    elif case == 'inactive_workflow':
        db.update_workflow(workflow_id, is_active=False)
    else:
        with db._get_connection() as conn:
            conn.execute('UPDATE channel_bindings SET trigger_workflows=0 WHERE id=?', (rule['binding_id'],))
    assert receive(client, connector, **options).status_code in (200, 202)
    consume_one(WorkflowEngine(db_manager=db))
    assert db.list_workflow_executions(workflow_id) == []


@pytest.mark.parametrize('case', ['revision', 'principal', 'lease', 'expired_text'])
def test_telegram_reservation_rechecks_policy_before_start(trigger, case):
    db, client, connector, workflow_id, _ = trigger
    assert receive(client, connector).status_code == 202
    claim = channel_ingress.claim(db)
    execution_id, = reserve_dispatches(db, claim)
    if case == 'revision':
        db.update_workflow(workflow_id, description='Changed after reservation')
    elif case == 'principal':
        db.update_user('atlas_MANAGER', status='INACTIVE')
    else:
        with db._get_connection() as conn:
            if case == 'lease':
                conn.execute('UPDATE channel_ingress_outbox SET lease_until=0')
            else:
                conn.execute('UPDATE channel_ingress_trigger_inputs SET expires_at=0')
    assert admit_dispatch(db, execution_id, db.get_workflow(workflow_id), claim['lease_token']) is None
    assert db.get_workflow_execution(execution_id).status == 'QUEUED'
